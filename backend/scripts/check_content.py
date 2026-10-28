"""학습/문서 콘텐츠의 모든 Python 코드를 Mock LLM 모드로 실제 실행해 검증한다.

사용법:
    uv run python scripts/check_content.py                 # 전체
    uv run python scripts/check_content.py 03-langgraph    # 경로에 문자열이 포함된 것만

규칙
- examples/*.py, solution.py : exit 0 이어야 통과
- exercise.py                : 문법(ruff E9/F821 등)만 검사 (TODO 상태이므로 실행 실패 허용)
- lesson 폴더의 다른 .py 파일들은 같은 작업 디렉터리에 함께 복사된다(import 가능)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.runner import run_collect  # noqa: E402
from app.validate import lint  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "content" / "learn"


async def check_lesson(lesson: Path, sem: asyncio.Semaphore) -> list[tuple[str, bool, str]]:
    py_files = {str(p.relative_to(lesson)): p.read_text(encoding="utf-8") for p in lesson.rglob("*.py")}
    results = []
    issues = await lint(py_files)
    for i in issues:
        results.append((f"{lesson.name}/{i['file']}:{i['line']}", False, f"{i['code']} {i['message']}"))
    runnable = [k for k in py_files if k.startswith("examples/") or k == "solution.py"]
    for entry in sorted(runnable):
        # 예제/정답은 import 경로를 단순하게: 해당 파일을 main 위치(루트)에 둔다
        files = dict(py_files)
        async with sem:
            res = await run_collect(files, entry, api_key=None, timeout=60)
        ok = res.exit_code == 0 and not res.timed_out
        tail = (res.stderr.strip().splitlines() or [""])[-1] if not ok else res.stdout.strip()[-120:].replace("\n", " ⏎ ")
        results.append((f"{lesson.name}/{entry}", ok, tail))
    return results


async def main(filt: str | None):
    lessons = sorted({p.parent for p in ROOT.rglob("lesson.md")})
    if filt:
        lessons = [l for l in lessons if filt in str(l)]
    sem = asyncio.Semaphore(6)
    all_res = await asyncio.gather(*(check_lesson(l, sem) for l in lessons))
    fails = 0
    for res in all_res:
        for name, ok, msg in res:
            fails += not ok
            print(("✅" if ok else "❌"), name, "—", msg[:200])
    print(f"\n{len(lessons)} lessons, {sum(len(r) for r in all_res)} checks, {fails} failures")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
