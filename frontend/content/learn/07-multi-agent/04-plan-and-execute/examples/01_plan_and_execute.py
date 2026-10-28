"""Plan-and-Execute: Planner → Executor(단계별) → Replanner 루프

흐름
  START → planner → executor → replanner ─┬─(continue)→ executor
                                           ├─(replan)  → executor (새 계획으로)
                                           └─(respond) → END

설계 포인트
- Planner 는 '무엇을 할지' 체크리스트만 만든다(큰 모델, 1회).
- Executor 는 체크리스트의 맨 앞 한 단계만 수행한다(작은 모델 + 도구).
- Replanner 는 지금까지의 결과를 보고 계속/수정/종료를 고른다.
- 상한 3종: 계획 길이(MAX_PLAN_STEPS), 재계획 횟수(MAX_REPLANS), 총 실행 단계(MAX_TOTAL_STEPS).
"""

import operator
import os
from typing import Annotated, Literal, TypedDict

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_PLAN_STEPS = 4
MAX_REPLANS = 2
MAX_TOTAL_STEPS = 6


# ---------------------------------------------------------------------------
# 1) 상태
# ---------------------------------------------------------------------------
class PlanExecuteState(TypedDict):
    input: str  # 사용자의 원래 목표
    plan: list[str]  # 남은 체크리스트
    past_steps: Annotated[list[tuple[str, str]], operator.add]  # (단계, 결과) 누적
    replans: int
    response: str


# ---------------------------------------------------------------------------
# 2) 구조화 출력 스키마
# ---------------------------------------------------------------------------
class Plan(BaseModel):
    """목표를 달성하기 위한 순서 있는 단계 목록."""

    steps: list[str] = Field(description="각 단계는 독립적으로 실행 가능한 한 문장")


class ReplanDecision(BaseModel):
    """지금까지의 결과를 보고 다음 행동을 고른다."""

    action: Literal["continue", "replan", "respond"] = Field(
        description="continue=남은 계획 진행, replan=계획 수정, respond=최종 답변"
    )
    new_steps: list[str] = Field(default_factory=list, description="replan 일 때의 새 남은 단계")
    response: str = Field(default="", description="respond 일 때의 최종 답변")


llm = init_chat_model(MODEL)
planner_llm = llm.with_structured_output(Plan)
replanner_llm = llm.with_structured_output(ReplanDecision)


# ---------------------------------------------------------------------------
# 3) Executor 에이전트와 도구
# ---------------------------------------------------------------------------
@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색한다."""
    return f"[검색] '{query[:30]}…' → 2025년 국내 전기차 판매량은 약 22만 대(가상 데이터)."


@tool
def calculator(a: float, b: float) -> float:
    """두 수를 곱한다."""
    return a * b


executor_agent = create_agent(
    MODEL,
    tools=[search_web, calculator],
    system_prompt="당신은 실행 담당입니다. 주어진 '한 단계'만 수행하고 결과를 짧게 보고하세요.",
    name="executor",
)


# ---------------------------------------------------------------------------
# 4) 노드
# ---------------------------------------------------------------------------
def planner(state: PlanExecuteState) -> dict:
    plan: Plan = planner_llm.invoke(
        [SystemMessage("목표를 3~4개의 실행 단계로 나누세요. 단계마다 한 문장."), HumanMessage(state["input"])]
    )
    steps = plan.steps[:MAX_PLAN_STEPS]  # 상한 1: 계획 길이
    print(f"[planner] 계획 {len(steps)}단계: {steps}")
    return {"plan": steps, "replans": 0}


def executor(state: PlanExecuteState) -> dict:
    task, rest = state["plan"][0], state["plan"][1:]
    prompt = f"전체 목표: {state['input']}\n지금 수행할 단계: {task}"
    result = executor_agent.invoke({"messages": [HumanMessage(prompt)]}, {"recursion_limit": 10})
    answer = result["messages"][-1].text
    print(f"[executor] ✔ {task} → {answer[:60]}…")
    return {"plan": rest, "past_steps": [(task, answer)]}


def replanner(state: PlanExecuteState) -> dict:
    # 완료된 단계를 AI 메시지로 나열해 '지금까지 무엇을 했는지' 보여준다
    history = [AIMessage(f"완료한 단계: {s}\n결과: {r}") for s, r in state["past_steps"]]
    decision: ReplanDecision = replanner_llm.invoke(
        [
            SystemMessage("목표와 완료된 단계를 보고, 남은 계획으로 계속할지, 계획을 고칠지, 답할지 고르세요."),
            HumanMessage(f"목표: {state['input']}\n남은 계획: {state['plan']}"),
            *history,
        ]
    )
    action = decision.action
    # 상한 2, 3: 강제 종료 조건
    if len(state["past_steps"]) >= MAX_TOTAL_STEPS:
        action = "respond"
    if action == "replan" and state["replans"] >= MAX_REPLANS:
        action = "continue"
    if action == "continue" and not state["plan"]:
        action = "respond"  # 더 할 일이 없으면 답변
    print(f"[replanner] 결정 = {decision.action} → 적용 = {action}")

    if action == "replan":
        return {"plan": decision.new_steps[:MAX_PLAN_STEPS], "replans": state["replans"] + 1}
    if action == "respond":
        summary = decision.response or " / ".join(r for _, r in state["past_steps"])
        return {"response": summary, "plan": []}
    return {}


def route_after_replan(state: PlanExecuteState) -> Literal["executor", "__end__"]:
    return END if state.get("response") else "executor"


builder = StateGraph(PlanExecuteState)
builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_node("replanner", replanner)
builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")
builder.add_edge("executor", "replanner")
builder.add_conditional_edges("replanner", route_after_replan)
graph = builder.compile()


if __name__ == "__main__":
    usage = UsageMetadataCallbackHandler()  # 모든 LLM 호출의 토큰 사용량을 모델별로 합산
    out = graph.invoke(
        {"input": "국내 전기차 판매량을 조사하고 2배가 되면 몇 대인지 계산해 줘", "past_steps": [], "response": ""},
        {"recursion_limit": 30, "callbacks": [usage]},
    )
    print("=" * 60)
    print("실행한 단계 수:", len(out["past_steps"]), "/ 재계획:", out["replans"])
    print("최종 답변:", out["response"][:150])
    print("토큰 사용량:", usage.usage_metadata)
