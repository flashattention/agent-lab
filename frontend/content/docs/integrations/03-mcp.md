---
title: "MCP (FastMCP · langchain.mcp)"
description: "FastMCP로 MCP 서버 만들기, fastmcp.Client로 호출하기, langchain.mcp.MCPAdapter로 에이전트 도구로 변환하기"
order: 3
source: "https://docs.langchain.com/oss/python/langchain/mcp"
tags: [mcp, fastmcp, tools, adapter]
---

MCP(Model Context Protocol)는 도구(Tools)·리소스(Resources)·프롬프트(Prompts)를 LLM 애플리케이션에 표준 방식으로 제공하는 프로토콜입니다. 이 프로젝트에서는 세 가지 구성 요소를 씁니다.

| 구성 요소 | 패키지 | 역할 |
|---|---|---|
| `FastMCP` | `fastmcp` 4.1.4 | MCP **서버** 작성 (`@mcp.tool`, `@mcp.resource`, `@mcp.prompt`) |
| `Client` | `fastmcp` 4.1.4 | MCP **클라이언트** (도구 목록 조회, 호출, 리소스 읽기) |
| `MCPAdapter` | `langchain.mcp` (beta) | MCP 도구 → LangChain `BaseTool` 변환, `create_agent`에 연결 |

## Import

```python
from fastmcp import FastMCP, Client, Context   # pip install fastmcp
from langchain.mcp import MCPAdapter, as_langchain_tool, MCPToolArtifact  # beta
```

## 시그니처

```python
FastMCP(
    name: str | None = None,
    instructions: str | None = None,
    *,
    version: str | int | float | None = None,
    auth: AuthProvider | None = None,
    middleware: Sequence[Middleware] | None = None,
    lifespan: LifespanCallable | Lifespan | None = None,
    tools: Sequence[Tool | Callable[..., Any]] | None = None,
    mask_error_details: bool | None = None,
    strict_input_validation: bool | None = None,
    # ... website_url, icons, providers, transforms, on_duplicate, cache_ttl, tasks 등
)
FastMCP.tool(name_or_fn=None, *, name=None, title=None, description=None, tags=None,
             output_schema=..., annotations=None, meta=None, timeout=None, auth=None,
             run_in_thread=True, ...)
FastMCP.resource(uri: str, *, name=None, description=None, mime_type=None, tags=None, ...)
FastMCP.prompt(name_or_fn=None, *, name=None, description=None, tags=None, ...)
FastMCP.run(transport: Transport | None = None, show_banner: bool | None = None, **transport_kwargs)

Client(
    transport: ClientTransport | FastMCP | AnyUrl | Path | MCPConfig | dict | str,
    name: str | None = None,
    timeout: timedelta | float | int | None = None,
    auth: httpx.Auth | Literal["oauth"] | str | None = None,
    elicitation_handler=None, sampling_handler=None, log_handler=None, progress_handler=None,
    cache: CacheConfig | bool | None = None,
    # ... roots, init_timeout, verify, mode 등
)
Client.list_tools(max_pages: int = 250, *, cache_mode: CacheMode = "use") -> list[mcp.types.Tool]
Client.call_tool(name: str, arguments: dict | None = None, *, timeout=None,
                 progress_handler=None, raise_on_error: bool = True, meta=None) -> CallToolResult

class MCPAdapter:
    def __init__(self, target: MCPAdapterTarget) -> None: ...
    async def list_tools(self, *, cache_mode: CacheMode = "use") -> list[BaseTool]: ...
    @property
    def client(self) -> fastmcp.Client | ClientGroup: ...

async def as_langchain_tool(tool: mcp.types.Tool, client: Client | ClientGroup) -> BaseTool
```

## 파라미터

### MCPAdapter

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `target` | `fastmcp.Client \| ClientGroup \| ClientTransport \| FastMCP \| MCPServer \| AnyUrl \| Path \| MCPConfig \| dict \| str` | (필수) | 연결 대상. `str`은 **http/https URL만** 허용. 로컬 스크립트는 `Path("server.py")`, 인프로세스 서버는 `FastMCP` 인스턴스, 여러 서버는 `MCPConfig`/dict |

`list_tools(cache_mode=...)`: `"use"`(기본, 클라이언트 캐시 사용), `"refresh"`(서버에서 다시 받아 캐시 갱신), `"bypass"`(캐시 무시).

### FastMCP.run 전송 방식(transport)

| 값 | 설명 |
|---|---|
| `"stdio"` (기본) | 표준 입출력. 클라이언트가 서버 프로세스를 띄움 |
| `"http"` | Streamable HTTP. `host`, `port`, `path` 키워드 사용 |
| `"streamable-http"` | `"http"`와 같은 Streamable HTTP |
| `"sse"` | 레거시 SSE 전송 |

