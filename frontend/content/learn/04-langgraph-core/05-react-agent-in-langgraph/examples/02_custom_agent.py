"""4.5 예제 2 — 직접 짠 그래프에서만 쉬운 커스터마이징 3가지.

1) 도구 호출 상한: 카운터 + 커스텀 라우터 → 예외 대신 우아한 종료
2) 가드 노드: 허용 목록에 없는 위험 도구는 실행하지 않고 '거부' ToolMessage 로 대체
3) 후처리 노드: 최종 답변에 꼬리말 + 통계 기록
"""

import operator
import os
from typing import Annotated, Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

# ---------------------------------------------------------------- 도구 정의
WEATHER_DB = {"서울": "맑음, 18도", "부산": "흐림, 21도", "도쿄": "비, 16도"}


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다. weather lookup"""
    return f"{city}: {WEATHER_DB.get(city, '정보 없음')}"


@tool
def multiply(a: float, b: float) -> float:
    """계산기 도구: 두 수를 곱합니다. multiply calculator"""
    return a * b


@tool
def cancel_order(order_id: int) -> str:
    """주문취소 처리 도구입니다. 결제가 환불됩니다. (위험: 되돌릴 수 없음)"""
    return f"주문 {order_id} 취소 및 환불 완료"


MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
TOOLS = [get_weather, multiply, cancel_order]
ALLOWED_TOOLS = {"get_weather", "multiply"}  # cancel_order 는 사람 승인 없이는 금지
llm = init_chat_model(MODEL).bind_tools(TOOLS)


class AgentState(MessagesState):
    tool_rounds: Annotated[int, operator.add]  # 도구 실행 횟수 (노드는 증가분만 반환)
    max_tool_rounds: int
    blocked: Annotated[list[str], operator.add]


def agent(state: AgentState) -> dict:
    ai = llm.invoke([SystemMessage("너는 쇼핑몰 상담 비서다."), *state["messages"]])
    return {"messages": [ai]}


def route_after_agent(state: AgentState) -> Literal["guard", "finalize"]:
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return "finalize"  # 답변 완료
    if state.get("tool_rounds", 0) >= state.get("max_tool_rounds", 3):
        return "finalize"  # 상한 초과 → 우아하게 종료
    return "guard"


def guard(state: AgentState) -> dict:
    """허용되지 않은 도구 호출을 걸러 낸다. 거부된 호출에도 ToolMessage 를 만들어 짝을 맞춘다."""
    last: AIMessage = state["messages"][-1]
    allowed = [c for c in last.tool_calls if c["name"] in ALLOWED_TOOLS]
    denied = [c for c in last.tool_calls if c["name"] not in ALLOWED_TOOLS]
    denials = [
        ToolMessage(f"'{c['name']}' 도구는 상담원 승인이 필요해 실행하지 않았습니다.", tool_call_id=c["id"])
        for c in denied
    ]
    # 허용된 호출만 남긴 AIMessage 로 '같은 id' 교체 → add_messages 가 기존 메시지를 대체
    trimmed = AIMessage(content=last.content, tool_calls=allowed, id=last.id)
    return {"messages": [trimmed, *denials], "blocked": [c["name"] for c in denied]}


def route_after_guard(state: AgentState) -> Literal["tools", "agent"]:
    # 허용된 호출이 남아 있으면 실행, 모두 거부됐으면 바로 agent 에게 결과를 보여 준다
    ai = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
    return "tools" if ai.tool_calls else "agent"


tool_node = ToolNode(TOOLS, handle_tool_errors=True)  # 도구 내부 예외도 ToolMessage 로 변환


def run_tools(state: AgentState) -> dict:
    out = tool_node.invoke(state)
    return {"messages": out["messages"], "tool_rounds": 1}


def finalize(state: AgentState) -> dict:
    last = state["messages"][-1]
    msgs = []
    if getattr(last, "tool_calls", None):
        # 상한으로 끊긴 경우: 응답 없는 tool_calls 가 남지 않게 짝을 맞추고 안내 메시지로 끝낸다
        msgs += [ToolMessage("호출 상한으로 실행하지 않음", tool_call_id=c["id"]) for c in last.tool_calls]
        msgs.append(AIMessage("도구 사용 한도에 도달했습니다. 지금까지의 정보로 상담원이 이어서 도와드릴게요."))
    else:
        msgs.append(AIMessage(f"{last.content}\n\n— 사용 도구 {state.get('tool_rounds', 0)}회", id=last.id))
    return {"messages": msgs}


builder = StateGraph(AgentState)
builder.add_node(agent)
builder.add_node(guard)
builder.add_node("tools", run_tools)
builder.add_node(finalize)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_after_agent)
builder.add_conditional_edges("guard", route_after_guard)
builder.add_edge("tools", "agent")
builder.add_edge("finalize", END)
graph = builder.compile()


def run(question: str, max_tool_rounds: int = 3) -> None:
    print("\n" + "#" * 70 + f"\n# {question}  (max_tool_rounds={max_tool_rounds})\n" + "#" * 70)
    path = []
    final = None
    for chunk in graph.stream(
        {"messages": [HumanMessage(question)], "max_tool_rounds": max_tool_rounds},
        config={"recursion_limit": 20},
        stream_mode=["updates", "values"],
    ):
        mode, data = chunk
        if mode == "updates":
            path += list(data)
        else:
            final = data
    print("경로:", " → ".join(path))
    print("차단된 도구:", final.get("blocked", []))
    print("최종 답변:", final["messages"][-1].content[:150])


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
    run("서울 날씨 어때?")  # 정상: 허용 도구
    run("주문취소 해주세요 1234번")  # 위험 도구 → guard 가 차단
    run("부산 날씨 알려줘", max_tool_rounds=0)  # 상한 0 → 도구 없이 우아하게 종료
