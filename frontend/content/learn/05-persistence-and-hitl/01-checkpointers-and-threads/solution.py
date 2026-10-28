"""실습: 주문 카운터 그래프에 영속성 붙이기

여러분은 장바구니 담기 요청을 처리하는 아주 작은 그래프를 만듭니다.
- 상태 `items`는 담긴 상품 목록이고, 리듀서로 '이어 붙이기'가 되어야 합니다.
- `add_item` 노드는 요청된 상품(`request`)을 `items`에 추가합니다.

할 일
1. TODO 1: `items` 필드에 operator.add 리듀서를 붙이세요.
2. TODO 2: InMemorySaver 체크포인터를 붙여 그래프를 컴파일하세요.
3. TODO 3: thread_id가 "alice"인 config를 만드세요.
4. TODO 4: get_state로 alice의 최신 상태를 가져오세요.
5. TODO 5: get_state_history로 alice의 전체 체크포인트 이력을 리스트로 만드세요.

맨 아래 assert가 모두 통과하면 성공입니다.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class CartState(TypedDict):
    request: str
    # TODO 1: 리스트가 덮어써지지 않고 이어 붙도록 리듀서를 지정하세요.
    items: Annotated[list[str], operator.add]


def add_item(state: CartState) -> dict:
    """요청된 상품 하나를 장바구니에 추가한다."""
    return {"items": [state["request"]]}


builder = StateGraph(CartState)
builder.add_node("add_item", add_item)
builder.add_edge(START, "add_item")
builder.add_edge("add_item", END)

# TODO 2: 체크포인터를 붙여 컴파일하세요.
graph = builder.compile(checkpointer=InMemorySaver())

# TODO 3: alice 스레드용 config
alice = {"configurable": {"thread_id": "alice"}}
bob = {"configurable": {"thread_id": "bob"}}

graph.invoke({"request": "사과", "items": []}, alice)
graph.invoke({"request": "바나나", "items": []}, alice)
graph.invoke({"request": "우유", "items": []}, bob)

# TODO 4: alice의 최신 상태 스냅샷
alice_snapshot = graph.get_state(alice)

# TODO 5: alice의 체크포인트 이력 (최신 → 과거)
alice_history = list(graph.get_state_history(alice))

print("alice items:", alice_snapshot.values["items"])
print("bob items  :", graph.get_state(bob).values["items"])
print("alice 체크포인트 수:", len(alice_history))

# ---- 자가 채점 ----
assert alice_snapshot is not None, "TODO 4를 채우세요"
assert alice_snapshot.values["items"] == ["사과", "바나나"], "같은 스레드의 상태가 누적되어야 합니다"
assert graph.get_state(bob).values["items"] == ["우유"], "스레드는 서로 독립이어야 합니다"
assert alice_snapshot.next == (), "실행이 끝난 스레드는 next가 비어 있어야 합니다"
assert len(alice_history) == 6, "턴마다 3개(input, 시작, add_item) × 2턴 = 6개 체크포인트"
assert alice_history[0].metadata["step"] > alice_history[-1].metadata["step"], "이력은 최신이 먼저입니다"
print("✅ 모든 테스트 통과!")
