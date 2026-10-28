"""4.5 예제 1 — ReAct 에이전트를 LangGraph로 직접 조립하기.

MessagesState + agent 노드 + ToolNode + tools_condition.
Mock 모드에서는 질문과 단어가 겹치는 도구(없으면 첫 번째 도구)를 호출한 뒤 답한다.
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

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


MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
TOOLS = [get_weather, multiply]
SYSTEM_PROMPT = "너는 친절한 비서다. 필요하면 도구를 사용하고, 한국어로 간결하게 답한다."

# 1) 모델에 도구 스키마를 바인딩 → 모델은 tool_calls 로 '호출 요청'만 한다
llm = init_chat_model(MODEL).bind_tools(TOOLS)


# 2) Reason: 대화 전체를 보고 다음 행동(도구 호출 또는 답변)을 정하는 노드
def agent(state: MessagesState) -> dict:
    # 시스템 프롬프트는 상태에 저장하지 않고 호출할 때마다 앞에 붙인다
    ai = llm.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [ai]}  # add_messages 리듀서가 대화에 이어 붙인다


# 3) 그래프 조립
builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS))  # Act: tool_calls 실행 → ToolMessage 생성
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # tool_calls 있으면 "tools", 없으면 END
builder.add_edge("tools", "agent")  # 도구 결과를 보고 다시 생각
graph = builder.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())

    for question in ["부산 날씨 알려줘", "계산기로 12 곱하기 7 해줘"]:
        print("\n" + "#" * 70 + f"\n# 질문: {question}\n" + "#" * 70)
        result = graph.invoke(
            {"messages": [HumanMessage(question)]},
            config={"recursion_limit": 11},  # agent↔tools 최대 5바퀴 정도
        )
        for msg in result["messages"]:
            msg.pretty_print()

        # 흐름 검증: Human → AI(tool_calls) → Tool → AI(최종) 순서인지 확인
        kinds = [type(m).__name__ for m in result["messages"]]
        print("메시지 순서:", " → ".join(kinds))
