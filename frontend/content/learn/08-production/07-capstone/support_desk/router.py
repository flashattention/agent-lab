"""라우터: 규칙 기반 빠른 경로 → 애매하면 작은 LLM 의 구조화 출력 (8.6강 비용 최적화).

  "환불/주문/배송 언제" → order    (도구가 필요한 업무)
  "정책/규정/어떻게"    → faq      (RAG)
  "안녕/고마워"         → smalltalk (도구 없음, 작은 모델)
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from .config import SETTINGS

Route = Literal["faq", "order", "smalltalk"]

ORDER_ID = r"\b[A-Z]-\d{4}\b"

# 순서가 곧 우선순위다. 주문 번호가 있으면 무조건 업무(order), 그다음 정책 질문, 업무 키워드, 인사 순.
_RULES: list[tuple[Route, str]] = [
    ("order", ORDER_ID),
    ("faq", r"(정책|규정|기간|어떻게|가능한가|멤버십|배송비|policy|faq)"),
    ("order", r"(주문|환불|반품|취소|배송\s*(언제|조회|어디)|order|refund)"),
    ("smalltalk", r"^(안녕|고마|감사|ㅎㅇ|hi|hello|thanks)"),
]


def rule_route(text: str) -> Route | None:
    """첫 번째로 맞는 규칙의 경로. 없으면 None (→ LLM 라우터)."""
    for route, pattern in _RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return route
    return None


class RouteDecision(BaseModel):
    """LLM 라우터 출력 스키마. 근거를 먼저 쓰게 한다."""

    reason: str = Field(description="분류 근거 한 문장")
    route: Route = Field(description="faq=정책 질문, order=주문·환불 업무, smalltalk=인사·잡담")


ROUTER_PROMPT = (
    "고객 메시지를 분류하라. faq: 정책/규정 질문, order: 특정 주문 조회·환불 등 업무 처리, "
    "smalltalk: 인사·감사·잡담."
)


@lru_cache(maxsize=1)
def _router_llm():
    return init_chat_model(SETTINGS.small_model).with_structured_output(RouteDecision)


def llm_route(text: str) -> RouteDecision:
    return _router_llm().invoke([("system", ROUTER_PROMPT), ("human", text)])
