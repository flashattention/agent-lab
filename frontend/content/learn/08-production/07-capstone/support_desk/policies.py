"""가드레일과 비즈니스 정책 (8.3강).

- detect_injection     : 입력 가드 (그래프의 guard 노드에서 사용)
- decide_refund        : 환불 자동 승인/사람 검토 판정 — 순수 함수라 단위 테스트가 쉽다
- refund_approval      : wrap_tool_call 미들웨어. 검토가 필요하면 interrupt() 로 사람에게 묻는다
- pii_middlewares      : 이메일·카드·전화번호 마스킹
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from langchain.agents.middleware import PIIMiddleware, ToolCallRequest, wrap_tool_call
from langchain.messages import ToolMessage
from langgraph.types import Command, interrupt

from .config import SETTINGS
from .data import ORDERS

# ------------------------------------------------------------------ 입력 가드
_INJECTION = [
    r"ignore (all |the )?(previous|above|prior) instructions",
    r"(이전|위의?) ?(지시|명령|지침)\S* ?(모두 )?무시",
    r"system prompt",
    r"시스템 ?프롬프트",
    r"developer mode",
]


def detect_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(p, lowered) for p in _INJECTION)


# ------------------------------------------------------------------ 환불 정책
Decision = Literal["auto", "review"]


def decide_refund(order_id: str, amount: int, user_id: str, tier: str, reason: str = "") -> tuple[Decision, str]:
    """환불 요청을 자동 처리할지, 사람이 검토할지 결정한다. (reason 은 정책 확장용 — 실습에서 사용)

    자동 승인 조건 (모두 만족):
      1) 본인 주문  2) 배송 완료 후 7일 이내  3) 금액 ≤ 한도 (VIP 는 상향 한도)
    """
    order = ORDERS.get(order_id)
    if order is None or order["customer"] != user_id:
        return "review", "주문 확인 불가 (번호 오류 또는 타인 주문)"
    days = order["days_since_delivery"]
    if days is None:
        return "review", "아직 배송 중인 주문"
    if days > 7:
        return "review", f"환불 기간 초과 (수령 후 {days}일)"
    limit = SETTINGS.vip_auto_refund_limit if tier == "VIP" else SETTINGS.auto_refund_limit
    if amount > limit:
        return "review", f"자동 승인 한도 초과 ({amount:,}원 > {limit:,}원)"
    return "auto", "정책 범위 내 자동 승인"


@wrap_tool_call
def refund_approval(request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage | Command]):
    """request_refund 호출을 가로채 정책을 적용한다. (interrupt 앞에는 부수효과를 두지 않는다!)"""
    call = request.tool_call
    if call["name"] != "request_refund":
        return handler(request)

    ctx = request.runtime.context
    args = call["args"]
    # 전역 이름은 호출 시점에 조회되므로 policies.decide_refund 를 교체(A/B 실험, 실습)하면 바로 반영된다
    decision, why = decide_refund(
        args.get("order_id", ""), int(args.get("amount", 0)), ctx.user_id, ctx.tier, str(args.get("reason", ""))
    )
    if decision == "auto":
        return handler(request)

    answer = interrupt({
        "type": "refund_review",
        "user_id": ctx.user_id,
        "tier": ctx.tier,
        "request": args,
        "reason": why,
        "allowed": ["approve", "edit", "reject"],
    })
    kind = answer.get("type")
    if kind == "approve":
        return handler(request)
    if kind == "edit":
        edited = {**call, "args": {**args, **answer.get("args", {})}}
        return handler(request.override(tool_call=edited))
    return ToolMessage(
        content=f"상담원이 환불을 거절했습니다: {answer.get('message', '정책 위반')}. 고객에게 사유를 정중히 안내하세요.",
        tool_call_id=call["id"], name=call["name"], status="error",
    )


# ------------------------------------------------------------------ PII
KR_PHONE = r"01[016789]-?\d{3,4}-?\d{4}"


def pii_middlewares() -> list[PIIMiddleware]:
    return [
        PIIMiddleware("email", strategy="redact"),
        PIIMiddleware("credit_card", strategy="mask"),
        PIIMiddleware("kr_phone", detector=KR_PHONE, strategy="redact"),
    ]
