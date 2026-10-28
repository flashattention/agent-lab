"""4.3 예제 1 — 결정적(규칙 기반) 라우터.

classify 노드가 분류 결과를 '기록'하고, route 함수가 그 값을 '읽어' 다음 노드를 고른다.
path_map 덕분에 Mermaid 그림에 세 갈래 분기가 정확히 그려진다.
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

Category = Literal["refund", "tech", "general"]


class TicketState(TypedDict, total=False):
    text: str
    category: Category
    reply: str


KEYWORDS: dict[str, tuple[str, ...]] = {
    "refund": ("환불", "취소", "반품"),
    "tech": ("오류", "에러", "로그인", "버그"),
}


def classify(state: TicketState) -> dict:
    """규칙으로 문의를 분류해 category 를 상태에 기록한다 (노드: 쓰기 담당)."""
    for category, words in KEYWORDS.items():
        if any(w in state["text"] for w in words):
            return {"category": category}
    return {"category": "general"}


def route(state: TicketState) -> Category:
    """기록된 category 를 읽어 경로 키를 반환한다 (라우터: 읽기 전용)."""
    return state["category"]


def handle_refund(state: TicketState) -> dict:
    return {"reply": "환불 담당: 주문번호를 알려주시면 바로 처리해 드릴게요."}


def handle_tech(state: TicketState) -> dict:
    return {"reply": "기술 지원: 사용 중인 브라우저와 오류 화면을 보내주세요."}


def handle_general(state: TicketState) -> dict:
    return {"reply": "상담원: 문의 주셔서 감사합니다. 곧 연락드릴게요."}


builder = StateGraph(TicketState)
builder.add_node(classify)
builder.add_node(handle_refund)
builder.add_node(handle_tech)
builder.add_node(handle_general)

builder.add_edge(START, "classify")
builder.add_conditional_edges(
    "classify",
    route,
    # path_map: 라우터 반환값 → 실제 노드 이름. 라우터는 노드 이름을 몰라도 된다.
    {"refund": "handle_refund", "tech": "handle_tech", "general": "handle_general"},
)
for node in ("handle_refund", "handle_tech", "handle_general"):
    builder.add_edge(node, END)  # 모든 경로가 END 에 도달하는지 그림으로 확인하자

graph = builder.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())

    tickets = [
        "어제 주문한 신발 환불하고 싶어요",
        "로그인하면 500 에러가 나요",
        "매장 영업시간이 궁금합니다",
    ]
    for text in tickets:
        path = [next(iter(c)) for c in graph.stream({"text": text}, stream_mode="updates")]
        result = graph.invoke({"text": text})
        print(f"\n문의 : {text}")
        print(f"경로 : {' → '.join(path)}")
        print(f"답변 : {result['reply']}")

    # 라우터는 순수 함수라 단위 테스트가 쉽다
    assert route({"category": "tech"}) == "tech"
    print("\n라우터 단위 테스트 통과 ✔")
