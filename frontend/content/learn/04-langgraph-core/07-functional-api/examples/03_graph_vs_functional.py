"""4.7 예제 3 — 같은 문제, 두 가지 API.

'초안 작성 → 평가 → 기준 미달이면 재작성(최대 3회)' 루프를
Graph API 와 Functional API 로 각각 구현해 비교한다. (LLM 없이 결정적으로)
"""

from typing import Literal, TypedDict

from langgraph.func import entrypoint, task
from langgraph.graph import END, START, StateGraph

MAX_ATTEMPTS = 3
PASS_SCORE = 80


def fake_score(draft: str) -> int:
    """버전이 올라갈수록 점수가 오르는 가짜 평가자"""
    version = int(draft.rsplit("v", 1)[1])
    return 55 + 12 * version


# ================================================================ Graph API
class DraftState(TypedDict, total=False):
    topic: str
    draft: str
    score: int
    attempts: int


def write(state: DraftState) -> dict:
    n = state.get("attempts", 0) + 1
    return {"draft": f"{state['topic']} 초안 v{n}", "attempts": n}


def review(state: DraftState) -> dict:
    return {"score": fake_score(state["draft"])}


def should_continue(state: DraftState) -> Literal["write", "__end__"]:
    if state["score"] >= PASS_SCORE or state["attempts"] >= MAX_ATTEMPTS:
        return END
    return "write"


builder = StateGraph(DraftState)
builder.add_node(write)
builder.add_node(review)
builder.add_edge(START, "write")
builder.add_edge("write", "review")
builder.add_conditional_edges("review", should_continue)
graph_app = builder.compile()


# ================================================================ Functional API
@task
def write_task(topic: str, version: int) -> str:
    return f"{topic} 초안 v{version}"


@task
def review_task(draft: str) -> int:
    return fake_score(draft)


@entrypoint()
def functional_app(inputs: dict) -> dict:
    # 평범한 for 루프 + if 문. 상태 스키마도 라우팅 함수도 없다.
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = write_task(inputs["topic"], attempt).result()
        score = review_task(draft).result()
        if score >= PASS_SCORE:
            break
    return {"topic": inputs["topic"], "draft": draft, "score": score, "attempts": attempt}


if __name__ == "__main__":
    print("── Graph API 구조 (흐름이 그림으로 보인다)")
    print(graph_app.get_graph().draw_mermaid())
    print("── Functional API 구조 (entrypoint 하나로만 보인다)")
    print(functional_app.get_graph().draw_mermaid())

    g = graph_app.invoke({"topic": "LangGraph"})
    f = functional_app.invoke({"topic": "LangGraph"})
    print("Graph API      :", g)
    print("Functional API :", f)
    assert g == f, "두 구현의 결과가 같아야 한다"

    print("\n── 실행 이벤트 비교 (updates)")
    print("Graph     :", [next(iter(c)) for c in graph_app.stream({"topic": "LangGraph"}, stream_mode="updates")])
    print("Functional:", [next(iter(c)) for c in functional_app.stream({"topic": "LangGraph"}, stream_mode="updates")])
