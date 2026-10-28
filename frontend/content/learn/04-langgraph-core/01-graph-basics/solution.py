"""4.1 실습 — 주문 처리 파이프라인 그래프 만들기 (정답)

과제
----
온라인 쇼핑몰의 주문 금액을 계산하는 그래프를 만듭니다.

    START → calc_subtotal → apply_discount → add_shipping → END

1. calc_subtotal : items(가격, 수량 목록)로 소계(subtotal)를 계산한다.
2. apply_discount: 소계가 50,000원 이상이면 10% 할인 금액(discount)을, 아니면 0을 기록한다.
3. add_shipping  : (소계 - 할인)이 30,000원 이상이면 배송비 0원, 아니면 3,000원.
                   최종 금액 total = 소계 - 할인 + 배송비.
4. 각 노드는 "바뀐 키만" 반환해야 한다 (상태 전체를 반환하지 말 것).
5. 그래프를 compile 하고 graph 변수에 담는다.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class OrderState(TypedDict, total=False):
    items: list[tuple[int, int]]  # (단가, 수량) 목록
    subtotal: int
    discount: int
    shipping: int
    total: int


def calc_subtotal(state: OrderState) -> dict:
    subtotal = sum(price * qty for price, qty in state["items"])
    return {"subtotal": subtotal}


def apply_discount(state: OrderState) -> dict:
    subtotal = state["subtotal"]
    discount = int(subtotal * 0.1) if subtotal >= 50_000 else 0
    return {"discount": discount}


def add_shipping(state: OrderState) -> dict:
    after_discount = state["subtotal"] - state["discount"]
    shipping = 0 if after_discount >= 30_000 else 3_000
    return {"shipping": shipping, "total": after_discount + shipping}


builder = StateGraph(OrderState)
builder.add_node(calc_subtotal)
builder.add_node(apply_discount)
builder.add_node(add_shipping)
builder.add_edge(START, "calc_subtotal")
builder.add_edge("calc_subtotal", "apply_discount")
builder.add_edge("apply_discount", "add_shipping")
builder.add_edge("add_shipping", END)
graph = builder.compile()


# ----------------------------------------------------------------- 자가 채점
assert graph is not None, "graph 를 compile 해서 담으세요"
nodes = set(graph.get_graph().nodes)
assert {"calc_subtotal", "apply_discount", "add_shipping"} <= nodes, f"노드가 부족합니다: {nodes}"

# 노드는 바뀐 키만 반환해야 한다
assert calc_subtotal({"items": [(1000, 2)]}) == {"subtotal": 2000}
assert set(apply_discount({"subtotal": 60_000})) == {"discount"}

big = graph.invoke({"items": [(25_000, 2), (10_000, 1)]})  # 60,000원
assert big["subtotal"] == 60_000 and big["discount"] == 6_000
assert big["shipping"] == 0 and big["total"] == 54_000

small = graph.invoke({"items": [(8_000, 2)]})  # 16,000원
assert small["discount"] == 0 and small["shipping"] == 3_000 and small["total"] == 19_000

# 실행 순서 확인
order = [next(iter(c)) for c in graph.stream({"items": [(1000, 1)]}, stream_mode="updates")]
assert order == ["calc_subtotal", "apply_discount", "add_shipping"], order

print(graph.get_graph().draw_mermaid())
print("큰 주문:", big)
print("작은 주문:", small)
print("✅ 모든 테스트 통과!")
