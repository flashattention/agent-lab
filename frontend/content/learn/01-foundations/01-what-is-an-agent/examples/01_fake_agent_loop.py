"""규칙 기반 '가짜 에이전트 루프'.

LLM 없이 if문으로 만든 정책(policy)을 두뇌로 사용해
Perceive → Reason → Act 루프의 뼈대만 순수하게 관찰한다.
"""

from __future__ import annotations

from typing import Any, Callable

# ---------------------------------------------------------------------------
# 1) 도구(Tools): 에이전트가 바깥세상과 상호작용하는 수단
#    실제로는 API 호출, DB 조회 등이 들어간다. 여기서는 가짜 데이터를 돌려준다.
# ---------------------------------------------------------------------------
FAKE_WEATHER = {"서울": {"rain_prob": 80, "temp": 17}, "부산": {"rain_prob": 10, "temp": 22}}
FAKE_FX = {"USD": 1380.0, "JPY": 9.2}


def get_weather(city: str) -> dict[str, Any]:
    """도시의 날씨를 조회한다. 결과는 '관찰(observation)'로 메모리에 합쳐진다."""
    data = FAKE_WEATHER.get(city, {"rain_prob": 50, "temp": 20})
    return {"weather": {"city": city, **data}}


def get_exchange_rate(currency: str) -> dict[str, Any]:
    """1 단위 외화의 원화 환율을 조회한다."""
    return {"rate": FAKE_FX[currency]}


def multiply(a: float, b: float) -> dict[str, Any]:
    """곱셈 계산기."""
    return {"product": a * b}


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
    "multiply": multiply,
}


# ---------------------------------------------------------------------------
# 2) 정책(Policy) = 두뇌. 실제 에이전트에서는 이 자리에 LLM이 들어간다.
#    입력: 지금까지의 메모리(목표 + 관찰)  /  출력: 다음 행동 하나
# ---------------------------------------------------------------------------
def rule_based_policy(memory: dict[str, Any]) -> dict[str, Any]:
    goal: str = memory["goal"]

    if "우산" in goal:
        city = "부산" if "부산" in goal else "서울"
        if "weather" not in memory:  # 아직 날씨를 모른다 → 도구 호출
            return {"type": "tool", "tool": "get_weather", "args": {"city": city}}
        w = memory["weather"]
        need = "챙기세요" if w["rain_prob"] >= 50 else "필요 없어요"
        return {"type": "finish", "answer": f"{w['city']} 강수확률 {w['rain_prob']}% → 우산 {need}."}

    if "달러" in goal:
        if "rate" not in memory:  # 1단계: 환율 조회
            return {"type": "tool", "tool": "get_exchange_rate", "args": {"currency": "USD"}}
        if "product" not in memory:  # 2단계: 앞 단계의 관찰을 이용해 계산
            return {"type": "tool", "tool": "multiply", "args": {"a": 50, "b": memory["rate"]}}
        return {"type": "finish", "answer": f"50달러는 약 {memory['product']:,.0f}원입니다."}

    return {"type": "finish", "answer": "제가 도울 수 있는 일이 아니에요."}


def broken_policy(memory: dict[str, Any]) -> dict[str, Any]:
    """버그 있는 정책: 종료를 모르고 같은 도구만 계속 부른다 (LLM도 실제로 이런 실수를 한다)."""
    return {"type": "tool", "tool": "get_weather", "args": {"city": "서울"}}


# ---------------------------------------------------------------------------
# 3) 에이전트 루프 = 실행기 + 종료 조건 + 반복 상한
# ---------------------------------------------------------------------------
def run_agent(goal: str, policy=rule_based_policy, max_steps: int = 6) -> str:
    memory: dict[str, Any] = {"goal": goal}  # 상태(State)
    print(f"\n🎯 목표: {goal}")
    for step in range(1, max_steps + 1):  # 반복 상한: 무한 루프 방지
        decision = policy(memory)  # Reason
        if decision["type"] == "finish":  # 종료 조건
            print(f"  [step {step}] ✅ 완료")
            return decision["answer"]
        name, args = decision["tool"], decision["args"]
        observation = TOOLS[name](**args)  # Act
        memory.update(observation)  # Perceive (관찰을 상태에 반영)
        print(f"  [step {step}] 🔧 {name}({args}) → {observation}")
    print(f"  ⛔ max_steps={max_steps} 도달, 강제 종료")
    return "최대 반복 횟수에 도달해 중단했습니다."


if __name__ == "__main__":
    print("=" * 60)
    print("같은 루프, 다른 목표 → 다른 경로")
    print("=" * 60)
    for g in ["서울 가는데 우산 챙겨야 할까?", "50달러는 원화로 얼마야?", "피자 주문해줘"]:
        print("  💬", run_agent(g))

    print("\n" + "=" * 60)
    print("고장 난 정책 + 반복 상한 → 안전하게 멈춤")
    print("=" * 60)
    print("  💬", run_agent("우산?", policy=broken_policy, max_steps=3))
