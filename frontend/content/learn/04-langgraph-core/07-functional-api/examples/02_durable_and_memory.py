"""4.7 예제 2 — 체크포인터와 함께: 실패 후 재개 + previous 로 대화 기억.

1) 성공한 task 결과는 저장되어, 재개(invoke(None, 같은 thread))할 때 다시 실행되지 않는다.
2) previous / entrypoint.final 로 스레드 단위 대화 기록을 이어 가는 LLM 챗봇.
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

# ---------------------------------------------------------------- 1) 내구성 있는 실행
calls = {"load_order": 0, "charge_payment": 0, "send_email": 0}


@task
def load_order(order_id: int) -> dict:
    calls["load_order"] += 1
    return {"id": order_id, "amount": 39_000}


@task
def charge_payment(order: dict) -> str:
    calls["charge_payment"] += 1
    if calls["charge_payment"] == 1:
        raise ConnectionError("결제 게이트웨이 일시 장애")  # 첫 시도는 실패
    return f"receipt-{order['id']}"


@task
def send_email(receipt: str) -> str:
    calls["send_email"] += 1
    return f"{receipt} 메일 발송 완료"


@entrypoint(checkpointer=InMemorySaver())
def order_pipeline(order_id: int) -> str:
    # 부수 효과(결제, 메일)는 모두 task 안에 있다 → 재개해도 중복 실행되지 않는다
    order = load_order(order_id).result()
    receipt = charge_payment(order).result()
    return send_email(receipt).result()


config = {"configurable": {"thread_id": "order-1001"}}
print("=" * 60)
print("① 1차 실행")
try:
    order_pipeline.invoke(1001, config)
except ConnectionError as e:
    print("  실패:", e, "| 호출 횟수:", calls)

print("② 재개: invoke(None, 같은 thread_id)")
print("  결과:", order_pipeline.invoke(None, config))
print("  호출 횟수:", calls)
assert calls["load_order"] == 1, "성공했던 load_order 는 재실행되지 않아야 한다"


# ---------------------------------------------------------------- 2) previous 로 대화 기억
MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@task
def call_llm(messages: list[AnyMessage]) -> AIMessage:
    """LLM 호출(비결정적 + 비용)은 반드시 task 안에서"""
    return llm.invoke([SystemMessage("너는 짧게 답하는 비서다."), *messages])


@entrypoint(checkpointer=InMemorySaver())
def chatbot(user_text: str, *, previous: list[AnyMessage] | None = None):
    history = [*(previous or []), HumanMessage(user_text)]
    reply = call_llm(history).result()
    saved = [*history, reply]
    # 호출자에게는 답변(+기록 길이)만, 다음 실행(previous)에는 전체 기록을 저장
    return entrypoint.final(value={"reply": reply.content, "history_len": len(saved)}, save=saved)


print("=" * 60)
print("③ previous + entrypoint.final 챗봇")
chat_cfg = {"configurable": {"thread_id": "chat-1"}}
for text in ["내 이름은 랭그래프야", "내 이름이 뭐라고 했지?"]:
    print(f"  👤 {text}")
    out = chatbot.invoke(text, chat_cfg)
    print(f"  🤖 {out['reply'][:80]}")
    print(f"     (저장된 대화 기록: 메시지 {out['history_len']}개 → 다음 턴의 previous)")

saved = chatbot.get_state(chat_cfg).values  # 체크포인트에 저장된 값 = 마지막 반환값(value)
print("  get_state().values:", str(saved)[:60], "...")

other = {"configurable": {"thread_id": "chat-2"}}
print("  다른 스레드(chat-2)는 기억을 공유하지 않는다 → 기록 길이", chatbot.invoke("안녕", other)["history_len"])
