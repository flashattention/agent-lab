"""4.2 예제 1 — 리듀서가 없을 때 vs 있을 때.

1) 리듀서 없는 키: 순차 실행이면 덮어쓰기, 병렬 실행이면 InvalidUpdateError
2) operator.add / add_messages / 커스텀 리듀서 / Overwrite 동작 비교
"""

import operator
from typing import Annotated, TypedDict

from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.types import Overwrite


def banner(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


# ---------------------------------------------------------------- 1) 리듀서 없음
class PlainState(TypedDict):
    logs: list[str]  # 리듀서 없음 → 덮어쓰기


def node_a(state) -> dict:
    return {"logs": ["A 실행"]}


def node_b(state) -> dict:
    return {"logs": ["B 실행"]}


def build(state_schema, parallel: bool):
    """A, B 를 순차(START→A→B) 또는 병렬(START→A, START→B)로 연결한 그래프."""
    b = StateGraph(state_schema)
    b.add_node("A", node_a)
    b.add_node("B", node_b)
    if parallel:
        b.add_edge(START, "A")
        b.add_edge(START, "B")
        b.add_edge(["A", "B"], END)
    else:
        b.add_edge(START, "A")
        b.add_edge("A", "B")
        b.add_edge("B", END)
    return b.compile()


banner("1) 리듀서 없는 키")
print("순차 실행:", build(PlainState, parallel=False).invoke({"logs": ["시작"]}))
try:
    build(PlainState, parallel=True).invoke({"logs": ["시작"]})
except InvalidUpdateError as e:
    print("병렬 실행: InvalidUpdateError →", str(e).splitlines()[0])


# ---------------------------------------------------------------- 2) operator.add
class AddState(TypedDict):
    logs: Annotated[list[str], operator.add]  # 리스트 이어 붙이기


banner("2) Annotated[list, operator.add]")
print("순차 실행:", build(AddState, parallel=False).invoke({"logs": ["시작"]}))
print("병렬 실행:", build(AddState, parallel=True).invoke({"logs": ["시작"]}))


# ---------------------------------------------------------------- 3) 커스텀 리듀서
def merge_docs(current: list[str], update: list[str]) -> list[str]:
    """중복 제거 + 최근 3개만 유지. 인자를 수정하지 않고 새 리스트를 반환한다."""
    merged = list(dict.fromkeys(current + update))
    return merged[-3:]


class DocState(TypedDict):
    docs: Annotated[list[str], merge_docs]


def search_web(state) -> dict:
    return {"docs": ["doc-1", "doc-2", "doc-3"]}


def search_db(state) -> dict:
    return {"docs": ["doc-2", "doc-4"]}  # doc-2 는 중복


b = StateGraph(DocState)
b.add_node(search_web)
b.add_node(search_db)
b.add_edge(START, "search_web")
b.add_edge(START, "search_db")
docs_graph = b.compile()

banner("3) 커스텀 리듀서 merge_docs (중복 제거 + 최근 3개)")
print(docs_graph.invoke({"docs": []}))
# 주의: 병렬 노드의 업데이트가 리듀서에 들어오는 순서는 '노드 실행 순서'가 아니다.
# '최근 3개'처럼 순서에 의존하는 리듀서는 결과가 직관과 다를 수 있다.
# → 가능하면 순서와 무관한(교환 법칙이 성립하는) 리듀서를 설계하자. 예: 정렬 후 자르기
print("직접 호출 (web→db 순서):", merge_docs(merge_docs([], ["doc-1", "doc-2", "doc-3"]), ["doc-2", "doc-4"]))


# ---------------------------------------------------------------- 4) add_messages
banner("4) add_messages: 추가 / 같은 id 교체 / RemoveMessage 삭제 / 튜플 변환")
history: list[AnyMessage] = [
    HumanMessage("안녕", id="h1"),
    AIMessage("반가워요! (초안)", id="a1"),
]
updated = add_messages(
    history,
    [
        AIMessage("반가워요! 무엇을 도와드릴까요?", id="a1"),  # 같은 id → 교체
        RemoveMessage(id="h1"),  # 삭제
        ("user", "날씨 알려줘"),  # 튜플 → HumanMessage 로 변환되어 추가
    ],
)
for m in updated:
    print(f"  {type(m).__name__:<13} id={m.id!s:<38} {m.content}")


# ---------------------------------------------------------------- 5) Overwrite
def reset_logs(state) -> dict:
    # 빈 리스트를 반환하면 '기존 + []' 라 변화가 없다. Overwrite 로 리듀서를 우회한다.
    return {"logs": Overwrite(["--- 초기화 ---"])}


b = StateGraph(AddState)
b.add_node("A", node_a)
b.add_node(reset_logs)
b.add_node("B", node_b)
b.add_edge(START, "A")
b.add_edge("A", "reset_logs")
b.add_edge("reset_logs", "B")
banner("5) Overwrite 로 리듀서 우회")
print(b.compile().invoke({"logs": ["시작"]}))
