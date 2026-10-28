"""MCP 클라이언트로 서버의 Tools / Resources / Prompts 를 직접 다뤄 본다.

fastmcp.Client(서버객체) 처럼 FastMCP 인스턴스를 그대로 넘기면 'in-memory 전송'으로 연결된다.
프로세스도 포트도 없다. 테스트와 학습에 이상적이고, 프로토콜 메시지는 실제 전송과 동일하다.

  Client(mcp)                         ← in-memory (이 예제)
  Client(Path("shop_mcp_server.py"))  ← stdio 로 서브프로세스 실행
  Client("https://api.acme.com/mcp")  ← Streamable HTTP 원격 서버
"""

from __future__ import annotations

import asyncio

from fastmcp import Client
from fastmcp.exceptions import ToolError
from shop_mcp_server import mcp


async def on_progress(progress: float, total: float | None, message: str | None) -> None:
    """서버가 ctx.report_progress() 로 보낸 진행률을 받는 콜백."""
    print(f"   ⏳ progress {progress:.0f}/{total:.0f} {message or ''}")


async def main() -> None:
    async with Client(mcp, progress_handler=on_progress) as client:
        print("=" * 70 + "\n1) 초기화(initialize) — 서버 정보와 능력(capabilities) 교환\n" + "=" * 70)
        print("서버 정보       :", client.server_info.name if client.server_info else None)
        print("프로토콜 버전   :", client.protocol_version)
        print("서버 instructions:", client.instructions)

        print("\n" + "=" * 70 + "\n2) tools/list — 도구 목록 + JSON 스키마 + 주석(annotations)\n" + "=" * 70)
        for t in await client.list_tools():
            ann = t.annotations
            print(f"🔧 {t.name}: {t.description}")
            print(f"   input_schema.properties = {list(t.input_schema['properties'])}")
            print(f"   readOnly={ann.read_only_hint} destructive={ann.destructive_hint}")

        print("\n" + "=" * 70 + "\n3) tools/call — 정상 호출과 에러 호출\n" + "=" * 70)
        ok = await client.call_tool("get_order_status", {"order_id": "A-100"})
        print("structured :", ok.structured_content)  # 구조화된 결과 (output schema 기반)
        print("text       :", ok.content[0].text)      # 모델에게 보낼 텍스트 표현
        try:
            await client.call_tool("get_order_status", {"order_id": "Z-9"})
        except ToolError as e:
            print("ToolError  :", e)  # raise_on_error=True(기본)면 예외로 받는다
        bad = await client.call_tool("get_order_status", {"order_id": "Z-9"}, raise_on_error=False)
        print("is_error   :", bad.is_error, "→ 에이전트는 이 메시지를 보고 스스로 재시도할 수 있다")

        print("\n진행률을 보고하는 도구 호출:")
        ret = await client.call_tool("create_return", {"order_id": "A-200", "reason": "사이즈 불만"})
        print("결과:", ret.data)

        print("\n" + "=" * 70 + "\n4) resources — 정적 리소스와 리소스 템플릿\n" + "=" * 70)
        for r in await client.list_resources():
            print("📄", r.uri, r.mime_type)
        for rt in await client.list_resource_templates():
            print("🧩", rt.uri_template)
        policy = await client.read_resource("policy://refund")
        print(policy[0].text)
        receipt = await client.read_resource("orders://A-200/receipt")
        print(receipt[0].text)

        print("\n" + "=" * 70 + "\n5) prompts — 서버가 제공하는 프롬프트 템플릿\n" + "=" * 70)
        prompts = await client.list_prompts()
        print("prompts:", [p.name for p in prompts])
        rendered = await client.get_prompt("triage_ticket", {"ticket": "키보드가 안 와요"})
        print(rendered.messages[0].content.text)


asyncio.run(main())
