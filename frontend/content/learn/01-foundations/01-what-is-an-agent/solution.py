"""실습: 에이전트 루프 완성하기 (정답)

목표: "커피 3잔은 얼마야?" 라는 목표를 받아
  1) lookup_price 도구로 커피 1잔 가격을 조회하고
  2) multiply 도구로 3잔 가격을 계산한 뒤
  3) 최종 답변을 내는 에이전트 루프를 완성한다.

요구사항 (run_agent 함수)
- policy(memory) 가 돌려주는 결정(decision)에 따라 행동한다.
    {"type": "tool", "tool": 이름, "args": {...}}  → TOOLS[이름](**args) 실행
    {"type": "finish", "answer": "..."}           → 루프 종료
- 도구 결과(dict)는 memory 에 합친다(memory.update).
- 매 단계를 trace 리스트에 기록한다: {"step": n, "tool": 이름 또는 "finish"}
- max_steps 번 안에 끝나지 않으면 stopped_reason="max_steps" 로 멈춘다.
- 반환값: {"answer": str, "steps": int, "trace": list, "stopped_reason": "finish" | "max_steps"}
"""

from __future__ import annotations

from typing import Any, Callable

PRICES = {"커피": 4500, "케이크": 6000}


def lookup_price(item: str) -> dict[str, Any]:
    """상품 1개 가격 조회 도구."""
    return {"price": PRICES[item]}


def multiply(a: float, b: float) -> dict[str, Any]:
    """곱셈 도구."""
    return {"total": a * b}


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {"lookup_price": lookup_price, "multiply": multiply}


def coffee_policy(memory: dict[str, Any]) -> dict[str, Any]:
    """정상 정책(두뇌). 메모리를 보고 다음 행동 하나를 고른다."""
    if "price" not in memory:
        return {"type": "tool", "tool": "lookup_price", "args": {"item": "커피"}}
    if "total" not in memory:
        return {"type": "tool", "tool": "multiply", "args": {"a": memory["price"], "b": 3}}
    return {"type": "finish", "answer": f"커피 3잔은 {int(memory['total'])}원입니다."}


def looping_policy(memory: dict[str, Any]) -> dict[str, Any]:
    """고장 난 정책: 끝내지 않고 가격 조회만 반복한다."""
    return {"type": "tool", "tool": "lookup_price", "args": {"item": "커피"}}


def run_agent(goal: str, policy: Callable[[dict], dict], max_steps: int = 5) -> dict[str, Any]:
    memory: dict[str, Any] = {"goal": goal}
    trace: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        decision = policy(memory)  # Reason

        if decision["type"] == "finish":  # 종료 조건
            trace.append({"step": step, "tool": "finish"})
            return {"answer": decision["answer"], "steps": step, "trace": trace, "stopped_reason": "finish"}

        observation = TOOLS[decision["tool"]](**decision["args"])  # Act
        memory.update(observation)  # Perceive
        trace.append({"step": step, "tool": decision["tool"]})
        print(f"[step {step}] {decision['tool']}({decision['args']}) → {observation}")

    # 반복 상한 도달
    return {"answer": "중단되었습니다.", "steps": max_steps, "trace": trace, "stopped_reason": "max_steps"}


if __name__ == "__main__":
    result = run_agent("커피 3잔은 얼마야?", coffee_policy)
    print("결과:", result)

    # --- 자가 채점 ---
    assert result["stopped_reason"] == "finish", "정상 정책은 finish 로 끝나야 합니다"
    assert result["steps"] == 3, "조회 → 계산 → 완료, 총 3단계여야 합니다"
    assert "13500" in result["answer"], "커피 3잔 = 13500원"
    assert [t["tool"] for t in result["trace"]] == ["lookup_price", "multiply", "finish"]

    broken = run_agent("커피 3잔은 얼마야?", looping_policy, max_steps=4)
    print("고장 난 정책 결과:", broken["stopped_reason"], broken["steps"])
    assert broken["stopped_reason"] == "max_steps", "무한 루프는 max_steps 에서 멈춰야 합니다"
    assert broken["steps"] == 4 and len(broken["trace"]) == 4

    print("✅ 모든 테스트 통과!")
