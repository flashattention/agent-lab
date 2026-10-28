"""[실습] 재고(inventory) MCP 서버를 만들고 에이전트에 연결하기

과제
1. FastMCP 서버 `inventory` 에 도구 두 개를 등록하라.
   - check_stock(sku: str) -> dict   : {"sku": sku, "qty": 재고} 반환. annotations={"readOnlyHint": True}
   - reserve_stock(sku: str, qty: int) -> dict : 재고 차감. 재고 부족이면 ToolError.
     annotations={"destructiveHint": True}
2. 리소스 "inventory://warehouses" 를 등록하라. 창고 목록 문자열을 반환한다.
3. split_by_risk(tools) 를 완성하라. MCPAdapter 가 만든 LangChain 도구들을
   (안전한 도구 이름 목록, 위험한 도구 이름 목록) 으로 나눈다.
   위험 = metadata["mcp"]["tool"]["annotations"] 의 destructive_hint 가 True
"""

from __future__ import annotations

import asyncio
import os
import warnings

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core._api import LangChainBetaWarning
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
from langchain.mcp import MCPAdapter  # noqa: E402

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
STOCK: dict[str, int] = {"KB-01": 5, "MS-02": 0}

inventory = FastMCP("inventory", instructions="재고 조회와 예약")


# ------------------------------------------------------------------ TODO 1
# TODO 1-a: @inventory.tool(annotations=...) 데코레이터로 등록하세요 (읽기 전용)
def check_stock(sku: str) -> dict:
    """상품 sku 의 재고 stock 수량을 조회한다."""
    raise NotImplementedError("TODO 1-a: check_stock")


# TODO 1-b: @inventory.tool(annotations=...) 데코레이터로 등록하세요 (파괴적 작업)
def reserve_stock(sku: str, qty: int) -> dict:
    """상품 sku 재고를 qty 만큼 예약(차감)한다."""
    # 재고가 부족하면 ToolError(f"재고 부족: ...") 를 raise 하세요
    raise NotImplementedError("TODO 1-b: reserve_stock")


# ------------------------------------------------------------------ TODO 2
# TODO 2: @inventory.resource("inventory://warehouses") 로 등록하세요
def warehouses() -> str:
    """창고 목록."""
    return "서울 1센터, 부산 2센터"


# ------------------------------------------------------------------ TODO 3
def split_by_risk(tools: list[BaseTool]) -> tuple[list[str], list[str]]:
    # TODO 3: 각 도구의 metadata["mcp"]["tool"]["annotations"]["destructive_hint"] 로 분류하세요
    raise NotImplementedError("TODO 3: split_by_risk")


# ================================================================== 자가 채점
async def grade() -> None:
    async with Client(inventory) as c:
        tools = {t.name: t for t in await c.list_tools()}
        assert set(tools) == {"check_stock", "reserve_stock"}, f"TODO 1: 도구 두 개를 서버에 등록하세요 (현재 {list(tools)})"
        assert tools["check_stock"].annotations.read_only_hint is True
        assert tools["reserve_stock"].annotations.destructive_hint is True
        ok = await c.call_tool("reserve_stock", {"sku": "KB-01", "qty": 2})
        assert ok.data["left"] == 3
        bad = await c.call_tool("reserve_stock", {"sku": "MS-02", "qty": 1}, raise_on_error=False)
        assert bad.is_error and "재고 부족" in bad.content[0].text
        res = await c.read_resource("inventory://warehouses")
        assert "서울" in res[0].text
    print("1~2) 서버 도구·에러·리소스 통과")

    async with MCPAdapter(inventory) as adapter:
        lc_tools = await adapter.list_tools()
    safe, risky = split_by_risk(lc_tools)
    assert safe == ["check_stock"] and risky == ["reserve_stock"], (safe, risky)
    print("3) 위험도 분류 통과:", safe, risky)

    agent = create_agent(
        MODEL, tools=lc_tools, checkpointer=InMemorySaver(),
        middleware=[HumanInTheLoopMiddleware(interrupt_on={n: True for n in risky})],
    )
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "sku KB-01 stock 확인"}]},
                              {"configurable": {"thread_id": "inv"}})
    assert out["messages"][-1].type == "ai"
    print("4) MCP 도구로 에이전트 실행 통과")
    print("✅ 모든 테스트 통과!")


asyncio.run(grade())
