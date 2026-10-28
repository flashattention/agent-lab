"""ReWOO (Reasoning WithOut Observation): 계획 1회 + 도구 실행(LLM 없음) + 정리 1회

Plan-and-Execute 와의 차이
- Planner 가 처음에 '어떤 도구를 어떤 입력으로 부를지'까지 모두 정한다.
- 나중 단계의 입력에 앞 단계 결과를 변수(#E1, #E2 …)로 참조한다.
- Worker 는 LLM 없이 도구만 순서대로 실행한다 → LLM 호출이 2번으로 고정된다.
- 대신 중간 결과를 보고 계획을 고칠 수 없다(관찰 없이 계획하므로 'Without Observation').
"""

import ast
import operator
import os
import re
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_STEPS = 4


# ---------------------------------------------------------------------------
# 1) 도구: Worker 가 LLM 없이 직접 부른다
# ---------------------------------------------------------------------------
def search(query: str) -> str:
    return f"[검색:{query[:20]}] 서울 지하철 하루 이용객은 약 700만 명(가상 데이터)"


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def calculator(expression: str) -> str:
    """사칙연산만 허용하는 안전한 계산기 (eval 을 쓰지 않는다)."""

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        raise ValueError("허용되지 않은 식")

    try:
        return str(ev(ast.parse(expression, mode="eval").body))
    except Exception:
        return f"계산 불가: {expression[:40]}"


TOOLS = {"search": search, "calculator": calculator}


# ---------------------------------------------------------------------------
# 2) 계획 스키마: 단계마다 도구와 입력을 지정, 앞 결과는 #E1 처럼 참조
# ---------------------------------------------------------------------------
class Step(BaseModel):
    plan: str = Field(description="이 단계에서 무엇을 하는지")
    tool: Literal["search", "calculator"]
    tool_input: str = Field(description="도구 입력. 앞 단계 결과는 #E1, #E2 처럼 참조")


class ReWOOPlan(BaseModel):
    steps: list[Step]


class State(TypedDict):
    task: str
    steps: list[dict]
    evidence: dict[str, str]  # {"#E1": "...", "#E2": "..."}
    answer: str


llm = init_chat_model(MODEL)


def planner(state: State) -> dict:
    plan: ReWOOPlan = llm.with_structured_output(ReWOOPlan).invoke(
        [
            SystemMessage(
                "도구(search, calculator)로 문제를 푸는 계획을 한 번에 세우세요. "
                "각 단계 결과는 순서대로 #E1, #E2… 로 참조할 수 있습니다."
            ),
            HumanMessage(state["task"]),
        ]
    )
    steps = [s.model_dump() for s in plan.steps[:MAX_STEPS]]
    for i, s in enumerate(steps, 1):
        print(f"[planner] #E{i} = {s['tool']}({s['tool_input'][:40]!r})  # {s['plan']}")
    return {"steps": steps, "evidence": {}}


def worker(state: State) -> dict:
    """LLM 호출 없이 도구만 순서대로 실행한다."""
    evidence: dict[str, str] = {}
    for i, step in enumerate(state["steps"], 1):
        # #E1 같은 참조를 실제 결과로 치환
        tool_input = re.sub(r"#E\d+", lambda m: evidence.get(m.group(0), m.group(0)), step["tool_input"])
        result = TOOLS[step["tool"]](tool_input)
        evidence[f"#E{i}"] = result
        print(f"[worker ] #E{i} ← {result[:60]}")
    return {"evidence": evidence}


def solver(state: State) -> dict:
    lines = [f"{k}: {v}" for k, v in state["evidence"].items()]
    msg = llm.invoke(
        [
            SystemMessage("계획과 증거(evidence)를 바탕으로 최종 답을 쓰세요."),
            HumanMessage(f"문제: {state['task']}\n증거:\n" + "\n".join(lines)),
        ]
    )
    return {"answer": msg.text}


builder = StateGraph(State)
builder.add_node("planner", planner)
builder.add_node("worker", worker)
builder.add_node("solver", solver)
builder.add_edge(START, "planner")
builder.add_edge("planner", "worker")
builder.add_edge("worker", "solver")
builder.add_edge("solver", END)
graph = builder.compile()


if __name__ == "__main__":
    usage = UsageMetadataCallbackHandler()
    out = graph.invoke(
        {"task": "서울 지하철 하루 이용객 수를 찾고, 일주일(7일) 이용객 수를 계산해 줘"},
        {"recursion_limit": 10, "callbacks": [usage]},
    )
    print("=" * 60)
    print("최종 답:", out["answer"][:150])
    print("토큰 사용량(LLM 2회):", usage.usage_metadata)
    print("직접 확인: calculator('700 * 7') =", calculator("700 * 7"))
