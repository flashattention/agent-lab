"""Supervisor 패턴 직접 구현: 구조화 출력 라우터 + Command

흐름
  START → supervisor ─(Route.next)→ researcher / writer ─→ supervisor → … → FINISH → END

설계 포인트
- 라우팅 결정은 '자유 텍스트'가 아니라 Literal 로 제한된 구조화 출력(structured output)으로 받는다.
- 작업자는 내부 대화(도구 호출 등)를 숨기고, 최종 답변 한 개만 공유 상태에 추가한다.
- 관리자는 steps 카운터로 최대 단계 수를 강제한다. (LLM이 FINISH를 잊어도 끝난다)
"""

import os
from typing import Literal

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_STEPS = 5  # 관리자가 결정할 수 있는 최대 횟수

WORKERS = ["researcher", "writer"]


# ---------------------------------------------------------------------------
# 1) 상태: 메시지 + 단계 카운터
# ---------------------------------------------------------------------------
class SupervisorState(MessagesState):
    steps: int


# ---------------------------------------------------------------------------
# 2) 라우터 스키마: 관리자가 고를 수 있는 선택지를 Literal 로 '닫는다'
# ---------------------------------------------------------------------------
class Route(BaseModel):
    """다음에 일할 작업자를 고른다. 모든 일이 끝났으면 FINISH."""

    next: Literal["researcher", "writer", "FINISH"] = Field(description="다음 작업자 또는 FINISH")
    reason: str = Field(description="그렇게 고른 이유 한 문장")


SUPERVISOR_PROMPT = (
    "당신은 팀 관리자입니다. 작업자: researcher(자료 조사), writer(글 작성).\n"
    "대화 기록을 보고 다음에 일할 작업자를 고르세요. 조사 → 작성 순서가 기본이며,\n"
    "사용자 요청이 충족되었으면 FINISH 를 고르세요."
)

router_llm = init_chat_model(MODEL).with_structured_output(Route)


def supervisor(state: SupervisorState) -> Command[Literal["researcher", "writer", "__end__"]]:
    steps = state.get("steps", 0)
    if steps >= MAX_STEPS:  # 안전장치: LLM 판단과 무관하게 종료
        print(f"  [supervisor] 최대 단계({MAX_STEPS}) 도달 → 강제 종료")
        return Command(goto=END)

    decision: Route = router_llm.invoke([SystemMessage(SUPERVISOR_PROMPT), *state["messages"]])
    print(f"  [supervisor] step={steps} → {decision.next} ({decision.reason})")

    goto = END if decision.next == "FINISH" else decision.next
    return Command(goto=goto, update={"steps": steps + 1})


# ---------------------------------------------------------------------------
# 3) 작업자: create_agent 로 만들고, 노드 함수로 감싼다
# ---------------------------------------------------------------------------
@tool
def search_web(query: str) -> str:
    """웹에서 자료를 검색한다."""
    return f"'{query}' 검색 결과: LangGraph는 상태 기반 에이전트 프레임워크다."


@tool
def count_words(text: str) -> int:
    """글의 단어 수를 센다."""
    return len(text.split())


researcher_agent = create_agent(
    MODEL, tools=[search_web], system_prompt="당신은 조사 전문가입니다. 검색 후 핵심만 보고하세요.", name="researcher"
)
writer_agent = create_agent(
    MODEL, tools=[count_words], system_prompt="당신은 작가입니다. 조사 내용을 바탕으로 짧은 글을 쓰세요.", name="writer"
)


def make_worker_node(name: str, agent):
    """작업자 에이전트를 실행하고 '최종 답변 한 개'만 공유 상태에 돌려주는 노드를 만든다."""

    def node(state: SupervisorState) -> Command[Literal["supervisor"]]:
        result = agent.invoke({"messages": state["messages"]}, {"recursion_limit": 10})
        final = result["messages"][-1]
        print(f"  [{name}] 내부 메시지 {len(result['messages']) - len(state['messages'])}개 생성 → 1개만 공유")
        # name 을 붙여 두면 관리자와 트레이스에서 '누가 말했는지' 구분된다
        return Command(goto="supervisor", update={"messages": [AIMessage(content=final.text, name=name)]})

    return node


# ---------------------------------------------------------------------------
# 4) 그래프 조립: 엣지는 START → supervisor 하나뿐. 나머지는 Command 가 정한다
# ---------------------------------------------------------------------------
builder = StateGraph(SupervisorState)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", make_worker_node("researcher", researcher_agent))
builder.add_node("writer", make_worker_node("writer", writer_agent))
builder.add_edge(START, "supervisor")
graph = builder.compile()


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid().split("graph TD;")[1].split("classDef")[0])
    print("=" * 60)
    out = graph.invoke(
        {"messages": [HumanMessage("LangGraph를 소개하는 짧은 블로그 글을 만들어 줘")], "steps": 0},
        {"recursion_limit": 25},
    )
    print("=" * 60)
    for m in out["messages"]:
        m.pretty_print()
    speakers = [m.name for m in out["messages"] if isinstance(m, AIMessage)]
    print(f"\n작업 순서: {speakers} / 관리자 결정 횟수: {out['steps']}")
