"""실습: Routing + Evaluator-optimizer 워크플로 만들기 (정답)

1. classify(question) -> "billing" | "tech" | "general"
   - llm.with_structured_output(Route) 로 분류한다.
   - 분류 지침은 SystemMessage, 사용자 원문은 HumanMessage 에 넣는다.
2. handle(question) -> {"category": str, "answer": str}
   - classify 결과에 맞는 SYSTEM_PROMPTS[category] 를 시스템 프롬프트로 써서 답변을 생성한다.
3. refine(task, threshold, max_rounds) -> {"answer": str, "rounds": int, "scores": list[int]}
   - 초안 생성 → Grade 로 평가 → 기준 미달이면 피드백 반영해 재작성. max_rounds 를 넘기지 않는다.
"""

from __future__ import annotations

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


class Route(BaseModel):
    category: Literal["billing", "tech", "general"] = Field(description="문의 유형")


class Grade(BaseModel):
    score: int = Field(description="1~10 품질 점수")
    feedback: str = Field(description="개선 피드백")


SYSTEM_PROMPTS = {
    "billing": "너는 결제/환불 전문 상담원이야. 정책을 근거로 짧게 답해.",
    "tech": "너는 기술지원 엔지니어야. 재현 단계와 해결책을 짧게 안내해.",
    "general": "너는 친절한 안내 직원이야. 짧게 답해.",
}


def classify(question: str) -> str:
    router = llm.with_structured_output(Route)
    result = router.invoke(
        [
            SystemMessage("고객 문의를 billing(결제) / tech(기술) / general(기타) 중 하나로 분류해."),
            HumanMessage(question),
        ]
    )
    return result.category


def handle(question: str) -> dict[str, str]:
    category = classify(question)
    reply = llm.invoke([SystemMessage(SYSTEM_PROMPTS[category]), HumanMessage(question)])
    return {"category": category, "answer": reply.text}


def refine(task: str, threshold: int = 7, max_rounds: int = 3) -> dict:
    evaluator = llm.with_structured_output(Grade)
    draft = llm.invoke(task).text
    scores: list[int] = []
    for round_no in range(1, max_rounds + 1):
        grade = evaluator.invoke(f"과제: {task}\n답안: {draft}\n1~10점으로 평가하고 피드백을 줘.")
        scores.append(grade.score)
        if grade.score >= threshold:
            return {"answer": draft, "rounds": round_no, "scores": scores}
        draft = llm.invoke(f"과제: {task}\n이전 답안: {draft}\n피드백: {grade.feedback}\n개선해줘.").text
    return {"answer": draft, "rounds": max_rounds, "scores": scores}


if __name__ == "__main__":
    q1 = "tech: 비밀번호 재설정 메일이 오지 않아요"
    q2 = "billing: 카드 결제가 두 번 청구됐어요"
    print("분류:", classify(q1), "/", classify(q2))
    r = handle(q1)
    print("처리:", r["category"], "→", r["answer"][:60])
    out = refine("RAG를 한 문장으로 설명해줘", threshold=7, max_rounds=3)
    print("개선 루프:", out["rounds"], "라운드, 점수", out["scores"])

    # --- 자가 채점 ---
    assert classify(q1) == "tech"
    assert classify(q2) == "billing"
    assert r["category"] in SYSTEM_PROMPTS and isinstance(r["answer"], str) and r["answer"]
    assert 1 <= out["rounds"] <= 3, "반복 상한을 지켜야 합니다"
    assert len(out["scores"]) == out["rounds"], "라운드마다 점수를 기록해야 합니다"
    assert all(isinstance(s, int) for s in out["scores"])
    assert isinstance(out["answer"], str) and out["answer"]
    print("✅ 모든 테스트 통과!")
