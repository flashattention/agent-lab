"""패턴 통합 테스트: 프론트엔드 코드 생성기가 만든 프로젝트 12종을 샌드박스에서 Mock 실행한다.

fixture 는 frontend 에서 `npm run export:patterns` 로 만든다 (vitest 가 최신 여부를 검사).
"""

import json
from pathlib import Path

import pytest
from helpers import collect

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "patterns.json").read_text(encoding="utf-8"))
PATTERNS = FIXTURE["patterns"]
CASES = PATTERNS + FIXTURE.get("cases", [])  # 패턴 외에 실행까지 검증할 그래프 (예: 승인 미들웨어 Agent)


def test_fixture_has_all_patterns():
    assert len(PATTERNS) >= 12
    assert all(p["analysis"]["errors"] == 0 for p in PATTERNS)


@pytest.mark.parametrize("pattern", CASES, ids=[p["id"] for p in CASES])
async def test_generated_project_runs(pattern):
    r = await collect(pattern["files"], "main.py", timeout=60)
    assert r["exit"]["code"] == 0, f"{pattern['id']} 실패\n{r['stderr'][-3000:]}"
    assert r["exit"]["timed_out"] is False

    # 최상위 그래프에서 실행된 노드는 모두 캔버스에 정의된 노드다
    # (create_agent 같은 서브그래프 안쪽 노드는 그 노드의 자식으로 따로 잡힌다)
    starts = [e for e in r["trace"] if e["ev"] == "start"]
    roots = {e["id"] for e in starts if e["parent"] is None}
    top = {e["name"] for e in starts if e["kind"] == "node" and e["parent"] in roots}
    defined = {n["name"] for n in pattern["nodes"]}
    assert top, "노드 실행 트레이스가 없습니다"
    assert top <= defined, top - defined


async def test_hitl_middleware_actually_interrupts_and_resumes():
    """승인 미들웨어가 issue_refund 실행 전에 멈추고, decisions 로 재개되어 끝까지 도는지 (조용히 건너뛰면 실패)."""
    case = next(c for c in CASES if c["id"] == "hitl-middleware")
    r = await collect(case["files"], "main.py", timeout=60)
    assert r["exit"]["code"] == 0, r["stderr"][-3000:]
    assert "'action_requests'" in r["stdout"] and "issue_refund" in r["stdout"]
    assert "Command(resume=...) 로 재개" in r["stdout"]
