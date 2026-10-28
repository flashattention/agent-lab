"""4.4 예제 1 — Command: 노드 안에서 '업데이트 + 이동'을 한 번에.

결제 심사 노드가 판단 결과를 상태에 기록하면서 동시에 다음 노드를 고른다.
마지막에는 Command 와 정적 엣지를 함께 쓸 때의 함정도 확인한다.
"""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class PaymentState(TypedDict, total=False):
    amount: int
    risk_score: float
    decision: str
    reason: str
    trail: Annotated[list[str], operator.add]  # 어떤 노드를 거쳤는지 기록


# 반환 타입 Command[Literal[...]] 이 '가능한 목적지'를 LangGraph 에 알려 준다 → 그림에 점선 표시
def review_payment(state: PaymentState) -> Command[Literal["approve", "manual_review", "reject"]]:
    amount, risk = state["amount"], state["risk_score"]
    if risk > 0.8:
        return Command(update={"decision": "reject", "reason": "고위험 거래", "trail": ["review"]}, goto="reject")
    if amount > 1_000_000:
        return Command(update={"decision": "hold", "reason": "고액 거래", "trail": ["review"]}, goto="manual_review")
    return Command(update={"decision": "approve", "reason": "정상", "trail": ["review"]}, goto="approve")


def approve(state: PaymentState) -> dict:
    return {"trail": ["approve: 결제 완료"]}


def manual_review(state: PaymentState) -> dict:
    return {"trail": ["manual_review: 담당자 검토 대기열 등록"]}


def reject(state: PaymentState) -> dict:
    return {"trail": ["reject: 거절 안내 발송"]}


builder = StateGraph(PaymentState)
builder.add_node(review_payment)  # 나가는 add_edge / add_conditional_edges 가 없다!
builder.add_node(approve)
builder.add_node(manual_review)
builder.add_node(reject)
builder.add_edge(START, "review_payment")
for n in ("approve", "manual_review", "reject"):
    builder.add_edge(n, END)
graph = builder.compile()

print(graph.get_graph().draw_mermaid())

cases = [
    {"amount": 35_000, "risk_score": 0.1},
    {"amount": 2_500_000, "risk_score": 0.2},
    {"amount": 9_900, "risk_score": 0.95},
]
for case in cases:
    out = graph.invoke(case)
    print(f"{case} → {out['decision']:<8} ({out['reason']})  경로: {out['trail']}")


# ------------------------------------------------------------- 함정: Command + 정적 엣지
def router(state: PaymentState) -> Command[Literal["approve"]]:
    return Command(goto="approve", update={"trail": ["router"]})


def audit(state: PaymentState) -> dict:
    return {"trail": ["audit"]}


b = StateGraph(PaymentState)
b.add_node(router)
b.add_node(approve)
b.add_node(audit)
b.add_edge(START, "router")
b.add_edge("router", "audit")  # 정적 엣지가 '추가로' 걸려 있다
print("\n[함정] Command(goto='approve') + add_edge('router', 'audit')")
print("  → 실행된 노드:", b.compile().invoke({"trail": []})["trail"])
print("  goto 는 정적 엣지를 대체하지 않고 '추가'된다. 두 경로가 모두 실행됨!")
