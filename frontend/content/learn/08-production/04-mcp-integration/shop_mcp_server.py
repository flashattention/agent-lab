"""쇼핑몰 MCP 서버 (FastMCP).

이 파일 하나가 'MCP 서버'다. 세 가지 기본 요소(primitive)를 모두 제공한다.

  Tools     : 모델이 호출하는 함수        → get_order_status, create_return
  Resources : 앱이 읽어 컨텍스트로 쓰는 데이터 → policy://refund, orders://{order_id}/receipt
  Prompts   : 재사용 가능한 프롬프트 템플릿  → triage_ticket

실행 방법 (참고 — 이 강의의 예제들은 서버를 띄우지 않고 in-memory 로 연결한다)
  fastmcp run shop_mcp_server.py                         # stdio
  fastmcp run shop_mcp_server.py --transport http --port 8000   # Streamable HTTP
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

mcp = FastMCP(
    name="shop",
    instructions="ACME 쇼핑몰의 주문 조회와 반품 접수를 담당하는 서버입니다.",
)

ORDERS: dict[str, dict] = {
    "A-100": {"status": "배송 중", "amount": 39_000, "item": "무선 이어폰"},
    "A-200": {"status": "배송 완료", "amount": 129_000, "item": "기계식 키보드"},
}


# ----------------------------------------------------------------- Tools
@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": False},  # 읽기 전용 → 자동 실행해도 안전
    tags={"read"},
)
def get_order_status(
    order_id: Annotated[str, Field(description="주문 번호. 예: A-100")],
) -> dict:
    """주문 order 의 배송 상태와 금액을 조회한다."""
    order = ORDERS.get(order_id)
    if order is None:
        # ToolError 의 메시지는 클라이언트(모델)에게 그대로 전달된다 → 모델이 스스로 고칠 수 있다
        raise ToolError(f"주문 {order_id} 을(를) 찾을 수 없습니다. 주문 번호 형식은 A-000 입니다.")
    return {"order_id": order_id, **order}


@mcp.tool(
    annotations={"destructiveHint": True, "idempotentHint": False},  # 쓰기 작업 → 승인 대상
    tags={"write"},
)
async def create_return(
    order_id: Annotated[str, Field(description="반품할 주문 번호")],
    reason: Annotated[str, Field(description="반품 사유")],
    ctx: Context,  # 서버 쪽 컨텍스트: 진행률 보고 등 (LLM 스키마에는 노출되지 않음)
) -> dict:
    """주문에 대한 반품 return 을 접수한다."""
    await ctx.report_progress(1, 2, "반품 가능 여부 확인")
    if order_id not in ORDERS:
        raise ToolError(f"주문 {order_id} 이(가) 없습니다.")
    await ctx.report_progress(2, 2, "반품 접수 완료")
    return {"return_id": f"R-{order_id}", "order_id": order_id, "reason": reason, "status": "접수"}


# ----------------------------------------------------------------- Resources
@mcp.resource("policy://refund", mime_type="text/markdown")
def refund_policy() -> str:
    """환불·반품 정책 문서."""
    return "# 환불 정책\n- 수령 후 7일 이내 반품 가능\n- 단순 변심은 왕복 배송비 6,000원 고객 부담"


@mcp.resource("orders://{order_id}/receipt")
def order_receipt(order_id: str) -> str:
    """주문 영수증 (리소스 템플릿: URI 의 일부가 파라미터)."""
    o = ORDERS.get(order_id, {})
    return f"영수증 {order_id}: {o.get('item', '?')} {o.get('amount', 0):,}원"


# ----------------------------------------------------------------- Prompts
@mcp.prompt
def triage_ticket(ticket: str) -> str:
    """고객 문의를 분류하는 표준 프롬프트."""
    return f"다음 고객 문의를 [배송, 반품, 결제, 기타] 중 하나로 분류하고 근거를 한 줄로 써라.\n\n문의: {ticket}"
