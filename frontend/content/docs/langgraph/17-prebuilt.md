---
title: "prebuilt (ToolNode, tools_condition, InjectedState, InjectedStore)"
description: "도구 실행 노드 ToolNode, 라우팅 함수 tools_condition, 도구 인자 주입 InjectedState/InjectedStore/ToolRuntime"
order: 17
source: "https://reference.langchain.com/python/langgraph/agents/"
tags: [prebuilt, toolnode, tools-condition, injected-state, tools]
---

`langgraph.prebuilt`는 직접 만든 에이전트 그래프에서 쓰는 도구 실행 부품을 제공합니다.

| 이름 | 종류 | 설명 |
|---|---|---|
| `ToolNode` | 노드 | 마지막 `AIMessage.tool_calls`를 실행하고 `ToolMessage`(또는 `Command`)를 반환. 여러 호출은 병렬 실행 |
| `tools_condition` | 라우팅 함수 | 마지막 AI 메시지에 tool_calls가 있으면 `"tools"`, 없으면 `END` |
| `InjectedState` | 타입 어노테이션 | 도구 인자에 그래프 상태(또는 특정 키)를 주입. LLM 스키마에서 숨김 |
| `InjectedStore` | 타입 어노테이션 | 도구 인자에 Store 주입 |
| `ToolRuntime` | 주입 타입 | state, context, store, stream_writer, tool_call_id를 한 번에 주입(`langchain.tools`에서도 import 가능) |
| `ValidationNode` | 노드 | **deprecated** (v1.0). `create_agent` + 도구 오류 처리 사용 |
| `create_react_agent` | 함수 | **deprecated**. `langchain.agents.create_agent` 사용 |

## Import

```python
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState, InjectedStore
from langchain.tools import ToolRuntime, tool
```

## 시그니처

```python
ToolNode(
    tools: Sequence[BaseTool | Callable],
    *,
    name: str = "tools",
    tags: list[str] | None = None,
    handle_tool_errors: bool | str | Callable[..., str] | type[Exception]
                        | tuple[type[Exception], ...] = _default_handle_tool_errors,
    messages_key: str = "messages",
    wrap_tool_call: ToolCallWrapper | None = None,
    awrap_tool_call: AsyncToolCallWrapper | None = None,
)

def tools_condition(
    state: list[AnyMessage] | dict[str, Any] | BaseModel,
    messages_key: str = "messages",
) -> Literal["tools", "__end__"]

InjectedState(field: str | None = None)
InjectedStore()
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `tools` | `Sequence[BaseTool \| Callable]` | (필수) | 실행할 도구. 일반 함수는 자동으로 도구로 변환 |
| `name` | `str` | `"tools"` | 노드 이름(`tools_condition`의 반환값과 맞출 것) |
| `tags` | `list[str] \| None` | `None` | 트레이스 태그 |
| `handle_tool_errors` | 아래 표 | 기본 핸들러 | 도구 오류 처리 방식 |
| `messages_key` | `str` | `"messages"` | 상태의 메시지 키 |
| `wrap_tool_call` | `(request, execute) -> ToolMessage \| Command` | `None` | 도구 실행 가로채기(재시도, 캐시, 로깅). `execute`는 여러 번 호출 가능 |
| `awrap_tool_call` | async 버전 | `None` | |
| `field` (InjectedState) | `str \| None` | `None` | 상태 전체 대신 특정 키만 주입 |

`handle_tool_errors` 값:

| 값 | 동작 |
|---|---|
| 기본값 | 인자 검증 오류(`ToolInvocationError`)만 메시지로 돌려주고, **도구 실행 중 예외는 다시 발생** |
| `True` | 모든 예외를 잡아 기본 템플릿 오류 메시지로 `ToolMessage(status="error")` 반환 |
| `str` | 모든 예외를 잡아 이 문자열 반환 |
| 예외 타입 / 튜플 | 해당 예외만 잡음 |
| `Callable[[Exception], str]` | 시그니처에 맞는 예외를 잡아 반환값 사용 |
| `False` | 처리 안 함(전파) |

## 메서드와 반환값

- `ToolNode` 출력: `{"messages": [ToolMessage, ...]}`. 도구가 `Command`를 반환하면 그 Command가 그대로 적용됩니다.
- 입력으로 상태 dict 대신 `list[AIMessage]`, 또는 `Send("tools", ToolCallWithContext)` 형식도 받습니다.
- `tools_condition`은 `add_conditional_edges("agent", tools_condition)`처럼 path_map 없이 씁니다. 반환값 `"tools"`가 노드 이름이므로 ToolNode 이름을 바꾸면 path_map을 지정하세요.

## 예제

### 수동 ReAct 루프

```python
import os
from typing import Annotated

from langchain.chat_models import init_chat_model
from langchain.tools import tool, ToolRuntime
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회한다."""
    return f"{city}: 맑음, 21도"


@tool
def count_messages(state: Annotated[dict, InjectedState]) -> int:
    """지금까지의 대화 메시지 수를 센다."""
    return len(state["messages"])  # state 인자는 LLM 스키마에 노출되지 않음


@tool
def whoami(runtime: ToolRuntime) -> str:
    """현재 도구 호출 ID를 확인한다."""
    return f"tool_call_id={runtime.tool_call_id}"


tools = [get_weather, count_messages, whoami]
llm = init_chat_model(MODEL).bind_tools(tools)


def agent(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # "tools" 또는 END
builder.add_edge("tools", "agent")
graph = builder.compile()

result = graph.invoke({"messages": [("user", "서울 날씨 알려줘")]}, {"recursion_limit": 10})
for m in result["messages"]:
    m.pretty_print()
```

### InjectedStore

```python
from typing import Annotated

from langchain.tools import tool
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore


@tool
def save_memory(text: str, store: Annotated[BaseStore, InjectedStore()]) -> str:
    """사용자에 대한 사실을 저장한다."""
    store.put(("memories",), str(hash(text)), {"text": text})
    return "저장됨"
# compile(store=InMemoryStore()) 한 그래프의 ToolNode에서 실행하면 store가 주입된다
```

## 주의사항

> [!WARNING]
> `ToolNode`는 그래프 안에서 실행되어야 합니다. 그래프 밖에서 `ToolNode(...).invoke(...)`를 직접 호출하면 런타임이 없어 `ValueError: Missing required config key ...`가 발생합니다.

> [!WARNING]
> 기본 `handle_tool_errors`는 도구 **내부 예외를 다시 발생**시켜 그래프 전체를 중단시킵니다. LLM에게 오류를 돌려주고 재시도하게 하려면 `handle_tool_errors=True`(또는 메시지/함수)를 지정하거나 도구에서 `ToolException`을 다루세요.

> [!TIP]
> 새 코드에서는 직접 루프를 조립하기보다 `create_agent`를 권장합니다. 도구 재시도·승인 등은 미들웨어로 처리합니다. 직접 조립은 비표준 흐름이 필요할 때 쓰세요.

## 관련 문서

- [create_agent](/docs/langchain/06-create-agent)
- [도구 (@tool, ToolException)](/docs/langchain/04-tools)
- [ToolRuntime과 InjectedToolCallId](/docs/langchain/05-tool-runtime)
- [MessagesState](/docs/langgraph/03-messages-state)
- [Store](/docs/langgraph/10-store)
