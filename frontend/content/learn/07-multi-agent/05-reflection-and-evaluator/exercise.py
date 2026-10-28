"""실습: Evaluator-Optimizer 루프의 '판단 로직' 완성하기

완성할 것
1. evaluator 노드 안의 판단 로직
   - passed = (점수 >= QUALITY_BAR)
   - 점수가 지금까지의 best_score 보다 높으면 best_draft / best_score 갱신
2. route 함수
   - passed 면 END
   - iterations 가 MAX_ITERATIONS 이상이면 END (반복 상한)
   - 그 외에는 "optimizer"

자가 채점 (Mock 모델은 score 를 항상 8 로 줍니다. QUALITY_BAR=9 이므로 통과하지 못하고 상한에서 멈춰야 합니다)
- 반복 횟수가 정확히 MAX_ITERATIONS 인가
- 점수 이력 길이 == 반복 횟수
- 통과하지 못했어도 best_draft 가 채워져 있는가 (graceful degradation)
"""

import os
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_ITERATIONS = 3
QUALITY_BAR = 9

llm = init_chat_model(MODEL)


class Grade(BaseModel):
    score: int = Field(ge=1, le=10, description="전체 품질 점수")
    feedback: str


class State(TypedDict):
    task: str
    draft: str
    feedback: str
    iterations: int
    scores: list[int]
    best_draft: str
    best_score: int
    passed: bool


def optimizer(state: State) -> dict:
    prompt = f"과제: {state['task']}" + (f"\n고칠 점: {state['feedback']}" if state["feedback"] else "")
    draft = llm.invoke([SystemMessage("간결한 카피라이터입니다."), HumanMessage(prompt)]).text
    return {"draft": draft, "iterations": state["iterations"] + 1}


def evaluator(state: State) -> dict:
    grade: Grade = llm.with_structured_output(Grade).invoke(
        [SystemMessage("엄격하게 채점하세요."), HumanMessage(f"과제: {state['task']}\n초안: {state['draft']}")]
    )
    update = {"feedback": grade.feedback, "scores": state["scores"] + [grade.score]}

    # TODO 1: update["passed"] 에 통과 여부(grade.score >= QUALITY_BAR)를 넣으세요.
    update["passed"] = False

    # TODO 2: grade.score 가 state["best_score"] 보다 크면
    #         update["best_draft"], update["best_score"] 를 갱신하세요.

    return update


def route(state: State) -> Literal["optimizer", "__end__"]:
    # TODO 3: 통과했으면 END
    # TODO 4: iterations 가 MAX_ITERATIONS 이상이면 END
    # TODO 5: 그 외에는 "optimizer"
    raise NotImplementedError("TODO 3~5: route 를 완성하세요")


builder = StateGraph(State)
builder.add_node("optimizer", optimizer)
builder.add_node("evaluator", evaluator)
builder.add_edge(START, "optimizer")
builder.add_edge("optimizer", "evaluator")
builder.add_conditional_edges("evaluator", route)
graph = builder.compile()


if __name__ == "__main__":
    init = {"task": "신제품 무선 이어폰 한 줄 광고 문구", "draft": "", "feedback": "", "iterations": 0,
            "scores": [], "best_draft": "", "best_score": 0, "passed": False}
    out = graph.invoke(init, {"recursion_limit": 2 * MAX_ITERATIONS + 2})
    print(f"반복 {out['iterations']}회, 점수 {out['scores']}, 통과={out['passed']}")
    print("최고 초안:", out["best_draft"][:80])

    assert out["iterations"] <= MAX_ITERATIONS, "반복 상한을 넘었습니다."
    assert len(out["scores"]) == out["iterations"], "점수 이력 길이와 반복 횟수가 달라요."
    if not out["passed"]:
        assert out["iterations"] == MAX_ITERATIONS, "통과하지 못했다면 상한까지 반복해야 합니다."
    assert out["best_draft"] and out["best_score"] > 0, "best_draft 를 갱신하세요."
    print("✅ 모든 테스트 통과!")