## 메서드와 반환값

- `MCPAdapter`는 async 컨텍스트 매니저입니다. `list_tools()`는 내부에서 연결을 열고 닫으며, 반환된 도구는 어댑터 컨텍스트가 끝난 뒤에도 호출할 수 있습니다(호출 시 다시 연결).
- 변환된 도구는 **비동기 전용**입니다. 에이전트는 `ainvoke`/`astream`으로 실행하세요.
- 도구 결과는 `ToolMessage.content`(콘텐츠 블록 리스트)로, MCP `structuredContent`는 `ToolMessage.artifact`(`MCPToolArtifact`, `{"structured_content": ...}`)로 들어갑니다.
- 서버가 실행 중 입력을 요청(elicitation)하면 어댑터가 LangGraph `interrupt()`로 바꿉니다. 체크포인터가 있어야 재개할 수 있습니다(`langchain.mcp.elicitation`).
- `Client.call_tool()`은 `CallToolResult`를 반환합니다. `.data`는 파싱된 Python 값, `.content`는 MCP 콘텐츠 블록, `.structured_content`는 구조화 결과입니다. 도구 오류 시 기본적으로 `ToolError`를 던집니다(`raise_on_error=False`로 끔).

## 예제

```python
# server.py — 독립 실행용 MCP 서버
from fastmcp import FastMCP

mcp = FastMCP("math")


@mcp.tool
def add(a: int, b: int) -> int:
    """두 정수를 더한다."""
    return a + b


@mcp.resource("config://version")
def version() -> str:
    return "1.0.0"


if __name__ == "__main__":
    mcp.run()  # stdio. HTTP: mcp.run(transport="http", host="127.0.0.1", port=8000)
```

```python
import asyncio

from fastmcp import Client, FastMCP

mcp = FastMCP("demo")


@mcp.tool
def greet(name: str) -> str:
    """이름으로 인사한다."""
    return f"안녕하세요, {name}님"


async def main() -> None:
    # FastMCP 인스턴스를 넘기면 네트워크 없이 인프로세스로 연결된다 (테스트에 유용)
    async with Client(mcp) as client:
        print([t.name for t in await client.list_tools()])
        result = await client.call_tool("greet", {"name": "지민"})
        print(result.data)


asyncio.run(main())
```

```python
import asyncio
import os
import warnings

from fastmcp import FastMCP
from langchain.agents import create_agent
from langchain_core._api import LangChainBetaWarning

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
from langchain.mcp import MCPAdapter  # noqa: E402

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
mcp = FastMCP("math")


@mcp.tool
def add(a: int, b: int) -> int:
    """두 정수를 더한다."""
    return a + b


async def main() -> None:
    # 원격 서버면 MCPAdapter("https://example.com/mcp"), 로컬 스크립트면 MCPAdapter(Path("server.py"))
    async with MCPAdapter(mcp) as adapter:
        tools = await adapter.list_tools()
    agent = create_agent(MODEL, tools=tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "3 더하기 4는?"}]})
    print(result["messages"][-1].content)


asyncio.run(main())
```

## 주의사항

> [!WARNING]
> `langchain.mcp`는 **베타**입니다. import 시 `LangChainBetaWarning`이 한 번 출력되며 API가 바뀔 수 있습니다. 별도 패키지 `langchain-mcp-adapters`(`MultiServerMCPClient`)는 이 환경에 설치되어 있지 않습니다.

> [!WARNING]
> `MCPAdapter("server.py")`처럼 **문자열로 로컬 경로를 넘기면 `ValueError`**입니다. 설정·모델 출력에서 온 문자열이 로컬 프로세스 실행으로 이어지는 것을 막기 위한 의도적 제한입니다. 로컬 서버는 `Path(...)`나 명시적 transport를 쓰세요.

> [!WARNING]
> stdio 서버에서는 `print()`가 프로토콜 스트림(stdout)을 깨뜨립니다. 서버 로그는 stderr나 `Context`의 로깅 메서드(`await ctx.info(...)`)로 남기세요.

> [!TIP]
> MCP 도구도 결국 LangChain 도구이므로 `HumanInTheLoopMiddleware`, `ToolCallLimitMiddleware` 등 [내장 미들웨어](/docs/langchain/07-built-in-middleware)를 그대로 적용할 수 있습니다. 외부 서버의 도구는 신뢰 경계 밖이므로 쓰기·삭제 도구에는 승인 단계를 두세요.

## 관련 문서

- [도구 (@tool, BaseTool)](/docs/langchain/04-tools)
- [create_agent](/docs/langchain/06-create-agent)
- [interrupt와 HITL](/docs/langgraph/08-interrupt)
- [공식 문서: LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp)
- [공식 문서: FastMCP](https://gofastmcp.com)
