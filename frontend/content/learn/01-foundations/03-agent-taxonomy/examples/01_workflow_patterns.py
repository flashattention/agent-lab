"""워크플로 패턴 3종: Prompt chaining, Routing, Parallelization.

Anthropic "Building effective agents" 의 분류를 LangChain 채팅 모델로 최소 구현한다.
LangGraph 를 쓰면 더 견고하게 만들 수 있지만(→ 4장), 여기서는 순수 Python 제어 흐름으로
'개발자가 경로를 정한다'는 워크플로의 본질에 집중한다.
"""

from __future__ import annotations

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def short(text: str, n: int = 70) -> str:
    """출력용: 줄바꿈을 없애고 n 글자로 자른다."""
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + "…"


def section(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


# ---------------------------------------------------------------------------
# 1) Prompt chaining: 작업을 고정된 단계로 나누고, 단계 사이에 '게이트(검사)'를 둔다
# ---------------------------------------------------------------------------
def prompt_chain(topic: str) -> str:
    outline = llm.invoke(f"'{topic}' 블로그 글의 개요를 3줄로 써줘.").text
    print("① 개요:", short(outline))

    # 게이트: 코드로 검사해서 통과 못 하면 조기 종료 (LLM 호출 낭비 방지)
    if len(outline.strip()) < 5:
        return "개요 생성 실패 → 중단"

    draft = llm.invoke(f"다음 개요로 짧은 글을 써줘:\n{outline}").text
    print("② 초안:", short(draft))
    polished = llm.invoke(f"다음 글을 더 간결하게 다듬어줘:\n{draft}").text
    print("③ 퇴고:", short(polished))
    return polished


# ---------------------------------------------------------------------------
# 2) Routing: LLM 이 입력을 분류하고, 분류에 따라 '전문 처리기'로 보낸다
# ---------------------------------------------------------------------------
class Route(BaseModel):
    """고객 문의 분류 결과."""

    category: Literal["billing", "tech", "general"] = Field(description="문의 유형")


router = llm.with_structured_output(Route)  # 출력 형식을 스키마로 강제 (→ 2.3)

HANDLERS = {
    "billing": lambda q: f"[결제팀 프롬프트로 처리] {q}",
    "tech": lambda q: f"[기술지원 프롬프트 + 문서검색으로 처리] {q}",
    "general": lambda q: f"[일반 상담 프롬프트로 처리] {q}",
}


def route(question: str) -> str:
    # 분류 지침은 system 에, 사용자 원문은 human 에 넣는다 (지침과 데이터 분리)
    category = router.invoke(
        [
            SystemMessage("고객 문의를 billing(결제) / tech(기술) / general(기타) 중 하나로 분류해."),
            HumanMessage(question),
        ]
    ).category
    print(f"  분류={category:<8} ← {question}")
    return HANDLERS[category](question)


# ---------------------------------------------------------------------------
# 3) Parallelization: 독립적인 작업을 동시에 실행
#    - Sectioning: 서로 다른 관점을 병렬로
#    - Voting: 같은 작업을 여러 번 시켜 다수결
# ---------------------------------------------------------------------------
def parallel_review(code: str) -> dict[str, str]:
    aspects = ["보안", "성능", "가독성"]
    prompts = [f"다음 코드를 {a} 관점에서만 한 줄로 리뷰해:\n{code}" for a in aspects]
    results = llm.batch(prompts, config={"max_concurrency": 3})  # 동시에 실행
    return {a: r.text for a, r in zip(aspects, results)}


class Vote(BaseModel):
    is_spam: bool = Field(description="스팸이면 True")


def vote_spam(text: str, n: int = 3) -> bool:
    voter = llm.with_structured_output(Vote)
    votes = voter.batch([f"이 메시지가 스팸인지 판단해: {text}"] * n)
    yes = sum(v.is_spam for v in votes)
    print(f"  투표 결과: 스팸 {yes} / {n}")
    return yes > n // 2


if __name__ == "__main__":
    section("1) Prompt chaining — 개요 → 초안 → 퇴고")
    prompt_chain("AI 에이전트 입문")

    section("2) Routing — 분류 후 전문 처리기로")
    for q in ["billing: 이번 달 결제가 두 번 됐어요", "tech: 앱이 실행되자마자 꺼져요", "general: 영업시간이 언제인가요?"]:
        print("  →", route(q))

    section("3-a) Parallelization (Sectioning) — 관점별 병렬 리뷰")
    for aspect, review in parallel_review("def f(x): return eval(x)").items():
        print(f"  [{aspect}] {short(review)}")

    section("3-b) Parallelization (Voting) — 다수결")
    print("  최종 판정:", "스팸" if vote_spam("지금 클릭하면 100만원 당첨!") else "정상")
