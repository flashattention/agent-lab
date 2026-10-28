"""격리된 subprocess 에서 사용자 Python 코드를 실행한다.

공개 배포를 전제로 한 방어선:
- 실행마다 새 임시 디렉터리, 최소 환경변수(서버 비밀값 전달 안 함)
- 프로세스 그룹 단위 타임아웃 kill, 출력량 상한
- Linux 에서는 rlimit(CPU/메모리/파일크기/프로세스 수) 적용
- 전역 동시 실행 수 제한(세마포어)
컨테이너 수준 격리(non-root, read-only rootfs)는 Dockerfile 에서 담당한다.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

SANDBOX_DIR = Path(__file__).resolve().parent.parent / "sandbox"
MAX_OUTPUT = int(os.getenv("AGENTLAB_MAX_OUTPUT", 200_000))
MAX_TIMEOUT = int(os.getenv("AGENTLAB_MAX_TIMEOUT", 90))
MAX_CONCURRENCY = int(os.getenv("AGENTLAB_MAX_CONCURRENCY", 8))
MAX_FILES = 64
MAX_FILE_BYTES = 200_000

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


class RunError(ValueError):
    pass


@dataclass
class RunResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    timed_out: bool = False
    mock: bool = False
    events: list[dict] = field(default_factory=list)


def _safe_path(root: Path, rel: str) -> Path:
    rel = rel.replace("\\", "/").lstrip("/")
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise RunError(f"잘못된 파일 경로: {rel}")
    return p


def _preexec(timeout: int):
    def fn():  # pragma: no cover - 자식 프로세스에서 실행
        os.setsid()
        if sys.platform.startswith("linux"):
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (timeout + 5, timeout + 5))
            mem = int(os.getenv("AGENTLAB_MEM_LIMIT_MB", 1024)) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))

    return fn


def _build_env(workdir: Path, api_key: str | None, model: str | None) -> tuple[dict, bool]:
    mock = not api_key
    env = {
        "PATH": os.path.dirname(sys.executable) + ":/usr/bin:/bin",
        "HOME": str(workdir),
        "TMPDIR": str(workdir),
        "PYTHONPATH": f"{SANDBOX_DIR}:{workdir}",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LANGSMITH_TRACING": "false",
        "LAB_MODEL": model or "openai:gpt-5-mini",
        # 실행마다 HOME/TMPDIR 이 바뀌므로 tiktoken 인코딩 캐시는 고정 경로를 쓴다
        "TIKTOKEN_CACHE_DIR": os.getenv("TIKTOKEN_CACHE_DIR", str(SANDBOX_DIR.parent / "data" / "tiktoken")),
    }
    if mock:
        env["AGENTLAB_MOCK"] = "1"
    else:
        env["OPENAI_API_KEY"] = api_key  # type: ignore[assignment]
    return env, mock


async def stream_run(
    files: dict[str, str],
    entry: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
    stdin: str | None = None,
) -> AsyncIterator[dict]:
    """실행 이벤트를 순서대로 yield 한다: start → stdout/stderr* → exit."""
    if len(files) > MAX_FILES:
        raise RunError("파일이 너무 많습니다.")
    if any(len(c.encode()) > MAX_FILE_BYTES for c in files.values()):
        raise RunError("파일 하나가 너무 큽니다 (200KB 제한).")
    if entry not in files:
        raise RunError(f"엔트리 파일 {entry} 이(가) 없습니다.")
    timeout = max(1, min(int(timeout), MAX_TIMEOUT))

    async with _semaphore:
        workdir = Path(tempfile.mkdtemp(prefix="agentlab-")).resolve()
        try:
            for rel, content in files.items():
                p = _safe_path(workdir, rel)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            env, mock = _build_env(workdir, api_key, model)
            yield {"type": "start", "mock": mock, "entry": entry}
            started = time.perf_counter()
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-X",
                "utf8",
                str(_safe_path(workdir, entry)),
                cwd=str(workdir),
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=_preexec(timeout),
            )
            if stdin:
                proc.stdin.write(stdin.encode())  # type: ignore[union-attr]
            proc.stdin.close()  # type: ignore[union-attr]

            queue: asyncio.Queue[dict | None] = asyncio.Queue()
            budget = {"left": MAX_OUTPUT}

            async def pump(stream: asyncio.StreamReader, kind: str):
                while True:
                    chunk = await stream.read(4096)
                    if not chunk:
                        break
                    if budget["left"] <= 0:
                        continue
                    text = chunk.decode("utf-8", errors="replace")
                    if kind == "stderr":
                        text = text.replace(str(workdir) + "/", "")
                    text = text[: budget["left"]]
                    budget["left"] -= len(text)
                    await queue.put({"type": kind, "data": text})
                    if budget["left"] <= 0:
                        await queue.put({"type": "stderr", "data": "\n[AgentLab] 출력이 너무 길어 잘렸습니다.\n"})
                await queue.put(None)

            tasks = [
                asyncio.create_task(pump(proc.stdout, "stdout")),  # type: ignore[arg-type]
                asyncio.create_task(pump(proc.stderr, "stderr")),  # type: ignore[arg-type]
            ]
            done_streams = 0
            timed_out = False
            deadline = started + timeout
            while done_streams < 2:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    timed_out = True
                    break
                if item is None:
                    done_streams += 1
                else:
                    yield item
            if timed_out:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                yield {"type": "stderr", "data": f"\n[AgentLab] 실행 시간 {timeout}초를 초과하여 중단했습니다.\n"}
            code = await proc.wait()
            for t in tasks:
                t.cancel()
            yield {
                "type": "exit",
                "code": code,
                "timed_out": timed_out,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "mock": mock,
            }
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


async def run_collect(files: dict[str, str], entry: str, **kw) -> RunResult:
    res = RunResult()
    async for ev in stream_run(files, entry, **kw):
        res.events.append(ev)
        if ev["type"] == "stdout":
            res.stdout += ev["data"]
        elif ev["type"] == "stderr":
            res.stderr += ev["data"]
        elif ev["type"] == "start":
            res.mock = ev["mock"]
        elif ev["type"] == "exit":
            res.exit_code = ev["code"]
            res.duration_ms = ev["duration_ms"]
            res.timed_out = ev["timed_out"]
    return res
