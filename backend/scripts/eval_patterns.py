"""패턴 실행 eval: 코드 생성기가 만든 패턴 12종을 샌드박스에서 실행하고 트레이스로 동작을 측정한다.

사용법:
    uv run python scripts/eval_patterns.py                 # Mock LLM, 패턴마다 3회
    uv run python scripts/eval_patterns.py --runs 5 --json out.json
    OPENAI_API_KEY=sk-... uv run python scripts/eval_patterns.py --live --runs 1   # 실제 모델 (비용 발생)

입력: tests/fixtures/patterns.json (frontend 에서 `npm run export:patterns` 로 생성)
측정: 성공률(exit 0), 실행 시간(p50/max), 실행된 노드 수, LLM 호출 수, 도구 호출 수, 토큰, 트레이스 이벤트 수
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AGENTLAB_NPROC_LIMIT", "0")

from app.runner import stream_run  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "patterns.json"


async def run_once(files: dict[str, str], api_key: str | None, model: str | None, timeout: int = 90) -> dict:
    stats = {"ok": False, "ms": 0, "nodes": 0, "llm": 0, "tools": 0, "tokens": 0, "events": 0, "errors": 0, "stderr": ""}
    async for ev in stream_run(files, "main.py", api_key=api_key, model=model, timeout=timeout):
        if ev["type"] == "trace":
            e = ev["event"]
            stats["events"] += 1
            if e["ev"] == "start":
                stats["nodes"] += e["kind"] == "node"
                stats["llm"] += e["kind"] == "llm"
                stats["tools"] += e["kind"] == "tool"
            else:
                stats["tokens"] += (e.get("usage") or {}).get("total", 0)
                stats["errors"] += e.get("status") == "error"
        elif ev["type"] == "stderr":
            stats["stderr"] += ev["data"]
        elif ev["type"] == "exit":
            stats["ok"] = ev["code"] == 0 and not ev["timed_out"]
            stats["ms"] = ev["duration_ms"]
    return stats


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--live", action="store_true", help="OPENAI_API_KEY 로 실제 모델 호출 (비용 발생)")
    ap.add_argument("--model", default="openai:gpt-5-mini")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=90, help="실행 1회 상한(초). 서버 AGENTLAB_MAX_TIMEOUT 를 넘으면 그 값으로 줄어든다")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY") if args.live else None
    if args.live and not api_key:
        print("--live 에는 OPENAI_API_KEY 가 필요합니다.", file=sys.stderr)
        return 2

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(args.concurrency)

    async def bounded(files):
        async with sem:
            return await run_once(files, api_key, args.model, args.timeout)

    rows = []
    for p in data["patterns"]:
        results = await asyncio.gather(*(bounded(p["files"]) for _ in range(args.runs)))
        ok = [r for r in results if r["ok"]]
        ms = [r["ms"] for r in results]
        first = ok[0] if ok else results[0]
        rows.append(
            {
                "id": p["id"],
                "title": p["title"],
                "category": p["category"],
                "graph_nodes": len(p["nodes"]),
                "success": f"{len(ok)}/{len(results)}",
                "success_rate": len(ok) / len(results),
                "p50_ms": int(statistics.median(ms)),
                "max_ms": max(ms),
                "nodes_run": first["nodes"],
                "llm_calls": first["llm"],
                "tool_calls": first["tools"],
                "tokens": first["tokens"],
                "trace_events": first["events"],
                "analysis_warnings": p["analysis"]["warnings"],
                "failure": "" if ok else results[0]["stderr"][-400:],
            }
        )
        r = rows[-1]
        print(
            f"{'✅' if r['success_rate'] == 1 else '❌'} {r['id']:<16} {r['success']}  p50 {r['p50_ms']:>5}ms  nodes {r['nodes_run']:>2}  llm {r['llm_calls']:>2}  tools {r['tool_calls']:>2}"
        )

    total_runs = sum(int(r["success"].split("/")[1]) for r in rows)
    total_ok = sum(int(r["success"].split("/")[0]) for r in rows)
    summary = {
        "mode": "live" if args.live else "mock",
        "model": args.model if args.live else "AgentLab Mock LLM",
        "generator": data["generator"],
        "patterns": len(rows),
        "runs_per_pattern": args.runs,
        "success_rate": total_ok / total_runs,
        "p50_ms_overall": int(statistics.median(r["p50_ms"] for r in rows)),
    }
    print(f"\n성공 {total_ok}/{total_runs} ({summary['success_rate']:.0%}), 패턴별 p50 의 중앙값 {summary['p50_ms_overall']}ms")
    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if total_ok == total_runs else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
