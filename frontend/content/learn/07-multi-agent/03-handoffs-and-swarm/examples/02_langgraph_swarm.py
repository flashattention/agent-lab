"""langgraph-swarm 으로 스웜(Swarm) 만들기

create_swarm 이 해 주는 일
- 각 에이전트를 부모 그래프의 노드로 등록
- SwarmState 에 active_agent 필드를 두고, START 에서 활성 에이전트로 라우팅
  (add_active_agent_router)
- create_handoff_tool 은 Command(goto=에이전트, graph=Command.PARENT, update={active_agent...}) 를 반환
→ 01 예제에서 직접 만든 것과 같은 구조다.
"""

import os

from langchain.agents import create_agent
from langchain.messages import AIMessage, HumanMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph_swarm import create_handoff_tool, create_swarm

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def search_flights(city: str) -> str:
    """flight 항공편을 도착 도시로 검색한다."""
    return f"{city} 행 항공편: KE123 (09:00), OZ456 (14:30)"


@tool
def search_hotels(city: str) -> str:
    """hotel 숙소를 도시로 검색한다."""
    return f"{city} 숙소: 시티호텔(1박 12만원), 리버호텔(1박 15만원)"


flight_agent = create_agent(
    MODEL,
    tools=[
        search_flights,
        create_handoff_tool(agent_name="hotel_agent", description="hotel 숙소 예약 담당에게 넘긴다."),
    ],
    system_prompt="당신은 항공권 담당입니다. 숙소 요청은 hotel_agent 에게 넘기세요.",
    name="flight_agent",
)
hotel_agent = create_agent(
    MODEL,
    tools=[
        search_hotels,
        create_handoff_tool(agent_name="flight_agent", description="flight 항공권 담당에게 넘긴다."),
    ],
    system_prompt="당신은 숙소 담당입니다. 항공권 요청은 flight_agent 에게 넘기세요.",
    name="hotel_agent",
)

checkpointer = InMemorySaver()
app = create_swarm([flight_agent, hotel_agent], default_active_agent="flight_agent").compile(checkpointer=checkpointer)


def run_turn(text: str, config: dict) -> None:
    before = len(app.get_state(config).values.get("messages", []))
    try:
        out = app.invoke({"messages": [HumanMessage(text)]}, config)
    except GraphRecursionError:
        print("⚠️ recursion_limit 도달: 에이전트끼리 핑퐁 중일 수 있습니다. 핸드오프 설명을 점검하세요.")
        return
    print("=" * 60)
    print(f"사용자: {text}")
    # 아직 한 번도 핸드오프가 없으면 active_agent 키가 비어 있고, default_active_agent 가 쓰인다
    print(f"→ 이번 턴 이후 active_agent = {out.get('active_agent') or '(미설정 → 기본값 flight_agent)'}")
    for m in out["messages"][before + 1 :]:
        if isinstance(m, AIMessage) and m.tool_calls:
            print(f"  {m.name:13} → {[c['name'] for c in m.tool_calls]}")
        else:
            print(f"  {(m.name or ''):13} : {m.text[:70]}")


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "trip-1"}, "recursion_limit": 20}
    run_turn("부산 가는 flight 를 찾아줘", config)  # 기본 활성 에이전트(flight_agent)가 받음
    run_turn("부산 hotel 도 알아봐 줘", config)  # flight_agent → hotel_agent 핸드오프
    run_turn("1박 가격을 다시 알려줘", config)  # 이제 hotel_agent 가 먼저 받는다
