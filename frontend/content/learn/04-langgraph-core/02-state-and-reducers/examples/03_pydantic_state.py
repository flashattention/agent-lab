"""4.2 예제 3 — TypedDict vs dataclass vs Pydantic 상태.

같은 '티켓 분류' 그래프를 세 방식으로 선언하고, Pydantic 이 입력을 검증하는 모습을 본다.
"""

import operator
from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from langgraph.graph import START, StateGraph
from pydantic import BaseModel, Field, ValidationError


# ---------------------------------------------------------------- TypedDict
class TicketTD(TypedDict, total=False):
    title: str
    priority: int
    tags: Annotated[list[str], operator.add]


def tag_td(state: TicketTD) -> dict:
    # TypedDict 상태는 dict 처럼 state["key"] 로 접근
    return {"tags": ["urgent"] if state["priority"] <= 2 else ["normal"]}


# ---------------------------------------------------------------- dataclass
@dataclass
class TicketDC:
    title: str
    priority: int = 3  # 기본값 지원
    tags: Annotated[list[str], operator.add] = field(default_factory=list)


def tag_dc(state: TicketDC) -> dict:
    # dataclass / Pydantic 상태는 속성으로 접근. 반환은 여전히 dict!
    return {"tags": ["urgent"] if state.priority <= 2 else ["normal"]}


# ---------------------------------------------------------------- Pydantic
class TicketPD(BaseModel):
    title: str = Field(min_length=1)
    priority: int = Field(default=3, ge=1, le=5)  # 1~5 범위 검증
    tags: Annotated[list[str], operator.add] = []


def tag_pd(state: TicketPD) -> dict:
    return {"tags": ["urgent"] if state.priority <= 2 else ["normal"]}


def make_graph(schema, node):
    b = StateGraph(schema)
    b.add_node("tag", node)
    b.add_edge(START, "tag")
    return b.compile()


if __name__ == "__main__":
    td = make_graph(TicketTD, tag_td).invoke({"title": "로그인 불가", "priority": 1})
    dc = make_graph(TicketDC, tag_dc).invoke({"title": "로그인 불가"})  # priority 기본값 3
    pd_graph = make_graph(TicketPD, tag_pd)
    pd = pd_graph.invoke({"title": "로그인 불가", "priority": "2"})  # "2" → 2 로 변환

    print("TypedDict :", td)
    print("dataclass :", dc)
    print("Pydantic  :", pd, "| 반환 타입:", type(pd).__name__)  # dict 로 돌아온다
    # 눈여겨볼 점 ①: 반환 dict 의 priority 는 입력한 문자열 '2' 그대로다.
    #   검증·변환된 모델 객체는 '노드에 전달될 때' 만들어지고, 채널에는 원래 입력값이 저장된다.
    # 눈여겨볼 점 ②: dataclass 결과에는 priority 가 없다. 기본값은 노드가 받는 객체에만 채워진다.
    print("다시 모델로:", TicketPD(**pd))

    print("\n── Pydantic 은 잘못된 입력을 첫 노드 실행 전에 막는다")
    for bad in ({"title": "결제 오류", "priority": 9}, {"title": "", "priority": 1}):
        try:
            pd_graph.invoke(bad)
        except ValidationError as e:
            err = e.errors()[0]
            print(f"  입력 {bad} → ValidationError: {err['loc']} {err['msg']}")

    print("\n── TypedDict 는 검증하지 않는다 (같은 잘못된 입력이 그대로 통과)")
    print("  ", make_graph(TicketTD, tag_td).invoke({"title": "결제 오류", "priority": 9}))
