"""4.2 예제 2 — 입력/출력 스키마와 private state.

그래프를 '함수'처럼 설계한다: 매개변수(input_schema)와 반환값(output_schema)만 공개하고
중간 계산 값(private state)은 숨긴다.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class InputState(TypedDict):
    """외부에서 넣을 수 있는 키"""

    question: str


class OutputState(TypedDict):
    """외부로 돌려줄 키"""

    answer: str


class OverallState(InputState, OutputState):
    """그래프 내부 전체 상태 (입력 + 출력 + 내부 메모)"""

    notes: list[str]


class PrivateState(TypedDict):
    """노드 사이에서만 오가는 값. OverallState 에 없어도 채널로 등록된다."""

    search_query: str
    raw_hits: list[str]


FAKE_INDEX = {
    "langgraph": ["LangGraph 는 상태 기반 그래프 프레임워크다", "LangGraph v1 은 2025년에 출시되었다"],
    "reducer": ["리듀서는 (기존값, 새값) → 합친값 함수다"],
}


def rewrite(state: InputState) -> PrivateState:
    """질문을 검색어로 바꾼다. 첫 매개변수 타입(InputState)이 이 노드가 읽는 스키마다."""
    keyword = next((k for k in FAKE_INDEX if k in state["question"].lower()), "langgraph")
    return {"search_query": keyword}


def search(state: PrivateState) -> PrivateState:
    return {"raw_hits": FAKE_INDEX.get(state["search_query"], [])}


def answer(state: PrivateState) -> dict:
    # 반환 dict 의 answer 는 OverallState(OutputState) 의 키, notes 는 내부 전용 키
    return {
        "answer": " / ".join(state["raw_hits"]) or "관련 정보를 찾지 못했습니다.",
        "notes": [f"query={state['search_query']}", f"hits={len(state['raw_hits'])}"],
    }


builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_node(rewrite)
builder.add_node(search)
builder.add_node(answer)
builder.add_edge(START, "rewrite")
builder.add_edge("rewrite", "search")
builder.add_edge("search", "answer")
builder.add_edge("answer", END)
graph = builder.compile()

if __name__ == "__main__":
    print("── 그래프 내부에서는 어떤 키가 오가나? (stream updates)")
    for chunk in graph.stream({"question": "Reducer 가 뭐야?"}, stream_mode="updates"):
        print("  ", chunk)

    result = graph.invoke({"question": "Reducer 가 뭐야?"})
    print("\n── invoke 결과 (output_schema 로 제한됨)")
    print("  ", result)
    assert set(result) == {"answer"}, "출력에는 answer 만 있어야 한다"

    print("\n── 입력/출력 JSON 스키마 (API 문서로 쓸 수 있다)")
    print("  input :", graph.get_input_jsonschema()["properties"].keys())
    print("  output:", graph.get_output_jsonschema()["properties"].keys())
