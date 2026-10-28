---
title: "커스텀 미들웨어"
description: "AgentMiddleware 훅(before/after/wrap)과 데코레이터, state_schema, jump_to, dynamic_prompt"
order: 8
source: "https://docs.langchain.com/oss/python/langchain/middleware/custom"
tags: [middleware, hooks, agent, decorator, dynamic-prompt]
---

커스텀 미들웨어는 `AgentMiddleware`를 상속하거나 훅 데코레이터(`@before_model` 등)로 만듭니다. 훅은 두 종류입니다.

- **노드형 훅(node-style)**: `before_agent`, `before_model`, `after_model`, `after_agent`. 그래프 노드로 실행되며 상태 업데이트 dict(또는 `None`)를 반환합니다.
- **래핑형 훅(wrap-style)**: `wrap_model_call`, `wrap_tool_call`. `handler`를 감싸 호출 전후를 제어합니다(재시도, 요청 수정, 단락).

실행 순서: `before_agent` → [`before_model` → `wrap_model_call`(모델) → `after_model` → `wrap_tool_call`(도구)]* → `after_agent`. `before_*`는 리스트 순서대로, `after_*`는 역순으로 실행됩니다.

## Import

```python
from langchain.agents.middleware import (
    AgentMiddleware, AgentState, ModelRequest, ModelResponse, ExtendedModelResponse, ToolCallRequest,
    before_agent, before_model, after_model, after_agent,
    wrap_model_call, wrap_tool_call, dynamic_prompt, hook_config,
)
from langgraph.runtime import Runtime
```

## 시그니처

```python
class AgentMiddleware(Generic[StateT, ContextT, ResponseT]):
    state_schema: type[StateT] = AgentState      # 추가 상태 필드
    tools: Sequence[BaseTool]                    # 미들웨어가 등록하는 도구
    trace_policy: TracePolicy | None = None      # 훅 span 기록 방식
    transformers: Sequence[TransformerFactory] = ()

    @property
    def name(self) -> str: ...                   # 기본: 클래스 이름

    def before_agent(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None: ...
    def before_model(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None: ...
    def after_model(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None: ...
    def after_agent(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None: ...
    def wrap_model_call(
        self, request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]: ...
    def wrap_tool_call(
        self, request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command: ...
    # 비동기: abefore_agent, abefore_model, aafter_model, aafter_agent, awrap_model_call, awrap_tool_call

# 데코레이터 (before_agent / after_model / after_agent 동일)
def before_model(func=None, *, state_schema: type | None = None, tools: list[BaseTool] | None = None,
                 can_jump_to: list[Literal["tools", "model", "end"]] | None = None,
                 name: str | None = None) -> AgentMiddleware
def wrap_model_call(func=None, *, state_schema=None, tools=None, name=None) -> AgentMiddleware
def wrap_tool_call(func=None, *, state_schema=None, tools=None, name=None) -> AgentMiddleware
def dynamic_prompt(func=None) -> AgentMiddleware   # func(request) -> str | SystemMessage
def hook_config(*, can_jump_to: list[JumpTo] | None = None)  # 클래스 메서드용
```

## 파라미터

### 데코레이터 공통

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `func` | `Callable` | `None` | 훅 함수. 노드형은 `(state, runtime)`, `wrap_model_call`은 `(request, handler)`, `wrap_tool_call`은 `(request, handler)`. |
| `state_schema` | `type \| None` | `None` | 이 미들웨어가 추가하는 상태 스키마(`AgentState` 확장 TypedDict). |
| `tools` | `list[BaseTool] \| None` | `None` | 미들웨어와 함께 등록할 도구. |
| `can_jump_to` | `list["tools" \| "model" \| "end"] \| None` | `None` | (노드형만) 반환 dict에 `"jump_to"`를 넣어 이동할 수 있는 대상. |
| `name` | `str \| None` | `None` | 미들웨어 이름(노드 이름). 기본은 함수 이름. |

### ModelRequest (wrap_model_call 입력)

| 필드 | 타입 | 설명 |
|---|---|---|
| `model` | `BaseChatModel` | 호출할 모델. |
| `messages` | `list[AnyMessage]` | 시스템 메시지를 제외한 메시지. |
| `system_message` | `SystemMessage \| None` | 시스템 메시지(`system_prompt` 프로퍼티로 문자열 접근). |
| `tools` | `list[BaseTool \| dict]` | 바인딩할 도구. |
| `tool_choice` | `Any \| None` | 도구 선택 강제. |
| `response_format` | `ResponseFormat \| None` | 구조화 출력 설정. |
| `model_settings` | `dict` | 모델 호출 추가 인자. |
| `state` / `runtime` | | 현재 상태와 런타임. |

요청을 바꿀 때는 직접 대입보다 `request.override(model=..., tools=..., messages=..., system_message=...)`로 새 객체를 만듭니다.

### ToolCallRequest (wrap_tool_call 입력)

