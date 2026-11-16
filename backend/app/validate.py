"""생성된 코드 검증: ruff 정적 분석 + Mock LLM 모드 실제 실행(smoke test)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .runner import _safe_path, check_files, run_collect

RUFF = shutil.which("ruff", path=os.path.dirname(sys.executable)) or shutil.which("ruff") or "ruff"
# 문법 오류, 정의되지 않은 이름, 잘못된 비교 등 "실행하면 터지는" 규칙만 엄격하게 본다.
SELECT = "E9,F63,F7,F82,F821,F811,F601,F632"


async def lint(files: dict[str, str]) -> list[dict]:
    check_files(files)
    workdir = Path(tempfile.mkdtemp(prefix="agentlab-lint-"))
    try:
        for rel, content in files.items():
            if not rel.endswith(".py"):
                continue
            p = _safe_path(workdir, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            RUFF, "check", "--output-format", "json", "--no-cache", "--select", SELECT, ".",
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
        try:
            raw = json.loads(out.decode() or "[]")
        except json.JSONDecodeError:
            return []
        return [
            {
                "file": os.path.relpath(os.path.realpath(d.get("filename", "")), os.path.realpath(workdir)),
                "line": (d.get("location") or {}).get("row"),
                "col": (d.get("location") or {}).get("column"),
                "code": d.get("code") or "syntax",
                "message": d.get("message"),
            }
            for d in raw
        ]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def validate(files: dict[str, str], entry: str = "main.py", timeout: int = 45) -> dict:
    issues = await lint(files)
    report: dict = {"lint": issues, "run": None, "ok": False}
    if issues:
        return report
    # API 키 없이 Mock 모드로 실행 → 그래프 컴파일 + 전체 경로 실행까지 확인
    res = await run_collect(files, entry, api_key=None, timeout=timeout)
    report["run"] = {
        "exit_code": res.exit_code,
        "timed_out": res.timed_out,
        "stdout": res.stdout[-4000:],
        "stderr": res.stderr[-4000:],
        "duration_ms": res.duration_ms,
    }
    report["ok"] = res.exit_code == 0 and not res.timed_out
    return report
