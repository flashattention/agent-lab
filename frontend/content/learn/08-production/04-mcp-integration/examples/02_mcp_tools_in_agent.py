"""MCP 도구를 LangChain 에이전트에 연결한다.

A) langchain.mcp.MCPAdapter (beta) — 서버 연결 → MCP 도구 발견 → LangChain 도구로 변환
B) 도구 주석(annotations)으로 '정책'을 자동 구성
     readOnlyHint=True   → 자동 실행
     destructiveHint=True → HumanInTheLoopMiddleware 로 승인 필요
C) 에이전트 실행 (MCP 도구는 비동기 전용 → ainvoke/astream 사용)
D) 어댑터가 내부에서 하는 일을 손으로 재현 (StructuredTool + client.call_tool)
"""

from __future__ import annotations

import asyncio
import os
import warnings

from fastmcp import Client
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import ToolMessage
from langchain_core._api import LangChainBetaWarning
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from shop_mcp_server import mcp

# langchain.mcp 는 beta 네임스페이스라 import 시 경고를 낸다. 알고 쓰는 것이므로 끈다.
warnings.filterwarnings("ignore", category=LangChainBetaWarning)
from langchain.mcp import MCPAdapter  # noqa: E402

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def annotations_of(t: BaseTool) -> dict:
    """MCPAdapter 가 넣어 둔 MCP 메타데이터에서 도구 주석을 꺼낸다."""
    return ((t.metadata or {}).get("mcp", {}).get("tool", {}) or {}).get("annotations", {})


async def main() -> None:
    # ------------------------------------------------------------ A) 발견 + 변환
    print("=" * 70 + "\nA) MCPAdapter 로 MCP 도구 → LangChain 도구\n" + "=" * 70)
    async with MCPAdapter(mcp) as adapter:  # 실서비스: MCPAdapter("https://.../mcp")
        tools = await adapter.list_tools()
    for t in tools:
        print(f"🔧 {t.name:<18} args={list(t.args)} annotations={annotations_of(t)}")
        print(f"   server={t.metadata['mcp']['server']['name']}  (출처 추적 → 감사 로그에 활용)")

    # ------------------------------------------------------------ B) 주석 기반 정책
    destructive = [t.name for t in tools if annotations_of(t).get("destructive_hint")]
    print("\n승인이 필요한 도구:", destructive)
    agent = create_agent(
        MODEL,
        tools=tools,
        system_prompt="쇼핑몰 상담원. 도구 에러 메시지를 읽고 필요하면 고쳐서 다시 시도해라.",
        middleware=[HumanInTheLoopMiddleware(interrupt_on={name: True for name in destructive})],
        checkpointer=InMemorySaver(),
    )

    # ------------------------------------------------------------ C) 실행
    print("\n" + "=" * 70 + "\nC-1) 읽기 도구: order 상태 조회 (자동 실행)\n" + "=" * 70)
    cfg = {"configurable": {"thread_id": "mcp-1"}}
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "order A-100 status 알려줘"}]}, cfg)
    for m in out["messages"]:
        if isinstance(m, ToolMessage):
            # 서버가 ToolError 를 내면 status="error" ToolMessage 로 모델에게 전달된다 (모델이 고쳐서 재시도 가능)
            print(f"   ToolMessage(status={m.status}): {m.content[0]['text'][:70]}")
    print("최종:", str(out["messages"][-1].content)[:90])

    print("\n" + "=" * 70 + "\nC-2) 쓰기 도구: 반품 return 접수 (승인 필요)\n" + "=" * 70)
    cfg = {"configurable": {"thread_id": "mcp-2"}}
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "return 접수해줘"}]}, cfg, version="v2")
    req = out.interrupts[0].value["action_requests"][0]
    print("승인 요청:", req["name"], req["args"])
    # 상담원이 인자를 올바른 주문번호로 고쳐서 승인(edit)
    fixed = {"type": "edit", "edited_action": {"name": req["name"], "args": {"order_id": "A-200", "reason": "불량"}}}
    out = await agent.ainvoke(Command(resume={"decisions": [fixed]}), cfg, version="v2")
    tool_msg = [m for m in out.value["messages"] if isinstance(m, ToolMessage)][-1]
    # edit 결정이면 미들웨어가 '사람이 인자를 바꿨다'는 안내문을 결과 앞에 붙여 모델에게 알려 준다
    print("도구 결과(앞부분):", str(tool_msg.content)[:90], "…")
    print("구조화 결과(artifact):", tool_msg.artifact["structured_content"])

    # ------------------------------------------------------------ D) 수동 변환
    print("\n" + "=" * 70 + "\nD) 어댑터 없이 직접 변환하기 (내부 원리)\n" + "=" * 70)
    client = Client(mcp)
    async with client:
        mcp_tools = await client.list_tools()

    def to_langchain(mt) -> StructuredTool:
        async def _call(**kwargs):
            async with client:  # FastMCP Client 는 재진입 가능 → 호출마다 연결을 열어도 된다
                res = await client.call_tool(mt.name, kwargs, raise_on_error=False)
            return ("ERROR: " if res.is_error else "") + res.content[0].text

        return StructuredTool(
            name=mt.name,
            description=mt.description or "",
            args_schema=mt.input_schema,  # JSON Schema dict 를 그대로 쓸 수 있다
            coroutine=_call,
        )

    manual = [to_langchain(mt) for mt in mcp_tools]
    print("수동 변환 도구:", [t.name for t in manual])
    print("직접 호출:", await manual[0].ainvoke({"order_id": "A-200"}))


asyncio.run(main())
