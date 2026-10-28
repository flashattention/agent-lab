"""여러 MCP 서버를 하나의 에이전트에 연결하기.

방법 1) ClientGroup — 클라이언트 쪽에서 여러 서버 연결을 묶는다. 도구 이름 앞에 '서버이름_' 접두사.
방법 2) mount     — 서버 쪽에서 게이트웨이 서버 하나에 여러 서버를 붙인다(namespace).
추가) 서버 미들웨어 — 모든 도구 호출을 가로채 감사 로그(audit log)를 남긴다.

그리고 도구가 많아질 때의 실무 문제: 도구 이름 충돌, 컨텍스트 낭비, 권한 범위.
"""

from __future__ import annotations

import asyncio
import os
import warnings

from fastmcp import Client, FastMCP
from fastmcp.client.group import ClientGroup
from fastmcp.server.middleware import Middleware, MiddlewareContext
from langchain.agents import create_agent
from langchain.messages import AIMessage
from langchain_core._api import LangChainBetaWarning
from shop_mcp_server import mcp as shop

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
from langchain.mcp import MCPAdapter  # noqa: E402

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# ------------------------------------------------------------ 두 번째 서버: CRM
crm = FastMCP("crm", instructions="고객 등급과 상담 이력")


@crm.tool(annotations={"readOnlyHint": True})
def get_customer(customer_id: str) -> dict:
    """고객 customer 등급과 누적 구매액을 조회한다."""
    return {"customer_id": customer_id, "tier": "VIP", "lifetime_value": 2_400_000}


@crm.tool(annotations={"readOnlyHint": True})
def get_order_status(order_id: str) -> str:
    """(CRM 쪽) 주문 메모를 조회한다. — shop 서버와 이름이 같다!"""
    return f"{order_id}: 고객이 배송 지연을 두 번 문의함"


# ------------------------------------------------------------ 서버 미들웨어: 감사 로그
AUDIT_LOG: list[dict] = []


class AuditMiddleware(Middleware):
    """모든 tools/call 을 기록한다. 실무에서는 변경 불가 저장소로 보낸다."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        AUDIT_LOG.append({"tool": context.message.name, "args": dict(context.message.arguments or {})})
        return await call_next(context)


async def main() -> None:
    print("=" * 70 + "\n방법 1) ClientGroup — 클라이언트에서 여러 서버 묶기\n" + "=" * 70)
    group = ClientGroup({"shop": Client(shop), "crm": Client(crm)})
    async with MCPAdapter(group) as adapter:
        tools = await adapter.list_tools()
    for t in tools:
        print(f"🔧 {t.name:<24} ← server={t.metadata['mcp']['server']['name']}")
    # 같은 이름(get_order_status)이 서버 접두사 덕분에 충돌하지 않는다

    agent = create_agent(MODEL, tools=tools)
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "customer C-7 등급 알려줘"}]})
    called = [tc["name"] for m in out["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    print("에이전트가 호출한 도구:", called)

    print("\n" + "=" * 70 + "\n방법 2) mount — 게이트웨이 서버 하나로 합치기 + 감사 미들웨어\n" + "=" * 70)
    gateway = FastMCP("gateway", middleware=[AuditMiddleware()])
    gateway.mount(shop, namespace="shop")
    gateway.mount(crm, namespace="crm")
    async with Client(gateway) as client:
        names = [t.name for t in await client.list_tools()]
        print("게이트웨이 도구:", names)
        await client.call_tool("crm_get_customer", {"customer_id": "C-7"})
        await client.call_tool("shop_get_order_status", {"order_id": "A-100"})
        # mount 하면 리소스 URI 에도 네임스페이스가 들어간다
        templates = [rt.uri_template for rt in await client.list_resource_templates()]
        print("리소스 템플릿:", templates)
    print("감사 로그:", AUDIT_LOG)
    assert len(AUDIT_LOG) == 2

    print("\n" + "=" * 70 + "\n실무 팁) 읽기 전용 도구만 골라 '조회 전용 에이전트' 만들기\n" + "=" * 70)
    read_only = [t for t in tools if t.metadata["mcp"].get("tool", {}).get("annotations", {}).get("read_only_hint")]
    print("조회 전용 에이전트 도구:", [t.name for t in read_only])


asyncio.run(main())
