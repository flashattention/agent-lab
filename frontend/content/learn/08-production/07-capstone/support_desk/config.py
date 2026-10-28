"""설정 한 곳에 모으기 — 환경변수로 덮어쓸 수 있는 값들.

현업에서는 pydantic-settings 등으로 검증하고, 환경(dev/staging/prod)별로 다르게 주입한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # 모델: 라우터·요약처럼 쉬운 일은 작은 모델, 상담 답변은 기본 모델
    model: str = field(default_factory=lambda: os.getenv("LAB_MODEL", "openai:gpt-5-mini"))
    small_model: str = field(default_factory=lambda: os.getenv("LAB_SMALL_MODEL", "openai:gpt-5-nano"))
    embedding_model: str = "text-embedding-3-small"

    # 정책
    auto_refund_limit: int = 50_000  # 원. 이하이고 본인 주문이면 자동 환불
    vip_auto_refund_limit: int = 100_000  # VIP 고객은 자동 한도 상향

    # 안전장치
    model_call_limit: int = 6  # 전문가 에이전트 1회 실행당 모델 호출 상한
    summarize_after_messages: int = 40  # 대화가 길어지면 요약
    retrieval_k: int = 2


SETTINGS = Settings()
