"""실습: 작업자 3명(researcher, writer, reviewer)을 거느린 Supervisor 완성하기

해야 할 일
1. supervisor 노드: 
   - steps 가 MAX_STEPS 이상이면 END 로 강제 종료
   - router_llm 으로 Route 를 받아 FINISH 면 END, 아니면 해당 작업자로 이동
   - steps 를 1 증가시켜 update
2. 작업자 노드(make_worker_node):
   - 에이전트를 공유 messages 로 실행(recursion_limit 10)
   - 결과의 '마지막 메시지 텍스트'만 AIMessage(content=..., name=name) 으로 추가
   - 다시 supervisor 로 이동

자가 채점: 세 작업자가 각각 정확히 한 번씩 일하고, 관리자 결정 횟수가 MAX_STEPS 이하인지 검사합니다.
(Mock 모델은 Literal 선택지를 순서대로 돌고 마지막에 FINISH 를 고릅니다.)
"""

import os
from typing import Literal

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_STEPS = 6


class TeamState(MessagesState):
    steps: int


class Route(BaseModel):
    """다음 작업자를 고른다. 모든 일이 끝났으면 FINISH."""

    next: Literal["researcher", "writer", "reviewer", "FINISH"]
    reason: str = Field(description="선택 이유")


PROMPT = "당신은 관리자입니다. researcher(조사) → writer(작성) → reviewer(검토) 순서로 일을 맡기고, 끝나면 FINISH."
router_llm = init_chat_model(MODEL).with_structured_output(Route)


def supervisor(state: TeamState) -> Command[Literal["researcher", "writer", "reviewer", "__end__"]]:
    steps = state.get("steps", 0)
    # TODO 1: steps 가 MAX_STEPS 이상이면 Command(goto=END) 를 반환하세요.

    # TODO 2: router_llm.invoke([SystemMessage(PROMPT), *state["messages"]]) 로 Route 를 받으세요.
    decision = None

    # TODO 3: decision.next 가 "FINISH" 면 END, 아니면 decision.next 로 이동하고 steps 를 1 올리세요.
    raise NotImplementedError("TODO 1~3: supervisor 를 완성하세요")


def make_worker_node(name: str, system_prompt: str):
    agent = create_agent(MODEL, tools=[], system_prompt=system_prompt, name=name)

    def node(state: TeamState) -> Command[Literal["supervisor"]]:
        # TODO 4: agent 를 {"messages": state["messages"]} 와 {"recursion_limit": 10} 으로 실행하세요.
        # TODO 5: 마지막 메시지의 텍스트만 AIMessage(content=..., name=name) 으로 만들어
        #         Command(goto="supervisor", update={"messages": [...]}) 로 반환하세요.
        raise NotImplementedError("TODO 4~5: 작업자 노드를 완성하세요")

    return node


builder = StateGraph(TeamState)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", make_worker_node("researcher", "당신은 조사 담당입니다."))
builder.add_node("writer", make_worker_node("writer", "당신은 작가입니다."))
builder.add_node("reviewer", make_worker_node("reviewer", "당신은 꼼꼼한 검토자입니다."))
builder.add_edge(START, "supervisor")
graph = builder.compile()


if __name__ == "__main__":
    out = graph.invoke(
        {"messages": [HumanMessage("에이전트 관측성에 대한 사내 공지문을 준비해 줘")], "steps": 0},
        {"recursion_limit": 30},
    )
    speakers = [m.name for m in out["messages"] if isinstance(m, AIMessage)]
    print("작업 순서:", speakers, "/ 관리자 결정 횟수:", out["steps"])

    assert sorted(speakers) == ["researcher", "reviewer", "writer"], f"세 작업자가 한 번씩 일해야 합니다: {speakers}"
    assert out["steps"] <= MAX_STEPS, "관리자 결정 횟수가 상한을 넘었습니다."
    assert all(m.name for m in out["messages"] if isinstance(m, AIMessage)), "작업자 메시지에는 name 이 있어야 합니다."
    print("✅ 모든 테스트 통과!")
