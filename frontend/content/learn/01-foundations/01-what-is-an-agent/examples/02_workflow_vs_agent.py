"""워크플로(개발자가 경로 고정) vs 에이전트(정책이 경로 결정) 비교.

같은 도구 세트로 두 방식을 구현하고, 처리 가능 범위와 단계 수를 비교한다.
"""

from __future__ import annotations

from typing import Any

# 도구: 간단한 가짜 데이터
WEATHER = {"서울": 80, "부산": 10}  # 강수확률(%)
FX = {"USD": 1380.0}


def tool_weather(city: str) -> int:
    return WEATHER.get(city, 50)


def tool_fx(currency: str) -> float:
    return FX[currency]


def tool_multiply(a: float, b: float) -> float:
    return a * b


# ---------------------------------------------------------------------------
# 방식 A: 워크플로 — 순서가 코드에 하드코딩되어 있다.
# ---------------------------------------------------------------------------
def umbrella_workflow(question: str) -> tuple[str, int]:
    """'날씨 조회 → 판단' 고정 2단계. 질문 종류와 상관없이 같은 길을 간다."""
    steps = 0
    city = "부산" if "부산" in question else "서울"
    prob = tool_weather(city)  # 1단계 (무조건)
    steps += 1
    answer = f"{city} 강수확률 {prob}% → 우산 {'필요' if prob >= 50 else '불필요'}"  # 2단계
    steps += 1
    return answer, steps


# ---------------------------------------------------------------------------
# 방식 B: 에이전트 — 매 단계 정책이 상황을 보고 다음 행동을 고른다.
# ---------------------------------------------------------------------------
def policy(question: str, memory: dict[str, Any]) -> dict[str, Any]:
    if "우산" in question:
        if "prob" not in memory:
            return {"tool": "weather", "args": {"city": "부산" if "부산" in question else "서울"}}
        return {"finish": f"강수확률 {memory['prob']}% → 우산 {'필요' if memory['prob'] >= 50 else '불필요'}"}
    if "달러" in question:
        if "rate" not in memory:
            return {"tool": "fx", "args": {"currency": "USD"}}
        if "won" not in memory:
            return {"tool": "multiply", "args": {"a": 100, "b": memory["rate"]}}
        return {"finish": f"100달러 ≈ {memory['won']:,.0f}원"}
    return {"finish": "지원하지 않는 요청입니다."}


def agent(question: str, max_steps: int = 5) -> tuple[str, int]:
    memory: dict[str, Any] = {}
    out_key = {"weather": "prob", "fx": "rate", "multiply": "won"}  # 관찰을 어느 칸에 기록할지
    tools = {"weather": tool_weather, "fx": tool_fx, "multiply": tool_multiply}
    for step in range(1, max_steps + 1):
        d = policy(question, memory)
        if "finish" in d:
            return d["finish"], step
        memory[out_key[d["tool"]]] = tools[d["tool"]](**d["args"])
    return "중단(max_steps)", max_steps


if __name__ == "__main__":
    questions = ["부산 갈 때 우산 필요해?", "100달러는 원화로 얼마?"]
    print(f"{'질문':<22} | {'방식':<8} | {'단계':>4} | 결과")
    print("-" * 80)
    for q in questions:
        for label, fn in [("워크플로", umbrella_workflow), ("에이전트", agent)]:
            answer, steps = fn(q)
            print(f"{q:<20} | {label:<6} | {steps:>4} | {answer}")
    print("-" * 80)
    print("💡 워크플로는 '우산' 질문만 제대로 처리하지만 항상 2단계로 예측 가능합니다.")
    print("💡 에이전트는 두 질문 모두 처리하지만, 질문에 따라 단계 수(=비용)가 달라집니다.")
