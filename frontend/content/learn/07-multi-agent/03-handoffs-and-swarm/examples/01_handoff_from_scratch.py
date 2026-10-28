"""핸드오프(Handoff)를 처음부터 구현하기: Command(goto=..., graph=Command.PARENT)

구성
- 부모 그래프 노드 3개: triage(접수), billing(결제), tech(기술 지원). 각 노드는 create_agent 로 만든 에이전트다.
- 각 에이전트는 '핸드오프 도구'를 가진다. 도구가 Command(graph=Command.PARENT)를 반환하면
  에이전트(자식 그래프)를 빠져나와 부모 그래프의 다른 노드로 이동한다.
- active_agent 를 상태에 저장하고 체크포인터를 쓰면, 다음 턴은 마지막 에이전트가 바로 받는다(스웜의 핵심).
- handoff_count 로 핑퐁(A→B→A→B…)을 막는다.
"""

import os
from typing import NotRequired

from langchain.agents import AgentState, create_agent
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_HANDOFFS = 3  # 한 번의 요청에서 허용하는 최대 핸드오프 횟수


# ---------------------------------------------------------------------------
# 1) 상태 정의
# ---------------------------------------------------------------------------
class SupportState(MessagesState):
    """부모 그래프 상태."""

    active_agent: NotRequired[str]  # 마지막으로 대화를 맡은 에이전트
    handoff_count: NotRequired[int]  # 이번 요청에서 일어난 핸드오프 횟수


class AgentWithHandoffState(AgentState):
    """자식(에이전트) 상태. 부모와 같은 이름의 키는 자동으로 주고받는다."""

    handoff_count: NotRequired[int]


# ---------------------------------------------------------------------------
# 2) 핸드오프 도구 팩토리
# ---------------------------------------------------------------------------
def make_handoff_tool(agent_name: str, description: str):
    """`agent_name` 으로 대화 주도권을 넘기는 도구를 만든다."""

    @tool(f"transfer_to_{agent_name}", description=description)
    def handoff(runtime: ToolRuntime) -> Command | str:
        count = runtime.state.get("handoff_count", 0)
        if count >= MAX_HANDOFFS:
            # 상한 초과: 이동하지 않고 '현재 에이전트가 직접 처리하라'는 결과만 돌려준다
            return f"핸드오프 한도({MAX_HANDOFFS})를 넘었습니다. 현재 에이전트가 직접 답하세요."

        tool_msg = ToolMessage(
            content=f"{agent_name} 에게 대화를 넘겼습니다.",
            name=f"transfer_to_{agent_name}",
            tool_call_id=runtime.tool_call_id,  # 어떤 tool_call 에 대한 응답인지 반드시 연결
        )
        return Command(
            goto=agent_name,  # 부모 그래프의 노드 이름
            graph=Command.PARENT,  # '나를 실행한 부모 그래프'에서 이동하라
            update={
                # 자식 안에서 만든 AI 메시지(tool_call 포함)가 부모로 전달되도록 현재 메시지 + 도구 응답을 함께 보낸다
                "messages": [*runtime.state["messages"], tool_msg],
                "active_agent": agent_name,
                "handoff_count": count + 1,
            },
        )

    return handoff


@tool
def check_refund_status(order_id: str) -> str:
    """refund 환불 처리 상태를 주문 번호로 조회한다."""
    return f"주문 {order_id}: 환불 승인 완료, 3영업일 내 입금 예정"


@tool
def check_server_status(service: str) -> str:
    """server 장애 여부를 확인한다."""
    return f"{service}: 정상 동작 중"


# ---------------------------------------------------------------------------
# 3) 에이전트들: 각자 '넘길 수 있는 대상'만 핸드오프 도구로 가진다
# ---------------------------------------------------------------------------
to_billing = make_handoff_tool("billing", "billing 결제·환불·청구 관련 요청을 결제 담당 에이전트에게 넘긴다.")
to_tech = make_handoff_tool("tech", "기술 오류, 로그인 장애 등 기술 지원 에이전트에게 넘긴다.")
to_triage = make_handoff_tool("triage", "담당 범위를 벗어난 요청을 접수 에이전트에게 되돌린다.")

triage = create_agent(
    MODEL, tools=[to_billing, to_tech], state_schema=AgentWithHandoffState, name="triage",
    system_prompt="당신은 고객센터 접수 담당입니다. 직접 답하지 말고 알맞은 담당자에게 넘기세요.",
)
billing = create_agent(
    MODEL, tools=[check_refund_status, to_triage], state_schema=AgentWithHandoffState, name="billing",
    system_prompt="당신은 결제·환불 담당입니다. 결제와 무관한 요청은 triage 로 되돌리세요.",
)
tech = create_agent(
    MODEL, tools=[check_server_status, to_triage], state_schema=AgentWithHandoffState, name="tech",
    system_prompt="당신은 기술 지원 담당입니다. 기술과 무관한 요청은 triage 로 되돌리세요.",
)


# ---------------------------------------------------------------------------
# 4) 부모 그래프: START 에서 '현재 활성 에이전트'로 보낸다
# ---------------------------------------------------------------------------
def route_to_active(state: SupportState) -> str:
    return state.get("active_agent", "triage")


def reset_counter(state: SupportState) -> dict:
    """새 사용자 메시지마다 핸드오프 카운터를 0으로 되돌린다."""
    return {"handoff_count": 0}


builder = StateGraph(SupportState)
builder.add_node("reset", reset_counter)
# destinations 는 그래프 그림에 핸드오프 경로를 표시하기 위한 정보다
builder.add_node("triage", triage, destinations=("billing", "tech"))
builder.add_node("billing", billing, destinations=("triage",))
builder.add_node("tech", tech, destinations=("triage",))
builder.add_edge(START, "reset")
builder.add_conditional_edges("reset", route_to_active, ["triage", "billing", "tech"])
graph = builder.compile(checkpointer=InMemorySaver())  # 멀티턴: active_agent 를 기억


def show_turn(title: str, out: dict, start_index: int) -> None:
    print("=" * 60)
    print(title, "| active_agent =", out.get("active_agent"), "| handoffs =", out.get("handoff_count"))
    print("-" * 60)
    for m in out["messages"][start_index:]:
        who = m.name or type(m).__name__
        if isinstance(m, AIMessage) and m.tool_calls:
            print(f"  {who:22} → tool_calls {[c['name'] for c in m.tool_calls]}")
        else:
            print(f"  {who:22} : {m.text[:80]}")


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "customer-42"}, "recursion_limit": 20}

    out1 = graph.invoke({"messages": [HumanMessage("billing 담당자에게 환불을 문의하고 싶어요")]}, config)
    show_turn("[턴 1] 접수 → 결제 담당으로 핸드오프", out1, 0)

    n = len(out1["messages"])
    out2 = graph.invoke({"messages": [HumanMessage("주문 A-1001 의 refund 처리 상태는요?")]}, config)
    show_turn("[턴 2] triage 를 거치지 않고 billing 이 바로 응답", out2, n)
