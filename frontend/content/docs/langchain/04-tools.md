---
title: "도구 (@tool, BaseTool)"
description: "@tool 데코레이터, BaseTool/StructuredTool, ToolException과 오류 처리"
order: 4
source: "https://docs.langchain.com/oss/python/langchain/tools"
tags: [tools, tool, basetool, structuredtool, toolexception]
---

도구(Tool)는 모델이 호출할 수 있는 함수입니다. 이름(`name`), 설명(`description`), 인자 스키마(`args_schema`)가 모델에게 전달되고, 모델이 만든 `tool_call`의 인자로 실행됩니다. 대부분은 `@tool` 데코레이터로 만들고, 상태가 필요하거나 동작을 세밀하게 제어할 때 `BaseTool`을 상속합니다.

## Import

```python
from langchain.tools import tool, BaseTool, ToolException
from langchain_core.tools import StructuredTool
```

## 시그니처

```python
def tool(
    name_or_callable: str | Callable | None = None,
    runnable: Runnable | None = None,
    *args,
    description: str | None = None,
    return_direct: bool = False,
    args_schema: type[BaseModel] | dict[str, Any] | None = None,
    infer_schema: bool = True,
    response_format: Literal["content", "content_and_artifact"] = "content",
    parse_docstring: bool = False,
    error_on_invalid_docstring: bool = True,
    extras: dict[str, Any] | None = None,
) -> BaseTool | Callable[[Callable], BaseTool]

StructuredTool.from_function(
    func: Callable | None = None,
    coroutine: Callable[..., Awaitable] | None = None,
    name: str | None = None,
    description: str | None = None,
    return_direct: bool = False,
    args_schema: ArgsSchema | None = None,
    infer_schema: bool = True,
    *,
    response_format: Literal["content", "content_and_artifact"] = "content",
    parse_docstring: bool = False,
    error_on_invalid_docstring: bool = False,
    **kwargs,
) -> StructuredTool
```

## 파라미터

### @tool

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `name_or_callable` | `str \| Callable` | `None` | `@tool("custom_name")`처럼 이름을 지정하거나, `@tool`로 함수를 바로 받습니다. 기본 이름은 함수 이름. |
| `description` | `str \| None` | `None` | 지정하지 않으면 docstring이 설명이 됩니다. |
| `return_direct` | `bool` | `False` | `True`면 도구 결과를 최종 답으로 하고 에이전트 루프를 끝냅니다. |
| `args_schema` | `type[BaseModel] \| dict` | `None` | 인자 스키마를 직접 지정. 필드 설명·검증을 세밀하게 할 때. |
| `infer_schema` | `bool` | `True` | 함수 시그니처에서 스키마를 추론할지 여부. |
| `response_format` | `"content" \| "content_and_artifact"` | `"content"` | `"content_and_artifact"`면 함수가 `(content, artifact)` 튜플을 반환하고, artifact는 `ToolMessage.artifact`에 저장됩니다. |
| `parse_docstring` | `bool` | `False` | Google 스타일 docstring의 `Args:` 섹션을 인자 설명으로 파싱합니다. |
| `error_on_invalid_docstring` | `bool` | `True` | `parse_docstring=True`일 때 docstring 형식 오류를 예외로 낼지. |
| `extras` | `dict \| None` | `None` | 제공자 전용 메타데이터(예: `{"defer_loading": True}`). |

### BaseTool 필드

| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `name` | `str` | 필수 | 모델에 노출되는 이름(영문·숫자·`_`·`-` 권장). |
| `description` | `str` | 필수 | 모델이 언제 호출할지 판단하는 근거. |
| `args_schema` | `type[BaseModel] \| dict \| None` | `None` | 인자 스키마. |
| `return_direct` | `bool` | `False` | 위와 동일. |
| `handle_tool_error` | `bool \| str \| Callable[[ToolException], str] \| None` | `False` | `ToolException` 처리. `True`면 예외 메시지, `str`이면 그 문자열을 결과로 돌려줍니다. |
| `handle_validation_error` | `bool \| str \| Callable \| None` | `False` | 인자 검증(`ValidationError`) 실패 처리. |
| `response_format` | `str` | `"content"` | 위와 동일. |
| `extras` | `dict \| None` | `None` | 위와 동일. |

