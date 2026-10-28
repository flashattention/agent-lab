"""4.5 실습 — 주문 조회 ReAct 에이전트를 그래프로 조립하기 (정답)

과제
----
쇼핑몰 주문 조회 에이전트를 LangGraph 로 직접 만듭니다.

    START → agent ─(tool_calls 있음)→ tools → agent ...
                  └(tool_calls 없음)→ END

1. agent 노드: 시스템 프롬프트 + 대화(messages)로 llm 을 호출하고, 결과 AIMessage 를 messages 로 반환하세요.
2. tools 노드: ToolNode(TOOLS) 로 등록하세요. (노드 이름은 반드시 "tools")
3. agent 뒤에 tools_condition 으로 조건부 엣지를 걸고, tools → agent 엣지를 연결하세요.
4. 실행 시 recursion_limit 은 10 으로 제한합니다. (실행 코드에 이미 있음)

Mock 모드에서도 통과하도록 '흐름'만 검사합니다: Human → AI(tool_calls) → Tool → AI(최종).
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
ORDERS = {5521: "배송중 (내일 도착 예정)", 7310: "배송완료"}


@tool
def lookup_order(order_id: int) -> str:
    """주문번호로 주문조회 (배송 상태 확인)."""
    return f"주문 {order_id}: {ORDERS.get(order_id, '존재하지 않는 주문')}"


TOOLS = [lookup_order]
SYSTEM_PROMPT = "너는 쇼핑몰 상담원이다. 주문 상태는 반드시 lookup_order 도구로 확인한다."
llm = init_chat_model(MODEL).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    ai = llm.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [ai]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")
graph = builder.compile()


# ----------------------------------------------------------------- 자가 채점
nodes = set(graph.get_graph().nodes)
assert {"agent", "tools"} <= nodes, f"agent, tools 노드가 필요합니다: {nodes}"

result = graph.invoke({"messages": [HumanMessage("주문조회 부탁해요. 5521번")]}, {"recursion_limit": 10})
msgs = result["messages"]
for m in msgs:
    m.pretty_print()

assert isinstance(msgs[0], HumanMessage)
assert isinstance(msgs[1], AIMessage) and msgs[1].tool_calls, "첫 AI 메시지는 도구를 호출해야 합니다"
assert msgs[1].tool_calls[0]["name"] == "lookup_order"
assert isinstance(msgs[2], ToolMessage) and "5521" in msgs[2].content, "ToolNode 가 도구를 실행해야 합니다"
assert msgs[2].tool_call_id == msgs[1].tool_calls[0]["id"], "ToolMessage 는 tool_call_id 로 짝지어져야 합니다"
assert isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls, "마지막은 도구 호출 없는 최종 답변"

print("✅ 모든 테스트 통과!")
