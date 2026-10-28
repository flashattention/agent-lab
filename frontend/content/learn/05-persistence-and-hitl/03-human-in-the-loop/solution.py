"""실습: 고액 환불은 매니저 승인을 받는 환불 그래프

규칙
- 10,000원 이하 환불은 자동 처리(refund)
- 그보다 크면 approval 노드에서 interrupt로 멈추고 매니저의 결정을 기다린다
  - {"action": "approve"}                → 그대로 환불
  - {"action": "edit", "amount": 정수}   → 금액을 고쳐서 환불
  - {"action": "reject", "reason": 문자열} → deny로 이동 (환불하지 않음)

할 일
1. TODO 1: approval 노드에서 interrupt()로 매니저에게 승인 요청(dict)을 보내고 결정을 받으세요.
2. TODO 2: 결정에 따라 Command(goto=..., update=...)를 반환하세요.
3. TODO 3: interrupt를 쓰려면 무엇이 필요할까요? 그래프를 올바르게 컴파일하세요.
4. TODO 4: 멈춘 스레드를 매니저의 결정으로 재개하는 함수를 완성하세요.
"""

from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

AUTO_LIMIT = 10_000
REFUNDS: list[tuple[str, int]] = []  # 실제로 처리된 환불 (부수효과 기록)


class RefundState(TypedDict, total=False):
    customer: str
    amount: int
    status: str


def check(state: RefundState) -> Command[Literal["refund", "approval"]]:
    """금액에 따라 자동 처리 또는 승인 대기로 보낸다."""
    if state["amount"] <= AUTO_LIMIT:
        return Command(goto="refund")
    return Command(goto="approval")


def approval(state: RefundState) -> Command[Literal["refund", "deny"]]:
    """매니저 승인을 받는다. (부수효과 없음! 재개 시 처음부터 다시 실행되므로)"""
    # TODO 1: 매니저에게 승인 요청을 보내고 결정을 받으세요.
    decision = interrupt({"customer": state["customer"], "amount": state["amount"]})

    # TODO 2: 결정에 따라 분기하세요.
    if decision["action"] == "approve":
        return Command(goto="refund")
    if decision["action"] == "edit":
        return Command(update={"amount": decision["amount"]}, goto="refund")
    return Command(update={"status": f"거절: {decision.get('reason', '')}"}, goto="deny")


def refund(state: RefundState) -> dict:
    REFUNDS.append((state["customer"], state["amount"]))
    return {"status": f"환불 완료 {state['amount']}원"}


def deny(state: RefundState) -> dict:
    return {}


builder = StateGraph(RefundState)
builder.add_node("check", check)
builder.add_node("approval", approval)
builder.add_node("refund", refund)
builder.add_node("deny", deny)
builder.add_edge(START, "check")
builder.add_edge("refund", END)
builder.add_edge("deny", END)

# TODO 3: interrupt가 동작하도록 컴파일하세요.
graph = builder.compile(checkpointer=InMemorySaver())


def start(thread_id: str, customer: str, amount: int):
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke({"customer": customer, "amount": amount}, config, version="v2")


def resume(thread_id: str, decision: dict):
    """TODO 4: 멈춘 스레드를 매니저의 결정(decision)으로 재개하세요."""
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(Command(resume=decision), config, version="v2")


# 1) 소액: 멈추지 않고 바로 환불
small = start("r-small", "가영", 5_000)
assert not small.interrupts, "소액은 승인 없이 처리되어야 합니다"
print("소액:", small.value["status"])

# 2) 고액 승인
big = start("r-approve", "나래", 50_000)
assert big.interrupts, "고액은 approval에서 멈춰야 합니다"
assert big.interrupts[0].value["amount"] == 50_000, "승인 요청에 금액이 들어 있어야 합니다"
print("승인 요청:", big.interrupts[0].value)
done = resume("r-approve", {"action": "approve"})
print("승인 후:", done.value["status"])

# 3) 고액 편집 (금액 조정)
start("r-edit", "다솜", 80_000)
edited = resume("r-edit", {"action": "edit", "amount": 30_000})
print("편집 후:", edited.value["status"])

# 4) 고액 거절
start("r-reject", "라희", 99_000)
rejected = resume("r-reject", {"action": "reject", "reason": "중복 요청"})
print("거절 후:", rejected.value["status"])

# ---- 자가 채점 ----
assert REFUNDS == [("가영", 5_000), ("나래", 50_000), ("다솜", 30_000)], f"환불 기록이 다릅니다: {REFUNDS}"
assert rejected.value["status"].startswith("거절"), "거절 사유가 status에 기록되어야 합니다"
assert graph.get_state({"configurable": {"thread_id": "r-reject"}}).next == (), "거절 후 실행이 끝나야 합니다"
print("✅ 모든 테스트 통과!")
