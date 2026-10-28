"""4.3 실습 — 이진 탐색으로 숫자 맞히기: 루프 + 종료 조건 (정답)

과제
----
1~100 사이의 비밀 숫자를 맞히는 그래프를 만듭니다.

    START → guess → check ─┬─(정답)────────────→ END
                 ▲         ├─(시도 소진)→ give_up → END
                 └─────────┘(그 외: 다시 guess)

1. guess  : low~high 의 중간값을 guess 에 기록하고 attempts 를 1 증가시킨다. (이미 구현됨)
2. check  : guess 와 secret 을 비교해 hint("correct" | "up" | "down")를 기록하고,
            up 이면 low = guess + 1, down 이면 high = guess - 1 로 범위를 좁힌다.
3. route  : hint 가 "correct" 면 "done", attempts >= max_attempts 면 "give_up", 아니면 "retry" 를 반환한다.
4. add_conditional_edges 의 path_map 으로 done→END, give_up→"give_up", retry→"guess" 를 연결한다.
5. 안전장치로 invoke 할 때 recursion_limit 을 25 로 준다. (실행 코드에 이미 있음)
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class GameState(TypedDict, total=False):
    secret: int
    low: int
    high: int
    guess: int
    hint: str
    attempts: int
    max_attempts: int
    result: str


def guess(state: GameState) -> dict:
    mid = (state["low"] + state["high"]) // 2
    return {"guess": mid, "attempts": state.get("attempts", 0) + 1}


def check(state: GameState) -> dict:
    g, secret = state["guess"], state["secret"]
    if g == secret:
        return {"hint": "correct", "result": f"{state['attempts']}번 만에 정답 {g}!"}
    if g < secret:
        return {"hint": "up", "low": g + 1}
    return {"hint": "down", "high": g - 1}


def route(state: GameState) -> Literal["done", "give_up", "retry"]:
    if state["hint"] == "correct":
        return "done"
    if state["attempts"] >= state["max_attempts"]:
        return "give_up"
    return "retry"


def give_up(state: GameState) -> dict:
    return {"result": f"{state['attempts']}번 시도 후 포기 (범위 {state['low']}~{state['high']})"}


builder = StateGraph(GameState)
builder.add_node(guess)
builder.add_node(check)
builder.add_node(give_up)
builder.add_edge(START, "guess")
builder.add_edge("guess", "check")
builder.add_conditional_edges("check", route, {"done": END, "give_up": "give_up", "retry": "guess"})
builder.add_edge("give_up", END)
graph = builder.compile()


def play(secret: int, max_attempts: int = 10) -> GameState:
    return graph.invoke(
        {"secret": secret, "low": 1, "high": 100, "max_attempts": max_attempts},
        {"recursion_limit": 25},  # 하드 상한
    )


# ----------------------------------------------------------------- 자가 채점
assert route({"hint": "correct", "attempts": 99, "max_attempts": 3}) == "done"
assert route({"hint": "up", "attempts": 3, "max_attempts": 3}) == "give_up", "시도 소진이면 give_up"
assert route({"hint": "down", "attempts": 1, "max_attempts": 3}) == "retry", "그 외에는 retry"
assert check({"guess": 30, "secret": 70, "attempts": 1}).get("low") == 31, "up 이면 low = guess + 1"

for secret in (1, 37, 50, 100):
    r = play(secret)
    assert r["hint"] == "correct" and r["guess"] == secret, r
    assert r["attempts"] <= 7, "이진 탐색이면 7번 이내에 맞혀야 합니다"
    print(f"secret={secret:>3} → {r['result']}")

r = play(secret=77, max_attempts=2)
assert r["attempts"] == 2 and r["result"].startswith("2번 시도 후 포기"), r
print("max_attempts=2 →", r["result"])

edges = graph.get_graph().draw_mermaid()
assert "give_up" in edges and "-.->" in edges, "조건부 엣지가 그림에 나타나야 합니다"
print("✅ 모든 테스트 통과!")
