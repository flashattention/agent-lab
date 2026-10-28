---
title: "ToolRuntime과 주입 인자"
description: "도구 안에서 state/context/store/stream_writer에 접근하는 ToolRuntime, InjectedToolCallId, Command 반환"
order: 5
source: "https://docs.langchain.com/oss/python/langchain/tools#accessing-context"
tags: [tools, toolruntime, injected, command, context]
---

도구 함수에 `runtime: ToolRuntime` 인자를 추가하면 실행 시 에이전트 상태(state), 런타임 컨텍스트(context), 스토어(store), 스트림 writer, 도구 호출 ID가 주입됩니다. 이 인자는 **모델에게 보내는 스키마에서 자동으로 제외**되므로 모델이 값을 만들 필요가 없습니다. 도구는 `Command`를 반환해 그래프 상태를 직접 갱신할 수도 있습니다.

## Import

```python
from langchain.tools import tool, ToolRuntime, InjectedToolCallId, InjectedState, InjectedStore, InjectedToolArg
from langchain.messages import ToolMessage
from langgraph.types import Command
```

## 시그니처

```python
@dataclass
class ToolRuntime(Generic[ContextT, StateT]):
    state: StateT
    context: ContextT
    config: RunnableConfig
    stream_writer: StreamWriter
    tool_call_id: str | None
    store: BaseStore | None
    tools: list[BaseTool] = field(default_factory=list)
    execution_info: ExecutionInfo | None = None
    server_info: ServerInfo | None = None
```

## 파라미터

| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `state` | `StateT` | | 현재 그래프 상태(에이전트면 `messages` 등). 읽기 전용으로 다루고, 갱신은 `Command`로 합니다. |
| `context` | `ContextT` | | `invoke(..., context=...)`로 넘긴 런타임 컨텍스트(`context_schema` 타입). |
| `config` | `RunnableConfig` | | `thread_id`, `tags`, `metadata` 등 실행 설정. |
| `stream_writer` | `StreamWriter` | | `stream_mode="custom"`으로 진행 상황을 보내는 함수. |
| `tool_call_id` | `str \| None` | | 이 호출의 ID. `ToolMessage(tool_call_id=...)`에 사용. |
| `store` | `BaseStore \| None` | | `create_agent(store=...)`로 넘긴 장기 메모리 스토어. |
| `tools` | `list[BaseTool]` | `[]` | 현재 사용 가능한 도구 목록. |
| `execution_info` | `ExecutionInfo \| None` | `None` | 실행 메타데이터(체크포인트/태스크 정보). |
| `server_info` | `ServerInfo \| None` | `None` | LangGraph Server에서 실행될 때의 서버 정보. |

### 개별 주입 어노테이션

| 어노테이션 | 용도 |
|---|---|
| `Annotated[str, InjectedToolCallId]` | 도구 호출 ID만 주입. |
| `Annotated[dict, InjectedState]` / `InjectedState("field")` | 상태 전체 또는 특정 필드만 주입. |
| `Annotated[BaseStore, InjectedStore()]` | 스토어만 주입. |
| `Annotated[T, InjectedToolArg]` | 모델에는 숨기고 호출자가 직접 채우는 인자. |

v1에서는 `ToolRuntime` 하나로 대부분을 대신할 수 있습니다. 개별 어노테이션은 `langgraph.prebuilt`의 `ToolNode`와 함께 쓰던 기존 코드와 호환을 위해 남아 있습니다.

## 메서드와 반환값

도구는 다음 중 하나를 반환할 수 있습니다.

| 반환 | 효과 |
|---|---|
| 일반 값(`str`, dict 등) | `ToolMessage(content=str(값))`로 감싸져 `messages`에 추가됩니다. |
| `ToolMessage` | 그대로 추가됩니다. |
| `Command(update={...})` | 상태를 직접 갱신합니다. `messages`를 갱신할 때는 **반드시** 해당 `tool_call_id`의 `ToolMessage`를 포함해야 합니다. |
| `Command(goto=..., graph=Command.PARENT)` | 상위 그래프의 노드로 이동(핸드오프). |

## 예제

```python
import os
from dataclasses import dataclass
from langchain.agents import create_agent, AgentState
from langchain.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@dataclass
class Ctx:
    user_id: str


class State(AgentState):
    favorite_city: str


@tool
def remember_city(city: str, runtime: ToolRuntime[Ctx, State]) -> Command:
    """사용자가 좋아하는 도시를 기억한다."""
    runtime.stream_writer({"progress": f"{runtime.context.user_id}의 도시 저장 중"})
    return Command(update={
        "favorite_city": city,
        "messages": [ToolMessage(f"{city} 저장 완료", tool_call_id=runtime.tool_call_id)],
    })


agent = create_agent(MODEL, tools=[remember_city], state_schema=State, context_schema=Ctx)
result = agent.invoke(
    {"messages": [{"role": "user", "content": "내가 좋아하는 도시는 부산이야, 기억해 줘"}]},
    context=Ctx(user_id="u-42"),
)
print(result.get("favorite_city"))
print(remember_city.tool_call_schema.model_json_schema()["properties"].keys())  # runtime 없음
```

`InjectedToolCallId`만 필요할 때:

```python
from typing import Annotated
from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.types import Command


@tool
def set_flag(flag: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """플래그를 설정한다."""
    return Command(update={"messages": [ToolMessage(f"flag={flag}", tool_call_id=tool_call_id)]})


out = set_flag.invoke({"name": "set_flag", "args": {"flag": "on"}, "id": "call_9", "type": "tool_call"})
print(out)
```

## 주의사항

> [!WARNING]
> `Command(update={"messages": [...]})`에 해당 `tool_call_id`의 `ToolMessage`가 빠지면, 다음 모델 호출에서 "tool_calls에 대한 응답이 없다"는 제공자 오류가 납니다.

> [!WARNING]
> 주입 인자가 있는 도구를 `tool.invoke({"city": "부산"})`처럼 인자 dict로 직접 호출하면 런타임이 없어 실패합니다. 단위 테스트에서는 ToolCall dict로 호출하거나 에이전트/`ToolNode`를 통해 실행하세요.

> [!TIP]
> 인자 이름은 반드시 `runtime`이고 타입이 `ToolRuntime`이어야 주입됩니다. 제네릭 `ToolRuntime[ContextT, StateT]`로 쓰면 `runtime.context`/`runtime.state` 자동완성이 됩니다.

## 관련 문서

- [도구](/docs/langchain/04-tools)
- [create_agent](/docs/langchain/06-create-agent)
- [Command](/docs/langgraph/06-command)
- [Runtime과 context_schema](/docs/langgraph/12-runtime-context)
- [Store](/docs/langgraph/10-store)
- [ToolNode, InjectedState (prebuilt)](/docs/langgraph/17-prebuilt)
