"""실습: 핸드오프 도구 팩토리 완성하기

`make_handoff_tool(agent_name)` 이 반환하는 도구는 호출되면
  Command(
      goto=agent_name,
      graph=Command.PARENT,
      update={"messages": [...현재 메시지..., ToolMessage], "active_agent": agent_name},
  )
를 반환해야 합니다.

체크 포인트
- ToolMessage 의 tool_call_id 는 runtime.tool_call_id 로 채운다 (빠지면 OpenAI 가 오류를 낸다)
- messages 에는 runtime.state["messages"] 전체 + ToolMessage 를 넣는다
  (자식 그래프 안에서 생긴 tool_call AI 메시지를 부모에 전달하기 위해)

자가 채점
- 접수(front_desk)가 결제(billing)로 넘겼고, active_agent 가 billing 인가
- 최종 답변은 billing 이 했는가
- 두 번째 턴은 front_desk 를 거치지 않고 billing 이 바로 받았는가
"""

import os
from typing import NotRequired

from langchain.agents import create_agent
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


class State(MessagesState):
    active_agent: NotRequired[str]


def make_handoff_tool(agent_name: str, description: str):
    @tool(f"transfer_to_{agent_name}", description=description)
    def handoff(runtime: ToolRuntime) -> Command:
        tool_msg = ToolMessage(
            content=f"{agent_name} 에게 넘겼습니다.",
            name=f"transfer_to_{agent_name}",
            tool_call_id=runtime.tool_call_id,
        )
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={"messages": [*runtime.state["messages"], tool_msg], "active_agent": agent_name},
        )

    return handoff


@tool
def lookup_invoice(invoice_id: str) -> str:
    """invoice 청구서를 조회한다."""
    return f"청구서 {invoice_id}: 29,000원 결제 완료"


front_desk = create_agent(
    MODEL,
    tools=[make_handoff_tool("billing", "billing 결제·환불 요청을 결제 담당에게 넘긴다.")],
    system_prompt="당신은 접수 담당입니다. 결제 문의는 billing 에게 넘기세요.",
    name="front_desk",
)
billing = create_agent(
    MODEL,
    tools=[lookup_invoice, make_handoff_tool("front_desk", "결제와 무관한 요청을 접수 담당에게 되돌린다.")],
    system_prompt="당신은 결제 담당입니다.",
    name="billing",
)

builder = StateGraph(State)
builder.add_node("front_desk", front_desk, destinations=("billing",))
builder.add_node("billing", billing, destinations=("front_desk",))
builder.add_conditional_edges(START, lambda s: s.get("active_agent", "front_desk"), ["front_desk", "billing"])
graph = builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "t1"}, "recursion_limit": 15}
    out = graph.invoke({"messages": [HumanMessage("billing 결제 문의가 있어요")]}, config)
    for m in out["messages"]:
        m.pretty_print()

    tool_names = [m.name for m in out["messages"] if isinstance(m, ToolMessage)]
    assert "transfer_to_billing" in tool_names, "transfer_to_billing 핸드오프가 일어나지 않았습니다."
    assert out.get("active_agent") == "billing", f"active_agent 가 billing 이어야 합니다: {out.get('active_agent')}"
    assert isinstance(out["messages"][-1], AIMessage) and out["messages"][-1].name == "billing"

    n = len(out["messages"])
    out2 = graph.invoke({"messages": [HumanMessage("invoice INV-7 내역을 보여줘")]}, config)
    speakers = [m.name for m in out2["messages"][n:] if isinstance(m, AIMessage)]
    print("두 번째 턴 발화자:", speakers)
    assert speakers and speakers[0] == "billing", "두 번째 턴은 billing 이 바로 받아야 합니다."
    assert "front_desk" not in speakers
    print("✅ 모든 테스트 통과!")
