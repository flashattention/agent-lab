"""[실습] 궤적 평가자 + 대본 모델 테스트 + 미니 evaluate() 만들기 — 정답

과제
1. trajectory_match(actual, expected, mode) 를 완성하라.
   - "strict": 순서·개수 완전 일치 / "unordered": 순서 무관 multiset 일치
   - "subset": 실제 ⊆ 기대 / "superset": 실제 ⊇ 기대
2. extract_trajectory(messages) 를 완성하라. AIMessage 의 tool_calls 이름을 순서대로 모은다.
3. evaluate(dataset, target_fn, evaluators) 를 완성하라.
   각 예제에 target_fn(inputs) 를 실행하고, 모든 평가자 결과의 score 를 key 별로 평균 내어
   {"key": 평균} dict 를 반환한다.
"""

from __future__ import annotations

from collections.abc import Callable
from statistics import mean
from typing import Any

from langchain.agents import create_agent
from langchain.messages import AIMessage, AnyMessage, HumanMessage
from langchain.tools import tool
from testing_utils import ScriptedChatModel, tool_call


# ------------------------------------------------------------------ TODO 1
def trajectory_match(actual: list[str], expected: list[str], mode: str) -> bool:
    if mode == "strict":
        return actual == expected
    if mode == "unordered":
        return sorted(actual) == sorted(expected)
    if mode == "subset":
        return set(actual) <= set(expected)
    if mode == "superset":
        return set(actual) >= set(expected)
    raise ValueError(f"알 수 없는 mode: {mode}")


# ------------------------------------------------------------------ TODO 2
def extract_trajectory(messages: list[AnyMessage]) -> list[str]:
    return [tc["name"] for m in messages if isinstance(m, AIMessage) for tc in m.tool_calls]


# ------------------------------------------------------------------ TODO 3
def evaluate(
    dataset: list[dict[str, Any]],
    target_fn: Callable[[dict], dict],
    evaluators: list[Callable[[dict, dict], dict]],
) -> dict[str, float]:
    scores: dict[str, list[float]] = {}
    for ex in dataset:
        outputs = target_fn(ex["inputs"])
        for ev in evaluators:
            r = ev(outputs, ex["reference"])
            scores.setdefault(r["key"], []).append(float(r["score"]))
    return {k: mean(v) for k, v in scores.items()}


# ================================================================== 자가 채점
# (1) 궤적 매칭 진리표
A, B, C = "lookup_order", "search_policy", "refund"
assert trajectory_match([A, B], [A, B], "strict")
assert not trajectory_match([B, A], [A, B], "strict")
assert trajectory_match([B, A], [A, B], "unordered")
assert not trajectory_match([A, A], [A], "unordered")
assert trajectory_match([A], [A, B], "subset")
assert not trajectory_match([A, C], [A, B], "subset")
assert trajectory_match([A, B, C], [A, B], "superset")
assert not trajectory_match([A], [A, B], "superset")
print("1) trajectory_match 진리표 통과")


# (2) 대본 모델로 에이전트 궤적 테스트
@tool
def lookup_order(order_id: str) -> str:
    """주문 상태 조회"""
    return "배송 중"


@tool
def search_policy(query: str) -> str:
    """정책 검색"""
    return "30일 이내 환불"


scripted = ScriptedChatModel(responses=[
    AIMessage(content="", tool_calls=[
        {"name": "lookup_order", "args": {"order_id": "A-1"}, "id": "c1"},
        {"name": "search_policy", "args": {"query": "환불"}, "id": "c2"},
    ]),
    AIMessage("A-1은 배송 중이며, 30일 이내 환불 가능합니다."),
])
agent = create_agent(scripted, tools=[lookup_order, search_policy])
res = agent.invoke({"messages": [HumanMessage("A-1 상태랑 환불 규정")]})
traj = extract_trajectory(res["messages"])
print("2) 에이전트 궤적:", traj)
assert trajectory_match(traj, ["search_policy", "lookup_order"], "unordered")
assert len(scripted.calls) == 2


# (3) 미니 evaluate()
def fake_target(inputs: dict) -> dict:
    """결정적 타깃: 질문에 'order' 가 있으면 lookup_order 를 쓴 것으로 친다."""
    model = ScriptedChatModel(responses=[
        tool_call("lookup_order", {"order_id": "X"}) if "order" in inputs["q"] else AIMessage("안녕하세요!"),
        AIMessage("완료"),
    ])
    out = create_agent(model, tools=[lookup_order]).invoke({"messages": [HumanMessage(inputs["q"])]})
    return {"trajectory": extract_trajectory(out["messages"])}


def traj_eval(outputs: dict, reference: dict) -> dict:
    return {"key": "trajectory", "score": trajectory_match(outputs["trajectory"], reference["tools"], "strict")}


def no_extra_tools(outputs: dict, reference: dict) -> dict:
    return {"key": "no_extra_tools", "score": trajectory_match(outputs["trajectory"], reference["tools"], "subset")}


DATASET = [
    {"inputs": {"q": "order A-1?"}, "reference": {"tools": ["lookup_order"]}},
    {"inputs": {"q": "안녕"}, "reference": {"tools": []}},
    {"inputs": {"q": "order 와 정책"}, "reference": {"tools": ["lookup_order", "search_policy"]}},
]
summary = evaluate(DATASET, fake_target, [traj_eval, no_extra_tools])
print("3) 실험 요약:", summary)
assert set(summary) == {"trajectory", "no_extra_tools"}
assert abs(summary["trajectory"] - 2 / 3) < 1e-9, "세 번째 예제는 search_policy 를 안 불렀으므로 strict 실패"
assert summary["no_extra_tools"] == 1.0
print("✅ 모든 테스트 통과!")
