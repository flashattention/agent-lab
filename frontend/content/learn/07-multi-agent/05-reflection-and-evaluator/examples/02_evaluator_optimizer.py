"""Evaluator-Optimizer: 평가자가 '기준'으로 채점하고, 통과할 때까지(상한 내) 최적화한다

Reflection 과의 차이
- 평가자는 구조화 출력으로 점수와 피드백을 낸다 → 코드가 '통과 여부'를 판단한다.
- 규칙 기반 검사(길이, 필수 단어)를 LLM 채점보다 먼저 한다 → 싸고 결정적이다.
- 상한에 도달하면 '지금까지 최고 점수 초안'을 품질 미달 표시와 함께 돌려준다.
"""

import os
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_ITERATIONS = 3
MAX_CHARS = 400  # 규칙 기반 기준: 글자 수 상한

llm = init_chat_model(MODEL)


class Evaluation(BaseModel):
    """채점 기준(rubric)에 따른 평가."""

    accuracy_score: int = Field(ge=1, le=10, description="사실 정확성 1~10")
    clarity_score: int = Field(ge=1, le=10, description="초보자 눈높이의 명확성 1~10")
    feedback: str = Field(description="다음 초안에서 고칠 점")


class State(TypedDict):
    task: str
    quality_bar: int
    draft: str
    feedback: str
    iterations: int
    scores: list[int]
    best_draft: str
    best_score: int
    passed: bool


def optimizer(state: State) -> dict:
    prompt = f"과제: {state['task']}\n{MAX_CHARS}자 이내로 쓰세요."
    if state["feedback"]:
        prompt += f"\n이전 초안:\n{state['draft']}\n고칠 점:\n{state['feedback']}"
    draft = llm.invoke([SystemMessage("당신은 기술 문서 작가입니다."), HumanMessage(prompt)]).text
    return {"draft": draft, "iterations": state["iterations"] + 1}


def evaluator(state: State) -> dict:
    draft = state["draft"]
    # 1단계: 규칙 기반 검사 (LLM 호출 없음, 결정적)
    rule_issues = []
    if len(draft) > MAX_CHARS:
        rule_issues.append(f"{MAX_CHARS}자를 넘었습니다({len(draft)}자).")
    if rule_issues:
        score, feedback = 1, " ".join(rule_issues)
    else:
        # 2단계: LLM 채점 (rubric 기반 구조화 출력)
        ev: Evaluation = llm.with_structured_output(Evaluation).invoke(
            [
                SystemMessage("당신은 엄격한 평가자입니다. 채점 기준에 따라 점수를 매기세요."),
                HumanMessage(f"과제: {state['task']}\n초안:\n{draft}"),
            ]
        )
        score = min(ev.accuracy_score, ev.clarity_score)  # 가장 약한 기준이 전체 품질을 결정
        feedback = ev.feedback

    passed = score >= state["quality_bar"]  # 통과 여부는 코드가 판단
    print(f"  [evaluator] #{state['iterations']} score={score} (기준 {state['quality_bar']}) → {'통과' if passed else '미달'}")
    update = {"feedback": feedback, "scores": state["scores"] + [score], "passed": passed}
    if score > state["best_score"]:
        update |= {"best_draft": draft, "best_score": score}
    return update


def route(state: State) -> Literal["optimizer", "__end__"]:
    if state["passed"]:
        return END
    if state["iterations"] >= MAX_ITERATIONS:
        print(f"  [route] 반복 상한({MAX_ITERATIONS}) 도달 → 최고 점수 초안으로 종료")
        return END
    return "optimizer"


builder = StateGraph(State)
builder.add_node("optimizer", optimizer)
builder.add_node("evaluator", evaluator)
builder.add_edge(START, "optimizer")
builder.add_edge("optimizer", "evaluator")
builder.add_conditional_edges("evaluator", route)
graph = builder.compile()


def run(quality_bar: int) -> None:
    print("=" * 60)
    print(f"품질 기준 {quality_bar}점으로 실행")
    out = graph.invoke(
        {
            "task": "RAG가 무엇인지 초보자에게 설명",
            "quality_bar": quality_bar,
            "draft": "",
            "feedback": "",
            "iterations": 0,
            "scores": [],
            "best_draft": "",
            "best_score": 0,
            "passed": False,
        },
        {"recursion_limit": 2 * MAX_ITERATIONS + 2},
    )
    status = "✅ 통과" if out["passed"] else "⚠️ 기준 미달(최고 점수 초안 반환)"
    print(f"  결과: {status} | 반복 {out['iterations']}회 | 점수 이력 {out['scores']}")
    print(f"  최종 초안: {out['best_draft'][:80].replace(chr(10), ' ')}")


if __name__ == "__main__":
    # Mock 모델은 score 류 숫자 필드를 항상 8로 채운다.
    run(quality_bar=8)  # 첫 초안에서 통과
    run(quality_bar=9)  # 통과 못 함 → 반복 상한에서 종료 (graceful degradation)
