"""4.6 예제 1 — 공유 상태 서브그래프.

검색(retrieval) 서브그래프를 컴파일해 부모 그래프에 노드로 그대로 추가한다.
- xray=True 로 서브그래프 내부까지 그림으로 보기
- stream(subgraphs=True) 로 네임스페이스별 이벤트 보기
- 누적 리듀서 키를 공유할 때 생기는 '중복' 함정과 해결법
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

FAKE_INDEX = {
    "langgraph": ["LangGraph는 상태 기반 그래프 프레임워크", "LangGraph는 체크포인트를 지원"],
    "subgraph": ["서브그래프는 컴파일된 그래프를 노드로 쓴다"],
}


# ---------------------------------------------------------------- 부모 상태
class ParentState(TypedDict, total=False):
    question: str
    docs: Annotated[list[str], operator.add]  # 누적 리듀서
    answer: str


# ---------------------------------------------------------------- 서브그래프
class RetrievalInput(TypedDict):
    """서브그래프 입력: docs 를 '받지 않는다' → 서브그래프는 빈 docs 로 시작"""

    question: str


class RetrievalState(TypedDict, total=False):
    question: str  # 부모와 공유
    docs: Annotated[list[str], operator.add]  # 부모와 공유 (출력)
    expanded_queries: list[str]  # 서브그래프 내부 전용


def expand_query(state: RetrievalState) -> dict:
    words = [w.lower().strip("?") for w in state["question"].split()]
    return {"expanded_queries": [w for w in words if w in FAKE_INDEX] or ["langgraph"]}


def search(state: RetrievalState) -> dict:
    found = [doc for q in state["expanded_queries"] for doc in FAKE_INDEX[q]]
    return {"docs": found}


def build_retrieval(isolated: bool):
    """isolated=True 면 input_schema 로 docs 를 받지 않아 '새 문서만' 돌려준다."""
    kwargs = {"input_schema": RetrievalInput} if isolated else {}
    b = StateGraph(RetrievalState, **kwargs)
    b.add_node(expand_query)
    b.add_node(search)
    b.add_edge(START, "expand_query")
    b.add_edge("expand_query", "search")
    b.add_edge("search", END)
    return b.compile()


# ---------------------------------------------------------------- 부모 그래프
def remember(state: ParentState) -> dict:
    """이전 대화에서 이미 확보한 문서가 있다고 가정"""
    return {"docs": ["(이전) 사용자는 초보자다"]}


def answer(state: ParentState) -> dict:
    return {"answer": f"문서 {len(state['docs'])}개를 근거로 답변: " + " / ".join(state["docs"])}


def build_parent(isolated: bool):
    p = StateGraph(ParentState)
    p.add_node(remember)
    p.add_node("retrieve", build_retrieval(isolated))  # ← 컴파일된 그래프를 노드로!
    p.add_node(answer)
    p.add_edge(START, "remember")
    p.add_edge("remember", "retrieve")
    p.add_edge("retrieve", "answer")
    p.add_edge("answer", END)
    return p.compile()


if __name__ == "__main__":
    graph = build_parent(isolated=True)
    print("── xray=True: 서브그래프 내부까지 펼친 구조")
    print(graph.get_graph(xray=True).draw_mermaid())

    q = {"question": "subgraph 가 뭐야?"}
    print("── stream(subgraphs=True): (namespace, 업데이트)")
    for namespace, chunk in graph.stream(q, stream_mode="updates", subgraphs=True):
        where = "부모" if not namespace else f"서브그래프 {namespace[0].split(':')[0]}"
        print(f"  [{where:<16}] {chunk}")

    print("\n── 누적 리듀서 키 공유 함정 비교")
    naive = build_parent(isolated=False).invoke(q)
    safe = build_parent(isolated=True).invoke(q)
    print("  input_schema 없음 :", naive["docs"])  # '(이전)' 문서가 중복된다!
    print("  input_schema 사용 :", safe["docs"])
    assert naive["docs"].count("(이전) 사용자는 초보자다") == 2
    assert safe["docs"].count("(이전) 사용자는 초보자다") == 1
