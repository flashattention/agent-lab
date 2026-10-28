"""4.5 예제 3 — 직접 만든 ReAct 그래프 vs create_agent.

두 방식의 그래프 구조와 실행 결과(메시지 흐름)를 나란히 비교한다.
"""

import os

from langchain.agents import create_agent
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
SYSTEM_PROMPT = "너는 친절한 비서다. 필요하면 도구를 사용한다."

# ---------------------------------------------------------------- A) 직접 조립
llm = init_chat_model(MODEL).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    return {"messages": [llm.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])]}


b = StateGraph(MessagesState)
b.add_node("agent", agent)
b.add_node("tools", ToolNode(TOOLS))
b.add_edge(START, "agent")
b.add_conditional_edges("agent", tools_condition)
b.add_edge("tools", "agent")
handmade = b.compile()

# ---------------------------------------------------------------- B) create_agent
prebuilt = create_agent(MODEL, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


def edges(graph) -> list[str]:
    """Mermaid 문자열에서 엣지 줄만 뽑아 구조를 비교하기 쉽게 만든다."""
    return [line.strip() for line in graph.get_graph().draw_mermaid().splitlines() if "->" in line]


print("=" * 70)
print("그래프 구조 비교")
print("=" * 70)
print("[직접 조립]   ", edges(handmade))
print("[create_agent]", edges(prebuilt))
print("→ 노드 이름(agent/model)만 다를 뿐 'LLM ↔ 도구' 루프 구조는 같다.")

question = {"messages": [HumanMessage("도쿄 날씨 알려줘")]}
config = {"recursion_limit": 11}
for name, graph in (("직접 조립", handmade), ("create_agent", prebuilt)):
    result = graph.invoke(question, config=config)
    kinds = [type(m).__name__ for m in result["messages"]]
    print("\n" + "-" * 70)
    print(f"[{name}] 메시지 흐름: {' → '.join(kinds)}")
    print(f"[{name}] 최종 답변 : {result['messages'][-1].content[:100]}")

print("\n※ create_agent 는 여기에 미들웨어(→ 3.3), response_format 등을 얹은 '표준화된 그래프'다.")
