"""예제 2: SqliteSaver로 '프로세스 재시작'을 견디고, 상태 이력을 조회하기.

1) 임시 SQLite 파일에 체크포인트를 저장하는 그래프로 대화를 한 번 한다.
2) 연결을 닫고 '새 연결 + 새 그래프 객체'를 만든다 (서버 재시작 흉내).
3) 같은 thread_id로 대화를 이어 가고, get_state / get_state_history를 살펴본다.
"""

import os
import sqlite3
import tempfile

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def chat(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


def build_graph(conn: sqlite3.Connection):
    """주어진 DB 연결로 체크포인터를 만들어 그래프를 컴파일한다."""
    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    # check_same_thread=False: LangGraph가 내부 스레드에서 DB에 접근할 수 있게 한다
    return builder.compile(checkpointer=SqliteSaver(conn))


db_path = os.path.join(tempfile.mkdtemp(), "checkpoints.sqlite")
config = {"configurable": {"thread_id": "order-support-1"}}

print("=" * 60)
print("1) 첫 번째 '서버 프로세스'")
print("=" * 60)
conn1 = sqlite3.connect(db_path, check_same_thread=False)
graph1 = build_graph(conn1)
graph1.invoke({"messages": [{"role": "user", "content": "주문 1234 배송 조회해 줘"}]}, config)
print("저장된 메시지 수:", len(graph1.get_state(config).values["messages"]))
conn1.close()  # 프로세스 종료를 흉내: 메모리의 그래프/연결은 사라진다
del graph1

print("\n" + "=" * 60)
print("2) 재시작된 '서버 프로세스' (새 연결, 새 그래프 객체)")
print("=" * 60)
conn2 = sqlite3.connect(db_path, check_same_thread=False)
graph2 = build_graph(conn2)
result = graph2.invoke({"messages": [{"role": "user", "content": "언제 도착해?"}]}, config)
print("이어진 대화의 메시지 수:", len(result["messages"]))  # 4 = 이전 2 + 새 2
assert len(result["messages"]) == 4

print("\n" + "=" * 60)
print("3) get_state: 최신 스냅샷")
print("=" * 60)
snap = graph2.get_state(config)
print("next        :", snap.next, "(비어 있으면 실행 완료)")
print("step/source :", snap.metadata["step"], "/", snap.metadata["source"])
print("checkpoint  :", snap.config["configurable"]["checkpoint_id"])
print("parent      :", snap.parent_config["configurable"]["checkpoint_id"])

print("\n" + "=" * 60)
print("4) get_state_history: 최신 → 과거 순서")
print("=" * 60)
history = list(graph2.get_state_history(config))
for s in history:
    cid = s.config["configurable"]["checkpoint_id"][-8:]  # 뒤 8자리만 표시
    print(
        f"step={s.metadata['step']:>2}  source={s.metadata['source']:<6} "
        f"next={str(s.next):<12} msgs={len(s.values.get('messages', []))}  id=…{cid}"
    )

# 턴 하나당 체크포인트 3개(input, 입력 반영 후, chat 실행 후) × 2턴
print(f"\n총 체크포인트 수: {len(history)}")
print("최근 2개만:", [s.metadata["step"] for s in graph2.get_state_history(config, limit=2)])
conn2.close()