| 필드 | 타입 | 설명 |
|---|---|---|
| `tool_call` | `ToolCall` | `{"name", "args", "id"}`. |
| `tool` | `BaseTool \| None` | 실행될 도구. |
| `state` | `Any` | 현재 상태. |
| `runtime` | `ToolRuntime` | 도구 런타임. |

## 메서드와 반환값

| 훅 | 반환 |
|---|---|
| 노드형 | `None`(변경 없음) 또는 상태 업데이트 dict. `{"jump_to": "end"}`로 흐름 이동(`can_jump_to` 선언 필요). |
| `wrap_model_call` | `ModelResponse(result=[AIMessage], structured_response=None)`, `AIMessage`, 또는 `ExtendedModelResponse(model_response, command=Command(update=...))`. |
| `wrap_tool_call` | `ToolMessage` 또는 `Command`. |
| `dynamic_prompt` 함수 | `str` 또는 `SystemMessage`. |

## 예제

데코레이터 방식:

```python
import os
from typing import Any
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model, wrap_model_call, wrap_tool_call, dynamic_prompt
from langchain.messages import AIMessage
from langchain.tools import tool
from langgraph.runtime import Runtime

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@before_model(can_jump_to=["end"])
def stop_if_too_long(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    if len(state["messages"]) > 20:
        return {"messages": [AIMessage("대화가 너무 깁니다.")], "jump_to": "end"}
    return None


@dynamic_prompt
def persona(request) -> str:
    return f"너는 친절한 비서다. 현재 메시지 수: {len(request.messages)}"


@wrap_model_call
def log_model(request, handler):
    print(f"[model] tools={[t.name for t in request.tools]}")
    return handler(request)


@wrap_tool_call
def log_tool(request, handler):
    print(f"[tool] {request.tool_call['name']} {request.tool_call['args']}")
    return handler(request)


@tool
def add(a: int, b: int) -> int:
    """두 수를 더한다."""
    return a + b


agent = create_agent(MODEL, tools=[add], middleware=[stop_if_too_long, persona, log_model, log_tool])
print(agent.invoke({"messages": [{"role": "user", "content": "3 더하기 4"}]})["messages"][-1].text)
```

클래스 방식(상태 확장 + 모델 교체):

```python
import os
from typing import Any, NotRequired
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


class CounterState(AgentState):
    model_calls: NotRequired[int]


class CountAndRoute(AgentMiddleware[CounterState]):
    state_schema = CounterState

    def __init__(self, cheap_model: str, max_calls: int = 3) -> None:
        super().__init__()
        self.cheap = init_chat_model(cheap_model)
        self.max_calls = max_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: CounterState, runtime) -> dict[str, Any] | None:
        if state.get("model_calls", 0) >= self.max_calls:
            return {"jump_to": "end"}
        return None

    def after_model(self, state: CounterState, runtime) -> dict[str, Any] | None:
        return {"model_calls": state.get("model_calls", 0) + 1}

    def wrap_model_call(self, request, handler):
        # 대화가 짧으면 저렴한 모델로 교체
        if len(request.messages) < 4:
            request = request.override(model=self.cheap)
        return handler(request)


agent = create_agent(MODEL, middleware=[CountAndRoute(MODEL)])
out = agent.invoke({"messages": [{"role": "user", "content": "안녕"}]})
print(out["model_calls"], out["messages"][-1].text)
```

## 주의사항

> [!WARNING]
> 노드형 훅에서 `jump_to`를 쓰려면 반드시 `can_jump_to`(데코레이터) 또는 `@hook_config(can_jump_to=[...])`(클래스 메서드)로 선언해야 합니다. 선언하지 않으면 그래프에 해당 엣지가 없어 무시되거나 오류가 납니다.

> [!WARNING]
> 같은 미들웨어 인스턴스를 두 번 넣거나 이름이 같은 미들웨어를 두 개 넣으면 `create_agent`가 `AssertionError`를 냅니다. 같은 클래스를 여러 번 쓰려면 `name` 프로퍼티를 다르게 하세요.

> [!WARNING]
> `wrap_model_call`/`wrap_tool_call`을 동기 함수로만 정의한 미들웨어를 `ainvoke`/`astream`으로 실행하면 `NotImplementedError`가 납니다. 비동기로 실행할 에이전트라면 `async def` 함수로 데코레이트하거나 클래스에 `awrap_*` 버전도 구현하세요.

> [!TIP]
> `ModelRequest`를 직접 수정(`request.model = ...`)하는 대신 `request.override(...)`를 쓰세요. 원본 요청이 바깥 미들웨어의 재시도 등에 그대로 남아 부작용이 없습니다.

## 관련 문서

- [내장 미들웨어](/docs/langchain/07-built-in-middleware)
- [create_agent](/docs/langchain/06-create-agent)
- [Runtime과 context_schema](/docs/langgraph/12-runtime-context)
- [Command](/docs/langgraph/06-command)
