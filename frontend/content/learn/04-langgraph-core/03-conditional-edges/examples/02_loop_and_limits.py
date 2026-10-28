"""4.3 예제 2 — 루프와 종료 조건: 카운터(소프트) / recursion_limit(하드) / RemainingSteps.

LLM 없이 '초안 작성 → 검토 → 미달이면 재작성' 루프를 흉내 낸다.
"""

from typing import Literal, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.managed import RemainingSteps

MAX_ATTEMPTS = 3  # 비즈니스 상한: 설정값으로 관리하는 것이 좋다


class DraftState(TypedDict, total=False):
    topic: str
    draft: str
    score: int
    attempts: int


def write(state: DraftState) -> dict:
    n = state.get("attempts", 0) + 1
    return {"draft": f"{state['topic']} 초안 v{n}", "attempts": n}


def make_review(points_per_attempt: int):
    """시도할수록 점수가 오르는 가짜 평가자를 만든다."""

    def review(state: DraftState) -> dict:
        return {"score": 50 + points_per_attempt * state["attempts"]}

    return review


def should_continue(state: DraftState) -> Literal["write", "__end__"]:
    if state["score"] >= 80:
        return END  # 합격
    if state["attempts"] >= MAX_ATTEMPTS:
        return END  # 상한 도달 → 우아하게 종료
    return "write"


def build(points_per_attempt: int, with_counter: bool = True):
    b = StateGraph(DraftState)
    b.add_node(write)
    b.add_node("review", make_review(points_per_attempt))
    b.add_edge(START, "write")
    b.add_edge("write", "review")
    if with_counter:
        b.add_conditional_edges("review", should_continue)
    else:
        # 카운터 없는 위험한 루프: 점수만 본다
        b.add_conditional_edges("review", lambda s: END if s["score"] >= 80 else "write", ["write", END])
    return b.compile()


print("=" * 60)
print("① 점수가 빨리 오르는 경우 → 합격으로 종료")
print(build(points_per_attempt=15).invoke({"topic": "리듀서"}))

print("=" * 60)
print("② 점수가 거의 안 오르는 경우 → 카운터 상한으로 우아하게 종료")
result = build(points_per_attempt=1).invoke({"topic": "리듀서"})
print(result, "| 상한 도달:", result["attempts"] >= MAX_ATTEMPTS)

print("=" * 60)
print("③ 카운터 없는 루프 + recursion_limit=8 → GraphRecursionError")
try:
    build(points_per_attempt=1, with_counter=False).invoke({"topic": "리듀서"}, {"recursion_limit": 8})
except GraphRecursionError as e:
    print("GraphRecursionError:", str(e).splitlines()[0])


# ------------------------------------------------------------- ④ RemainingSteps
class LoopState(TypedDict, total=False):
    count: int
    status: str
    remaining_steps: RemainingSteps  # 런타임이 자동으로 채워 주는 '남은 스텝 수'


def work(state: LoopState) -> dict:
    print(f"   work: count={state.get('count', 0)}, remaining_steps={state['remaining_steps']}")
    return {"count": state.get("count", 0) + 1}


def wrap_up(state: LoopState) -> dict:
    return {"status": f"한도 직전에 정리 종료 (count={state['count']})"}


def route_work(state: LoopState) -> Literal["work", "wrap_up"]:
    # 한도에 거의 다다르면 예외 대신 정리 노드로 보낸다
    return "wrap_up" if state["remaining_steps"] <= 2 else "work"


b = StateGraph(LoopState)
b.add_node(work)
b.add_node(wrap_up)
b.add_edge(START, "work")
b.add_conditional_edges("work", route_work)
b.add_edge("wrap_up", END)

print("=" * 60)
print("④ RemainingSteps 로 스스로 멈추는 루프 (recursion_limit=6)")
print(b.compile().invoke({"count": 0}, {"recursion_limit": 6}))
