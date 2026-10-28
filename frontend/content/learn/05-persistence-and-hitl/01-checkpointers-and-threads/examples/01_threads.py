"""예제 1: InMemorySaver + thread_id로 대화를 기억하고, 스레드끼리 분리하기.

- 체크포인터를 붙여 컴파일하면 같은 thread_id의 호출은 이전 상태에서 이어집니다.
- 다른 thread_id는 완전히 독립된 대화입니다.
"""

import os

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def chat(state: MessagesState) -> dict:
    """지금까지의 모든 메시지를 모델에 보내고 답을 상태에 추가한다."""
    reply = llm.invoke(state["messages"])
    return {"messages": [reply]}  # add_messages 리듀서가 기존 목록 뒤에 붙인다


builder = StateGraph(MessagesState)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)

# ① 체크포인터는 앱 전체에서 하나만 만들고 compile 할 때 붙인다
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)


def talk(thread_id: str, text: str) -> None:
    """특정 스레드에 사용자 메시지를 보내고 결과를 요약 출력한다."""
    config = {"configurable": {"thread_id": thread_id}}  # ② 스레드 지정
    result = graph.invoke({"messages": [{"role": "user", "content": text}]}, config)
    last = result["messages"][-1]
    print(f"[{thread_id}] 사용자: {text}")
    print(f"[{thread_id}] AI    : {last.content[:70]}")
    print(f"[{thread_id}] 누적 메시지 수 = {len(result['messages'])}")
    print("-" * 60)


print("=" * 60)
print("민수 스레드에 두 번, 지영 스레드에 한 번 말을 겁니다")
print("=" * 60)
talk("minsu", "안녕, 내 이름은 민수야")
talk("minsu", "내 이름이 뭐였지?")  # 이전 2개 메시지 + 새 질문이 모델에 전달됨
talk("jiyoung", "안녕, 나는 지영이야")  # 빈 상태에서 시작

# ③ 저장된 최신 상태 직접 꺼내 보기
minsu_state = graph.get_state({"configurable": {"thread_id": "minsu"}})
jiyoung_state = graph.get_state({"configurable": {"thread_id": "jiyoung"}})

print("민수 스레드의 대화 기록:")
for m in minsu_state.values["messages"]:
    print(f"  - {m.type:>5}: {m.content[:50]}")

assert len(minsu_state.values["messages"]) == 4  # human, ai, human, ai
assert len(jiyoung_state.values["messages"]) == 2  # human, ai
print("\n✔ 스레드마다 대화가 독립적으로 저장되었습니다.")
