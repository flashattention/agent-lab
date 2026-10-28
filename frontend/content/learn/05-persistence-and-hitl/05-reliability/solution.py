"""실습: 장애에 강한 '유료 번역 작업' 그래프

그래프: translate → charge → notify
- translate: 번역 API가 처음 두 번은 ConnectionError로 실패한다 → 재시도로 성공시키세요.
- charge   : 요금을 청구한다. 첫 실행에서 청구 직후 서버가 죽는다 → 재개해도 이중 청구가 없어야 합니다.
- notify   : 알림 서비스가 완전히 죽어 있다 → 재시도 후에도 실패하면 fallback으로 status를 남기세요.

할 일
1. TODO 1: ConnectionError만 재시도하는 RetryPolicy를 만드세요. (max_attempts=3, initial_interval=0.01)
2. TODO 2: notify 실패 시 호출될 error_handler를 완성하세요. {"status": "notify_failed"}를 반환합니다.
3. TODO 3: 재실행해도 같은 값이 나오는 결정적 멱등성 키를 만드세요. 형식: "job:<job_id>:charge"
4. TODO 4: 크래시 후 같은 thread에서 실행을 재개하세요.
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy


class NotifyServiceDown(Exception):
    pass


class JobState(TypedDict, total=False):
    job_id: str
    text: str
    translated: str
    status: str


CALLS = {"translate": 0, "charge": 0, "notify": 0}
LEDGER: dict[str, int] = {}  # 결제사: 멱등성 키 → 금액
CRASH = {"armed": True}


def translate(state: JobState) -> dict:
    CALLS["translate"] += 1
    if CALLS["translate"] < 3:
        raise ConnectionError("번역 API 연결 실패")
    return {"translated": state["text"].upper()}


def idempotency_key(job_id: str) -> str:
    # TODO 3: 결정적 멱등성 키
    return f"job:{job_id}:charge"


def charge(state: JobState) -> dict:
    CALLS["charge"] += 1
    key = idempotency_key(state["job_id"])
    LEDGER.setdefault(key, 500)  # 같은 키는 한 번만 청구된다
    if CRASH["armed"]:
        CRASH["armed"] = False
        raise RuntimeError("청구 직후 서버 크래시")
    return {"status": "charged"}


def notify(state: JobState) -> dict:
    CALLS["notify"] += 1
    raise NotifyServiceDown("알림 서비스 503")


# TODO 1: ConnectionError만 재시도하는 정책
retry = RetryPolicy(max_attempts=3, initial_interval=0.01, retry_on=ConnectionError)


def notify_fallback(state: JobState, error: NodeError) -> dict:
    # TODO 2: 실패를 상태에 기록
    return {"status": "notify_failed"}


builder = StateGraph(JobState)
builder.add_node("translate", translate, retry_policy=retry)
builder.add_node("charge", charge)
builder.add_node(
    "notify",
    notify,
    retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.01, retry_on=NotifyServiceDown),
    error_handler=notify_fallback,
)
builder.add_edge(START, "translate")
builder.add_edge("translate", "charge")
builder.add_edge("charge", "notify")
builder.add_edge("notify", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "job-77"}}
try:
    graph.invoke({"job_id": "77", "text": "hello"}, config, durability="sync")
except RuntimeError as e:
    print("1차 실행 크래시:", e)

print("멈춘 지점:", graph.get_state(config).next)

# TODO 4: 같은 thread로 재개
final = graph.invoke(None, config)

print("최종 상태:", final)
print("호출 횟수:", CALLS)
print("청구 내역:", LEDGER)

# ---- 자가 채점 ----
assert idempotency_key("77") == idempotency_key("77") == "job:77:charge", "TODO 3: 키는 결정적이어야 합니다"
assert final["translated"] == "HELLO"
assert CALLS["translate"] == 3, "TODO 1: 번역은 재시도로 3번째에 성공해야 하고, 재개 시 다시 실행되면 안 됩니다"
assert CALLS["charge"] == 2, "charge는 크래시 후 재개 시 한 번 더 실행됩니다 (at-least-once)"
assert LEDGER == {"job:77:charge": 500}, "멱등성 키 덕분에 청구는 한 건이어야 합니다"
assert final["status"] == "notify_failed", "TODO 2: notify 실패가 fallback으로 기록되어야 합니다"
assert CALLS["notify"] == 2, "notify는 재시도 정책대로 2번 시도되어야 합니다"
print("✅ 모든 테스트 통과!")
