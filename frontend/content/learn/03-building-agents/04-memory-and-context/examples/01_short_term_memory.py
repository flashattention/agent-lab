"""단기 메모리: checkpointer + thread_id.

- 같은 thread_id  → 이전 대화가 복원되어 이어진다
- 다른 thread_id  → 완전히 분리된 새 대화
- get_state()     → 저장된 상태를 꺼내 본다
"""

import os

from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def save_preference(topic: str) -> str:
    """사용자가 좋아하는 주제(topic)를 기록합니다."""
    return f"선호 주제 기록 완료: {topic[:30]}"


def ask(agent, thread_id: str, text: str) -> dict:
    """특정 스레드에 메시지를 보내고 결과를 출력한다."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config)
    print(f"  [{thread_id}] 사용자: {text}")
    print(f"  [{thread_id}] 에이전트: {str(result['messages'][-1].content)[:70]}")
    print(f"  [{thread_id}] 누적 메시지 수: {len(result['messages'])}")
    return result


def main() -> None:
    checkpointer = InMemorySaver()  # 학습용. 프로덕션은 SqliteSaver/PostgresSaver (→ 5.1)
    agent = create_agent(
        MODEL,
        tools=[save_preference],
        system_prompt="너는 사용자의 취향을 기억하는 비서다.",
        checkpointer=checkpointer,
    )

    print("=" * 60)
    print("1) 같은 스레드에서 두 번 대화")
    print("=" * 60)
    ask(agent, "minji:chat-1", "내 이름은 민지야. 나는 등산을 좋아해")
    second = ask(agent, "minji:chat-1", "내 이름이 뭐였지?")
    humans = [m.content for m in second["messages"] if m.type == "human"]
    print("  → 모델이 본 사용자 메시지들:", humans)

    print("\n" + "=" * 60)
    print("2) 다른 스레드는 격리된다")
    print("=" * 60)
    other = ask(agent, "jun:chat-1", "내 이름이 뭐였지?")
    print("  → 이전 대화 흔적:", [m.content for m in other["messages"] if m.type == "human"])

    print("\n" + "=" * 60)
    print("3) get_state로 저장된 상태 조회")
    print("=" * 60)
    snapshot = agent.get_state({"configurable": {"thread_id": "minji:chat-1"}})
    print("  상태 키       :", list(snapshot.values.keys()))
    print("  저장된 메시지 :", len(snapshot.values["messages"]))
    for m in snapshot.values["messages"]:
        print(f"    - {m.type:<5} {str(m.content)[:50] or [c['name'] for c in m.tool_calls]}")


if __name__ == "__main__":
    main()
