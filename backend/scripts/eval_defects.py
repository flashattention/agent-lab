"""분석기가 막지 않았다면: 결함을 주입한 그래프의 생성 코드를 실제로 실행해 결과를 분류한다.

사용법:
    (frontend) npx vite-node scripts/eval-analyzer.ts ../docs/eval/analyzer.json /tmp/defects.json
    (backend)  uv run python scripts/eval_defects.py /tmp/defects.json --json ../docs/eval/defects-runtime.json

분류: crash(예외로 종료) / hang(시간 초과·recursion_limit) / silent(exit 0 — 결함이 드러나지 않고 지나감) / codegen(코드 생성 단계 실패)
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AGENTLAB_NPROC_LIMIT", "0")

from app.runner import RunError, run_collect  # noqa: E402


def classify(res) -> str:
    if res.timed_out or "GraphRecursionError" in res.stderr or "recursion_limit" in res.stdout:
        return "hang"
    if res.exit_code != 0:
        return "crash"
    return "silent"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("defects", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()
    items = json.loads(args.defects.read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(6)

    async def one(it):
        if "codegenError" in it:
            return {**it, "outcome": "codegen", "detail": it["codegenError"][:200]}
        async with sem:
            try:
                res = await run_collect(it["files"], "main.py", timeout=args.timeout)
            except RunError as e:
                return {"pattern": it["pattern"], "mutation": it["mutation"], "outcome": "crash", "detail": str(e)}
        last = (res.stderr.strip().splitlines() or [""])[-1][:200]
        return {"pattern": it["pattern"], "mutation": it["mutation"], "outcome": classify(res), "detail": last, "ms": res.duration_ms}

    rows = await asyncio.gather(*(one(it) for it in items))
    by_mut = collections.defaultdict(collections.Counter)
    for r in rows:
        by_mut[r["mutation"]][r["outcome"]] += 1
    total = collections.Counter(r["outcome"] for r in rows)
    for m, c in by_mut.items():
        print(f"{m:<16} " + "  ".join(f"{k} {v}" for k, v in sorted(c.items())))
    print(f"\n전체 {len(rows)}건: " + ", ".join(f"{k} {v}" for k, v in sorted(total.items())))
    if args.json:
        args.json.write_text(
            json.dumps(
                {"total": dict(total), "by_mutation": {k: dict(v) for k, v in by_mut.items()}, "rows": rows}, ensure_ascii=False, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
