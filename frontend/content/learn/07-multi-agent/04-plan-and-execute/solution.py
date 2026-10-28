"""실습: 체크리스트 기반 Plan-and-Execute 루프 완성하기

완성할 것
1. execute_step 노드
   - state["checklist"] 의 맨 앞 항목을 꺼내 executor_agent 로 실행 (recursion_limit 10)
   - 반환: {"checklist": 남은 항목, "done": [(항목, 결과 텍스트)]}
2. route 함수 (replanner 다음에 어디로 갈지)
   - state["final"] 이 채워졌으면 END
   - len(state["done"]) >= MAX_TOTAL_STEPS 이면 END (안전 상한)
   - 그 외에는 "execute_step"

replanner 는 이미 구현되어 있습니다. 결정이 respond 이거나 체크리스트가 비면 final 을 채웁니다.

자가 채점: 최소 1단계 이상 실행, 상한 이하, final 이 채워졌는지, done 의 각 항목이 (str, str) 튜플인지.
"""

import operator
import os
from typing import Annotated, Literal, TypedDict

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_TOTAL_STEPS = 5


class State(TypedDict):
    goal: str
    checklist: list[str]
    done: Annotated[list[tuple[str, str]], operator.add]
    final: str


class Checklist(BaseModel):
    items: list[str] = Field(description="실행할 단계 목록")


class Decision(BaseModel):
    action: Literal["continue", "replan", "respond"]
    new_items: list[str] = Field(default_factory=list)


llm = init_chat_model(MODEL)


@tool
def lookup_fact(query: str) -> str:
    """사실 정보를 조회한다."""
    return f"조회 결과: '{query[:20]}…' 관련 자료 3건"


executor_agent = create_agent(MODEL, tools=[lookup_fact], system_prompt="한 단계만 수행하고 짧게 보고하세요.")


def plan(state: State) -> dict:
    cl: Checklist = llm.with_structured_output(Checklist).invoke(
        [SystemMessage("목표를 실행 단계로 나누세요."), HumanMessage(state["goal"])]
    )
    return {"checklist": cl.items[:4]}


def execute_step(state: State) -> dict:
    item, rest = state["checklist"][0], state["checklist"][1:]
    result = executor_agent.invoke({"messages": [HumanMessage(f"목표: {state['goal']}\n단계: {item}")]}, {"recursion_limit": 10})
    return {"checklist": rest, "done": [(item, result["messages"][-1].text)]}


def replan(state: State) -> dict:
    history = [AIMessage(f"완료: {s} → {r[:40]}") for s, r in state["done"]]
    d: Decision = llm.with_structured_output(Decision).invoke(
        [SystemMessage("계속/수정/답변 중 고르세요."), HumanMessage(f"목표: {state['goal']}"), *history]
    )
    print(f"[replan] {d.action} (완료 {len(state['done'])}단계, 남은 {len(state['checklist'])}단계)")
    if d.action == "replan":
        return {"checklist": d.new_items[:3]}
    if d.action == "respond" or not state["checklist"]:
        return {"final": " / ".join(r for _, r in state["done"])}
    return {}


def route(state: State) -> Literal["execute_step", "__end__"]:
    if state.get("final"):
        return END
    if len(state["done"]) >= MAX_TOTAL_STEPS:
        return END
    return "execute_step"


builder = StateGraph(State)
builder.add_node("plan", plan)
builder.add_node("execute_step", execute_step)
builder.add_node("replan", replan)
builder.add_edge(START, "plan")
builder.add_edge("plan", "execute_step")
builder.add_edge("execute_step", "replan")
builder.add_conditional_edges("replan", route)
graph = builder.compile()


if __name__ == "__main__":
    out = graph.invoke({"goal": "팀 워크숍 준비: 장소 후보 조사와 예산 정리", "done": [], "final": ""}, {"recursion_limit": 30})
    for i, (s, r) in enumerate(out["done"], 1):
        print(f"{i}. {s} → {r[:50]}")

    assert 1 <= len(out["done"]) <= MAX_TOTAL_STEPS, "실행 단계 수가 범위를 벗어났습니다."
    assert all(isinstance(x, tuple) and len(x) == 2 for x in out["done"]), "done 항목은 (단계, 결과) 튜플이어야 합니다."
    assert out["final"], "final 이 채워져야 합니다."
    print("✅ 모든 테스트 통과!")
