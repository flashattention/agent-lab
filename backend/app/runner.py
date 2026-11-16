"""격리된 subprocess 에서 사용자 Python 코드를 실행한다.

공개 배포를 전제로 한 방어선:
- 실행마다 새 임시 디렉터리, 최소 환경변수(서버 비밀값 전달 안 함)
- 프로세스 그룹 단위 타임아웃 kill, 출력량 상한
- Linux 에서는 rlimit(CPU/메모리/파일크기/프로세스 수) 적용
- 전역 동시 실행 수 제한(세마포어)
- audit hook 보안 정책(sandbox/agentlab_guard.py): 네트워크 허용 목록, 외부 프로그램 실행 차단
컨테이너 수준 격리(non-root, read-only rootfs)는 Dockerfile 에서 담당한다.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import sys
import sysconfig
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

SANDBOX_DIR = Path(__file__).resolve().parent.parent / "sandbox"
MAX_OUTPUT = int(os.getenv("AGENTLAB_MAX_OUTPUT", 200_000))
MAX_TIMEOUT = int(os.getenv("AGENTLAB_MAX_TIMEOUT", 90))
MAX_CONCURRENCY = int(os.getenv("AGENTLAB_MAX_CONCURRENCY", 8))
MAX_FILES = int(os.getenv("AGENTLAB_MAX_FILES", 256))  # 서브 에이전트마다 패키지가 생기므로 넉넉히
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = int(os.getenv("AGENTLAB_MAX_TOTAL_BYTES", 2_000_000))
# 실제 키로 실행할 때 접속을 허용할 호스트. Mock 모드에서는 외부 연결을 모두 막는다.
EGRESS_ALLOW = os.getenv("AGENTLAB_EGRESS_ALLOW", "api.openai.com")
GUARD = SANDBOX_DIR / "agentlab_guard.py"

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


class RunError(ValueError):
    pass


def check_files(files: dict[str, str], entry: str | None = None) -> None:
    """디스크에 쓰기 전에 파일 수·크기를 검사한다 (실행·린트 공통)."""
    if len(files) > MAX_FILES:
        raise RunError(f"파일이 너무 많습니다 ({len(files)}개, 최대 {MAX_FILES}개).")
    total = 0
    for rel, content in files.items():
        if not isinstance(content, str):
            raise RunError(f"파일 내용이 문자열이 아닙니다: {rel}")
        size = len(content.encode())
        if size > MAX_FILE_BYTES:
            raise RunError(f"파일 하나가 너무 큽니다: {rel} (200KB 제한).")
        total += size
        if len(rel) > 300 or "\x00" in rel:
            raise RunError(f"잘못된 파일 경로: {rel[:60]}")
    if total > MAX_TOTAL_BYTES:
        raise RunError(f"파일 전체 크기가 너무 큽니다 ({total // 1000}KB, 최대 {MAX_TOTAL_BYTES // 1000}KB).")
    if entry is not None and entry not in files:
        raise RunError(f"엔트리 파일 {entry} 이(가) 없습니다.")


def _install_guard_pth() -> None:
    """샌드박스 파이썬이 -I(격리 모드)로 자식 파이썬을 띄워도 보안 정책이 걸리도록
    site-packages 에 .pth 를 둔다. AGENTLAB_SANDBOX=1 일 때만 동작하므로 서버 프로세스에는 영향이 없다.
    Docker 이미지에서는 빌드 단계에서 미리 만들어 두고(읽기 전용 FS), 로컬 개발에서는 여기서 만든다."""
    try:
        target = Path(sysconfig.get_paths()["purelib"]) / "agentlab_guard.pth"
        line = f"import os; os.environ.get('AGENTLAB_SANDBOX') == '1' and __import__('runpy').run_path({str(GUARD)!r})\n"
        if not target.exists() or target.read_text() != line:
            target.write_text(line)
    except OSError:
        pass


_install_guard_pth()


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
        "AGENTLAB_SANDBOX": "1",
        # 실행마다 HOME/TMPDIR 이 바뀌므로 tiktoken 인코딩 캐시는 고정 경로를 쓴다
        "TIKTOKEN_CACHE_DIR": os.getenv("TIKTOKEN_CACHE_DIR", str(SANDBOX_DIR.parent / "data" / "tiktoken")),
    }
    if mock:
        env["AGENTLAB_MOCK"] = "1"
        env["AGENTLAB_EGRESS_ALLOW"] = ""
    else:
        env["AGENTLAB_EGRESS_ALLOW"] = EGRESS_ALLOW
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
    check_files(files, entry)
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
