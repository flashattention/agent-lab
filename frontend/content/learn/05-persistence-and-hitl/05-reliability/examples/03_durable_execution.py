"""예제 3: Durable execution — 프로세스가 죽어도 마지막 체크포인트에서 이어 가기 + 멱등성.

시나리오: 주문 처리 그래프 reserve_stock → charge_card → send_receipt
1) charge_card 직후 '서버 크래시'가 일어난다 (결제는 이미 외부에서 처리됨!)
2) 재시작 후 같은 thread_id로 invoke(None, config) → 실패한 노드부터 재개
3) 재개 시 charge_card가 다시 실행되지만, 멱등성 키 덕분에 이중 결제가 일어나지 않는다
4) Functional API의 @task는 완료된 결과를 체크포인트에 저장해 재개 시 다시 실행하지 않는다
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

# ---------------------------------------------------------------- 가짜 외부 결제 시스템
PAYMENT_LEDGER: dict[str, int] = {}  # 멱등성 키 → 금액 (결제사 서버라고 생각)
CHARGE_REQUESTS = {"n": 0}


def payment_api_charge(idempotency_key: str, amount: int) -> str:
    """실제 결제사 API처럼 같은 멱등성 키의 요청은 한 번만 처리한다."""
    CHARGE_REQUESTS["n"] += 1
    if idempotency_key in PAYMENT_LEDGER:
        return f"이미 처리된 결제 (key=…{idempotency_key[-8:]})"
    PAYMENT_LEDGER[idempotency_key] = amount
    return f"{amount}원 결제 완료 (key=…{idempotency_key[-8:]})"


# ---------------------------------------------------------------- 그래프
class OrderState(TypedDict, total=False):
    order_id: str
    amount: int
    log: Annotated[list[str], operator.add]


CRASH = {"enabled": True}
RUNS = {"reserve_stock": 0, "charge_card": 0, "send_receipt": 0}


def reserve_stock(state: OrderState) -> dict:
    RUNS["reserve_stock"] += 1
    return {"log": ["재고 확보"]}


def charge_card(state: OrderState, runtime: Runtime) -> dict:
    RUNS["charge_card"] += 1
    # 멱등성 키: '이 주문의 결제'를 결정적으로 식별하는 값. 재시도/재개해도 같아야 한다.
    key = f"order:{state['order_id']}:charge"
    msg = payment_api_charge(key, state["amount"])
    print(f"  charge_card 실행 #{RUNS['charge_card']}: {msg}")
    if CRASH["enabled"]:
        CRASH["enabled"] = False
        raise RuntimeError("💥 결제 직후 서버 크래시 (OOM, 배포, 네트워크 단절 ...)")
    return {"log": [msg]}


def send_receipt(state: OrderState) -> dict:
    RUNS["send_receipt"] += 1
    return {"log": ["영수증 발송"]}


builder = StateGraph(OrderState)
builder.add_node("reserve_stock", reserve_stock)
builder.add_node("charge_card", charge_card)
builder.add_node("send_receipt", send_receipt)
builder.add_edge(START, "reserve_stock")
builder.add_edge("reserve_stock", "charge_card")
builder.add_edge("charge_card", "send_receipt")
builder.add_edge("send_receipt", END)
graph = builder.compile(checkpointer=InMemorySaver())  # 실서비스: PostgresSaver

config = {"configurable": {"thread_id": "order-A-1001"}}

print("=" * 64)
print("1) 첫 실행 → 크래시")
print("=" * 64)
try:
    graph.invoke({"order_id": "A-1001", "amount": 39000, "log": []}, config, durability="sync")
except RuntimeError as e:
    print("  예외:", e)

snap = graph.get_state(config)
print("  저장된 상태 log :", snap.values["log"])
print("  다음 실행할 노드:", snap.next)
print("  실패 기록      :", snap.tasks[0].name, "→", repr(snap.tasks[0].error))

print("\n" + "=" * 64)
print("2) 재시작 후 같은 thread로 재개: invoke(None, config)")
print("=" * 64)
final = graph.invoke(None, config)
print("  최종 log:", final["log"])
print("  노드 실행 횟수:", RUNS)
print("  결제 API 요청 수:", CHARGE_REQUESTS["n"], "/ 실제 결제 건수:", len(PAYMENT_LEDGER))

assert RUNS["reserve_stock"] == 1, "완료된 노드는 다시 실행되지 않는다"
assert RUNS["charge_card"] == 2, "실패한 노드는 처음부터 다시 실행된다"
assert len(PAYMENT_LEDGER) == 1, "멱등성 키 덕분에 이중 결제가 없다"

# ---------------------------------------------------------------- Functional API
print("\n" + "=" * 64)
print("3) Functional API: @task 결과는 체크포인트에 저장되어 재개 시 재사용된다")
print("=" * 64)
TASK_RUNS = {"translate": 0, "summarize": 0}
FAIL_ONCE = {"on": True}


@task
def translate(text: str) -> str:
    TASK_RUNS["translate"] += 1
    return text.upper()


@task
def summarize(text: str) -> str:
    TASK_RUNS["summarize"] += 1
    if FAIL_ONCE["on"]:
        FAIL_ONCE["on"] = False
        raise RuntimeError("요약 서버 일시 장애")
    return text[:10] + "..."


@entrypoint(checkpointer=InMemorySaver())
def pipeline(text: str) -> str:
    translated = translate(text).result()  # 완료되면 결과가 저장된다
    return summarize(translated).result()


cfg = {"configurable": {"thread_id": "doc-1"}}
try:
    pipeline.invoke("durable execution matters", cfg)
except RuntimeError as e:
    print("  1차 실행 실패:", e)
print("  재개 결과:", pipeline.invoke(None, cfg))
print("  task 실행 횟수:", TASK_RUNS)
assert TASK_RUNS["translate"] == 1, "성공한 task는 재개 시 다시 실행되지 않는다"
print("\n✔ durable execution + 멱등성 예제 완료")
