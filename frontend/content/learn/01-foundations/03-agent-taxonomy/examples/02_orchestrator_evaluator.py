"""워크플로 패턴 2종: Orchestrator-workers, Evaluator-optimizer.

- Orchestrator-workers: 하위 작업 목록을 '미리' 알 수 없을 때, LLM 이 작업을 쪼개고 워커들이 처리한다.
- Evaluator-optimizer: 생성 → 평가 → 피드백 반영을 반복한다. 반드시 반복 상한을 둔다.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def short(text: str, n: int = 70) -> str:
    """출력용: 줄바꿈을 없애고 n 글자로 자른다."""
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------------------------
# 1) Orchestrator-workers
# ---------------------------------------------------------------------------
class Plan(BaseModel):
    """오케스트레이터가 만든 하위 작업 목록."""

    subtasks: list[str] = Field(description="서로 독립적으로 처리 가능한 하위 작업들 (2~4개)")


def orchestrate(request: str) -> str:
    # ① 오케스트레이터: 작업 분해 (몇 개로 나뉠지 실행 전에는 모른다 — 워크플로와의 차이)
    plan = llm.with_structured_output(Plan).invoke(f"다음 요청을 하위 작업으로 나눠: {request}")
    subtasks = plan.subtasks[:4]  # 상한: 워커 수 폭증 방지
    print(f"🧭 오케스트레이터가 {len(subtasks)}개 하위 작업 생성")

    # ② 워커: 하위 작업을 병렬 처리
    outputs = llm.batch([f"다음 하위 작업을 수행해: {t}" for t in subtasks])
    for i, (t, o) in enumerate(zip(subtasks, outputs), 1):
        print(f"  👷 worker {i}: {short(t, 30)} → {short(o.text, 40)}")

    # ③ 종합(synthesizer)
    merged = "\n".join(f"- {o.text}" for o in outputs)
    return llm.invoke(f"다음 결과들을 하나의 답으로 종합해:\n{merged}").text


# ---------------------------------------------------------------------------
# 2) Evaluator-optimizer
# ---------------------------------------------------------------------------
class Grade(BaseModel):
    """평가자 출력."""

    score: int = Field(description="1~10 품질 점수")
    feedback: str = Field(description="개선을 위한 구체적 피드백")


def evaluator_optimizer(task: str, threshold: int = 7, max_rounds: int = 3) -> tuple[str, int]:
    evaluator = llm.with_structured_output(Grade)
    draft = llm.invoke(task).text
    for round_no in range(1, max_rounds + 1):  # 반복 상한 필수
        grade = evaluator.invoke(f"과제: {task}\n답안: {draft}\n1~10점으로 평가하고 피드백을 줘.")
        print(f"  🔁 round {round_no}: score={grade.score} feedback={short(grade.feedback, 40)}")
        if grade.score >= threshold:  # 품질 기준 통과 → 종료
            return draft, round_no
        draft = llm.invoke(f"과제: {task}\n이전 답안: {draft}\n피드백: {grade.feedback}\n개선해서 다시 써줘.").text
    return draft, max_rounds  # 상한 도달: 최선의 결과를 반환 (현업에서는 사람 검토로 넘기기도 함)


if __name__ == "__main__":
    print("=" * 64 + "\n1) Orchestrator-workers\n" + "=" * 64)
    final = orchestrate("우리 회사 신규 AI 고객지원 도입 보고서를 작성해줘")
    print("📄 종합:", short(final, 90))

    print("\n" + "=" * 64 + "\n2) Evaluator-optimizer\n" + "=" * 64)
    answer, rounds = evaluator_optimizer("'에이전트'를 초등학생에게 두 문장으로 설명해줘")
    print(f"✅ {rounds}라운드 만에 종료 → {short(answer, 80)}")
