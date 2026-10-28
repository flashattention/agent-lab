---
title: "Runtime과 context_schema"
description: "노드에 주입되는 Runtime 객체(context, store, stream_writer, heartbeat, execution_info 등)와 실행 시 context= 전달"
order: 12
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#runtime-context"
tags: [runtime, context, dependency-injection, context-schema]
---

`Runtime`은 실행(run) 범위의 의존성과 유틸리티를 묶은 객체입니다. 노드 함수에 `runtime: Runtime[Ctx]` 파라미터를 선언하면 자동 주입됩니다.

**컨텍스트(context)** 는 상태(state)와 다릅니다.

| | State | Context |
|---|---|---|
| 변경 | 노드가 업데이트 | 실행 중 **불변** |
| 저장 | 체크포인트에 저장 | 저장 안 됨 |
| 예 | 메시지, 중간 결과 | user_id, DB 연결, API 클라이언트, 모델 이름 |

v0.x의 `config["configurable"]`로 의존성을 넘기던 방식은 `context_schema` + `context=`로 대체되었습니다.

## Import

```python
from langgraph.runtime import Runtime, get_runtime
from langgraph.config import get_config, get_stream_writer
```

## 시그니처

```python
@dataclass
class Runtime(Generic[ContextT]):
    context: ContextT = None
    store: BaseStore | None = None
    stream_writer: StreamWriter = <no-op>
    heartbeat: Callable[[], None] = <no-op>
    previous: Any = None
    execution_info: ExecutionInfo | None = None
    server_info: ServerInfo | None = None
    control: RunControl | None = None

def get_runtime(context_schema: type[ContextT] | None = None) -> Runtime[ContextT]
```

## 파라미터

| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `context` | `ContextT` | `None` | `invoke(..., context=...)`로 넘긴 값. 타입은 `context_schema` |
| `store` | `BaseStore \| None` | `None` | `compile(store=...)`로 붙인 Store |
| `stream_writer` | `StreamWriter` | no-op | `"custom"` 스트림 writer (`get_stream_writer()`와 동일) |
| `heartbeat` | `Callable[[], None]` | no-op | `TimeoutPolicy(idle_timeout=...)`의 진행 신호. idle 타임아웃이 없으면 no-op |
| `previous` | `Any` | `None` | 함수형 API `entrypoint`에서 같은 스레드의 이전 반환값(체크포인터 필요) |
| `execution_info` | `ExecutionInfo \| None` | `None` | 읽기 전용 실행 정보(아래) |
| `server_info` | `ServerInfo \| None` | `None` | LangGraph Server에서 실행 시 `assistant_id`, `graph_id`, `user` |
| `control` | `RunControl \| None` | `None` | 협조적 중단(drain) 제어 |

`ExecutionInfo` 필드: `checkpoint_id`, `checkpoint_ns`, `task_id`, `thread_id`(체크포인터 없으면 `None`), `run_id`, `node_attempt`(1부터, 재시도 횟수 확인용), `node_first_attempt_time`.

`StateGraph(State, context_schema=Ctx)`의 `context_schema`는 `dataclass`, `TypedDict`, Pydantic 모델 모두 가능합니다.

## 메서드와 반환값

| API | 반환 | 설명 |
|---|---|---|
| `get_runtime(context_schema=None)` | `Runtime` | 노드 시그니처에 runtime을 선언하지 않고 실행 중 어디서든 가져오기 |
| `get_config()` | `RunnableConfig` | 현재 config. `Runtime`에는 config가 없으므로 이걸 쓰거나 노드에 `config: RunnableConfig` 파라미터를 선언 |
| `Runtime.override(**kw)` / `merge(other)` | `Runtime` | 새 Runtime 생성(주로 내부/테스트용) |

## 예제

### context_schema로 의존성 주입

```python
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.runtime import Runtime


@dataclass
class Ctx:
    user_id: str
    tone: str = "formal"


class State(TypedDict):
    reply: str


def respond(state: State, runtime: Runtime[Ctx]) -> dict:
    info = runtime.execution_info
    prefix = "안녕하세요" if runtime.context.tone == "formal" else "안녕"
    return {"reply": f"{prefix}, {runtime.context.user_id} (attempt={info.node_attempt})"}


graph = StateGraph(State, context_schema=Ctx).add_node("respond", respond).add_edge(START, "respond").compile()

print(graph.invoke({"reply": ""}, context=Ctx(user_id="u-1")))
print(graph.invoke({"reply": ""}, context=Ctx(user_id="u-2", tone="casual")))
```

### get_runtime / get_config

```python
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config
from langgraph.graph import StateGraph, START
from langgraph.runtime import get_runtime


class State(TypedDict):
    out: str


def helper() -> str:
    rt = get_runtime()                       # 깊은 호출 스택에서도 접근
    tid = get_config()["configurable"].get("thread_id", "-")
    return f"ctx={rt.context} thread={tid}"


def node(state: State, config: RunnableConfig) -> dict:
    return {"out": helper()}


graph = StateGraph(State, context_schema=dict).add_node("node", node).add_edge(START, "node").compile()
print(graph.invoke({"out": ""}, {"configurable": {"thread_id": "t9"}}, context={"lang": "ko"}))
```

## 주의사항

> [!WARNING]
> `Runtime`에는 `config`가 없습니다. `runtime.config`는 `AttributeError`입니다. config가 필요하면 노드에 `config: RunnableConfig`를 선언하거나 `get_config()`를 쓰세요.

> [!WARNING]
> 컨텍스트에는 직렬화되지 않는 객체(DB 커넥션 등)를 넣어도 되지만, 상태(state)에 넣으면 체크포인트 저장 시 직렬화 오류가 납니다. 의존성은 context, 데이터는 state로 나누세요.

> [!TIP]
> 도구(tool)에서는 `Runtime` 대신 `ToolRuntime`을 씁니다. `context`, `store`, `stream_writer`, `state`, `tool_call_id`를 함께 제공합니다([ToolRuntime](/docs/langchain/05-tool-runtime)).

## 관련 문서

- [StateGraph (context_schema)](/docs/langgraph/01-state-graph)
- [Store](/docs/langgraph/10-store)
- [스트리밍 (stream_writer)](/docs/langgraph/11-streaming)
- [정책: TimeoutPolicy와 heartbeat](/docs/langgraph/16-policies)
- [ToolRuntime](/docs/langchain/05-tool-runtime)