## 메서드와 반환값

| 메서드/속성 | 설명 |
|---|---|
| `invoke(input, config=None)` | `input`이 인자 dict면 원시 결과, **ToolCall dict**(`{"name","args","id","type":"tool_call"}`)면 `ToolMessage`를 반환합니다. |
| `ainvoke` | 비동기 실행. `coroutine`이 없으면 스레드에서 동기 함수를 실행합니다. |
| `.args` | 인자 JSON 스키마의 `properties`. |
| `.tool_call_schema` | 모델에 실제로 보내는 스키마(주입 인자 제외). |
| `_run(...)` / `_arun(...)` | `BaseTool` 상속 시 구현할 메서드. |

## 예제

```python
from pydantic import BaseModel, Field
from langchain.tools import tool


@tool(parse_docstring=True)
def add(a: int, b: int) -> int:
    """두 정수를 더한다.

    Args:
        a: 첫 번째 정수
        b: 두 번째 정수
    """
    return a + b


class SearchArgs(BaseModel):
    query: str = Field(description="검색어")
    top_k: int = Field(default=3, ge=1, le=10, description="결과 개수")


@tool("doc_search", args_schema=SearchArgs, response_format="content_and_artifact")
def search(query: str, top_k: int = 3):
    """사내 문서를 검색한다."""
    hits = [f"{query}-문서{i}" for i in range(top_k)]
    return f"{len(hits)}건 찾음", {"hits": hits}  # (content, artifact)


print(add.invoke({"a": 2, "b": 3}))  # 5
msg = search.invoke({"name": "doc_search", "args": {"query": "휴가"}, "id": "c1", "type": "tool_call"})
print(msg.content, msg.artifact)
print(search.tool_call_schema.model_json_schema()["properties"].keys())
```

`BaseTool` 상속과 `ToolException`:

```python
from langchain.tools import BaseTool, ToolException


class Divide(BaseTool):
    name: str = "divide"
    description: str = "a를 b로 나눈다."
    handle_tool_error: bool = True  # ToolException → 오류 메시지를 결과로 반환

    def _run(self, a: float, b: float) -> float:
        if b == 0:
            raise ToolException("0으로 나눌 수 없습니다.")
        return a / b


div = Divide()
print(div.invoke({"a": 1, "b": 0}))  # "0으로 나눌 수 없습니다."
```

## 주의사항

> [!WARNING]
> `handle_tool_error`는 `ToolException`만 처리합니다. 일반 `ValueError` 등은 그대로 전파됩니다. `create_agent`의 기본 `ToolNode`도 인자 검증 오류(`ToolInvocationError`)만 모델에게 돌려주고 나머지 실행 예외는 다시 던집니다. 실행 예외를 모델에게 돌려주려면 [ToolErrorMiddleware](/docs/langchain/07-built-in-middleware)나 `ToolNode(handle_tool_errors=...)`를 쓰세요.

> [!WARNING]
> 설명(docstring)이 없는 함수에 `@tool`을 붙이면 `ValueError`가 납니다. 설명은 모델의 도구 선택 정확도를 좌우하므로 "언제 쓰는지"를 구체적으로 쓰세요.

> [!TIP]
> 상태·컨텍스트·스토어가 필요하면 인자에 `runtime: ToolRuntime`을 추가합니다. 이 인자는 모델 스키마에서 자동으로 숨겨집니다. [ToolRuntime](/docs/langchain/05-tool-runtime) 참고.

## 관련 문서

- [ToolRuntime과 주입 인자](/docs/langchain/05-tool-runtime)
- [create_agent](/docs/langchain/06-create-agent)
- [ToolNode (prebuilt)](/docs/langgraph/17-prebuilt)
- [MCP](/docs/integrations/03-mcp)
