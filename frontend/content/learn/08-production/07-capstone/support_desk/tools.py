"""상담 도구들.

설계 원칙 (2.4강 + 8.3강)
- 도구는 '누가' 호출하는지 runtime.context 로 안다. 사용자 ID 를 인자로 받지 않는다(위조 방지).
- 남의 주문은 조회·환불할 수 없다 — 권한 검사는 도구 안에서 결정적으로.
- 에러는 모델이 고칠 수 있는 문장으로 돌려준다.
- 쓰기 도구(request_refund)는 policies.refund_approval 미들웨어가 승인 정책을 적용한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.tools import ToolRuntime, tool

from .data import ORDERS
from .knowledge import format_docs, search_policies


@dataclass
class SupportContext:
    """요청마다 서버가 인증 정보로 채우는 컨텍스트 (LLM 이 바꿀 수 없음)."""

    user_id: str
    tier: str = "STANDARD"
    channel: str = "web"


# ------------------------------------------------------------------ FAQ / RAG
@tool
def search_policy(query: str, runtime: ToolRuntime[SupportContext]) -> str:
    """환불·교환·배송·멤버십 정책 policy 문서를 검색한다. 정책 질문에는 반드시 먼저 사용한다."""
    runtime.stream_writer({"tool": "search_policy", "status": "정책 문서 검색 중"})
    return format_docs(search_policies(query))


# ------------------------------------------------------------------ 주문
@tool
def list_my_orders(runtime: ToolRuntime[SupportContext]) -> str:
    """현재 고객의 주문 order 목록을 조회한다. 주문 번호를 모를 때 먼저 사용한다."""
    mine = {oid: o for oid, o in ORDERS.items() if o["customer"] == runtime.context.user_id}
    if not mine:
        return "주문 내역이 없습니다."
    return "\n".join(f"{oid}: {o['item']} {o['amount']:,}원 ({o['status']})" for oid, o in mine.items())


@tool
def lookup_order(order_id: str, runtime: ToolRuntime[SupportContext]) -> str:
    """주문 번호(예: A-1001)로 주문 order 상세 상태를 조회한다."""
    order = ORDERS.get(order_id)
    if order is None or order["customer"] != runtime.context.user_id:
        # 존재 여부를 구분해 알려 주지 않는다(남의 주문 번호 탐색 방지)
        return f"주문 {order_id} 을(를) 찾을 수 없습니다. list_my_orders 로 주문 번호를 확인하세요."
    return f"{order_id}: {order['item']} / {order['amount']:,}원 / {order['status']}"


@tool
def request_refund(order_id: str, amount: int, reason: str, runtime: ToolRuntime[SupportContext]) -> str:
    """주문에 대한 환불 refund 을 실행한다. amount 는 원 단위 정수."""
    # 여기까지 왔다면 policies.refund_approval 이 자동 승인했거나 사람이 승인한 것이다.
    runtime.stream_writer({"tool": "request_refund", "status": "결제사 환불 API 호출 중"})
    order = ORDERS.get(order_id)
    if order is None or order["customer"] != runtime.context.user_id:
        return f"환불 실패: 주문 {order_id} 을(를) 찾을 수 없습니다."
    if amount > order["amount"]:
        return f"환불 실패: 요청 금액 {amount:,}원이 결제 금액 {order['amount']:,}원을 초과합니다."
    return f"환불 접수 완료: {order_id} {amount:,}원 (사유: {reason}). 영업일 3일 내 카드사로 환불됩니다."


@tool
def escalate_to_human(summary: str) -> str:
    """상담원 human 연결이 필요할 때 티켓을 만든다. 화난 고객, 정책 밖 요청, 반복 실패 시 사용."""
    return f"상담원 연결 티켓이 생성되었습니다. (요약: {summary[:60]})"


FAQ_TOOLS = [search_policy, escalate_to_human]
ORDER_TOOLS = [list_my_orders, lookup_order, request_refund, search_policy, escalate_to_human]
