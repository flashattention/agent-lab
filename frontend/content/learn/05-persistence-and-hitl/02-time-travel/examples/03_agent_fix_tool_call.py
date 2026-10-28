"""예제 3: create_agent 에이전트에서 잘못된 도구 호출을 고쳐 포크하기.

1) 에이전트가 주문 조회 도구를 호출한다 (Mock 모드에서는 인자가 엉터리로 채워진다).
2) 'tools 노드 실행 직전' 체크포인트로 돌아가, AIMessage의 tool_calls 인자를 고친다.
   - 같은 id의 메시지를 넘기면 add_messages 리듀서가 '추가'가 아니라 '교체'한다.
3) 고친 지점부터 다시 실행하면 올바른 인자로 도구가 실행된다.
"""

import os

from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

ORDERS = {"A-1234": "배송 중 (내일 도착 예정)"}


@tool
def lookup_order(order_id: str) -> str:
    """주문 번호(order_id)로 배송 상태를 조회한다."""
    return ORDERS.get(order_id, f"주문 {order_id!r}을(를) 찾을 수 없습니다")


agent = create_agent(MODEL, tools=[lookup_order], checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "support-9"}}

result = agent.invoke({"messages": [{"role": "user", "content": "제 주문 배송 상태 조회해 주세요"}]}, config)
print("=" * 64)
print("원래 실행")
print("=" * 64)
for m in result["messages"]:
    m.pretty_print()

# 'tools' 노드 실행 직전 체크포인트 = 모델이 tool_call을 만든 직후
snap = next(s for s in agent.get_state_history(config) if s.next == ("tools",))
bad_msg = snap.values["messages"][-1]
print("\n잘못된 tool_call 인자:", bad_msg.tool_calls[0]["args"])

# 같은 id를 유지한 채 tool_calls만 교체한 새 AIMessage
fixed_call = {**bad_msg.tool_calls[0], "args": {"order_id": "A-1234"}}
fixed_msg = bad_msg.model_copy(update={"tool_calls": [fixed_call]})
fork_config = agent.update_state(snap.config, {"messages": [fixed_msg]})

forked = agent.invoke(None, fork_config)
print("\n" + "=" * 64)
print("포크한 실행 (고친 인자로 tools부터 다시)")
print("=" * 64)
for m in forked["messages"][-2:]:
    m.pretty_print()

tool_msgs = [m for m in forked["messages"] if m.type == "tool"]
assert "배송 중" in tool_msgs[-1].content, "고친 인자로 도구가 실행되어야 한다"
ai_with_calls = [m for m in forked["messages"] if m.type == "ai" and m.tool_calls]
assert len(ai_with_calls) == 1, "같은 id로 넘겼으므로 메시지가 추가되지 않고 교체되어야 한다"
print("\n✔ 도구 호출 메시지가 교체되었고, 올바른 주문이 조회되었습니다.")
