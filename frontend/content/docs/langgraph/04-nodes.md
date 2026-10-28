---
title: "노드 (add_node)"
description: "add_node의 모든 옵션: retry_policy, cache_policy, timeout, defer, destinations, error_handler, input_schema, metadata, trace_policy"
order: 4
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#nodes"
tags: [node, add-node, retry, cache, timeout, error-handler]
---

노드(Node)는 상태를 받아 업데이트(dict), `Command`, 또는 `None`을 반환하는 함수(동기/비동기) 또는 Runnable입니다. `StateGraph.add_node()`로 등록하며, 재시도·캐시·타임아웃·오류 처리 같은 실행 정책을 노드 단위로 붙일 수 있습니다.

노드 함수가 받을 수 있는 인자(이름이 아니라 **타입 힌트/이름으로 주입**):

| 인자 | 주입 내용 |
|---|---|
| 첫 번째 위치 인자 | 상태(또는 `input_schema`에 맞춘 부분 상태) |
| `config: RunnableConfig` | 실행 설정(`thread_id`, `tags`, ...) |
| `runtime: Runtime[Ctx]` | 컨텍스트, store, stream_writer 등 ([Runtime](/docs/langgraph/12-runtime-context)) |
| `error: NodeError` | `error_handler` 노드에서만: 실패 정보 |

## Import

```python
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy, CachePolicy, TimeoutPolicy, TracePolicy, Command
from langgraph.errors import NodeError
```

## 시그니처

```python
StateGraph.add_node(
    node: str | StateNode,
    action: StateNode | None = None,
    *,
    defer: bool = False,
    metadata: dict[str, Any] | None = None,
    input_schema: type | None = None,
    retry_policy: RetryPolicy | Sequence[RetryPolicy] | None = None,
    cache_policy: CachePolicy | None = None,
    error_handler: StateNode | None = None,
    destinations: dict[str, str] | tuple[str, ...] | None = None,
    timeout: float | timedelta | TimeoutPolicy | None = None,
    trace_policy: TracePolicy | None = None,
) -> Self

StateGraph.add_sequence(
    nodes: Sequence[StateNode | tuple[str, StateNode]],
) -> Self
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `node` | `str \| callable` | (필수) | 노드 이름. 함수만 넘기면 함수 `__name__`이 이름이 됨 |
| `action` | `callable \| Runnable \| None` | `None` | 실행할 함수. 컴파일된 그래프를 넣으면 [서브그래프](/docs/langgraph/14-subgraphs) |
| `defer` | `bool` | `False` | `True`면 다른 모든 대기 작업이 끝난 뒤, 실행이 종료되기 직전까지 실행을 미룸. 길이가 다른 병렬 분기의 조인(join)에 사용 |
| `metadata` | `dict \| None` | `None` | 노드 메타데이터(트레이스, 그래프 시각화에 노출) |
| `input_schema` | `type \| None` | `None` | 이 노드가 받을 상태 스키마. 생략 시 함수 첫 인자의 타입 힌트, 그것도 없으면 그래프 상태 |
| `retry_policy` | `RetryPolicy \| Sequence[RetryPolicy] \| None` | `None` | 실패 시 재시도. 시퀀스면 예외에 처음 매칭되는 정책 적용 ([정책](/docs/langgraph/16-policies)) |
| `cache_policy` | `CachePolicy \| None` | `None` | 입력 기반 결과 캐시. `compile(cache=...)` 필요 |
| `error_handler` | `callable \| None` | `None` | 노드가 (재시도 후에도) 실패하면 대신 실행되는 핸들러. `NodeError`를 주입받고 dict 또는 `Command`를 반환 |
| `destinations` | `dict[str, str] \| tuple[str, ...] \| None` | `None` | `Command(goto=...)`로 이동할 수 있는 노드 목록. **그래프 시각화용**이며 실행에는 영향 없음. dict면 `{노드: 엣지 라벨}` |
| `timeout` | `float \| timedelta \| TimeoutPolicy \| None` | `None` | 노드 시도(attempt)당 제한 시간. 숫자는 `TimeoutPolicy(run_timeout=...)`로 변환. **async 노드 전용** |
| `trace_policy` | `TracePolicy \| None` | `None` | 트레이스에 기록할 입력/출력을 가공(`process_inputs`, `process_outputs`). 비밀 마스킹 용도는 아님 |

`NodeError` 필드: `node: str`(실패한 노드 이름), `error: BaseException`(원래 예외).

## 메서드와 반환값

노드 함수가 반환할 수 있는 값:

| 반환 | 의미 |
|---|---|
| `dict` | 상태 부분 업데이트 |
| `None` | 업데이트 없음 |
| `Command(update=..., goto=...)` | 업데이트 + 다음 노드 지정 ([Command](/docs/langgraph/06-command)) |
| `list[Send]`(조건부 엣지 함수에서) | 동적 팬아웃 ([Send](/docs/langgraph/07-send)) |

`add_node`/`add_sequence`는 `Self`를 반환합니다.

## 예제

### 재시도 + 오류 핸들러

```python
import operator
from typing import Annotated, TypedDict

from langgraph.errors import NodeError
from langgraph.graph import StateGraph, START
from langgraph.types import Command, RetryPolicy


class State(TypedDict):
    status: str
    log: Annotated[list[str], operator.add]


def call_api(state: State) -> dict:
    raise ConnectionError("upstream down")  # 항상 실패하는 외부 호출


def on_error(state: State, error: NodeError) -> Command:
    # 재시도를 모두 소진한 뒤 호출된다
    return Command(update={"status": "degraded", "log": [f"{error.node} 실패: {error.error}"]})


builder = StateGraph(State)
builder.add_node(
    "call_api",
    call_api,
    retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.01),
    error_handler=on_error,
)
builder.add_edge(START, "call_api")
graph = builder.compile()

print(graph.invoke({"status": "ok", "log": []}))
# {'status': 'degraded', 'log': ['call_api 실패: upstream down']}
```

### defer로 길이가 다른 분기 조인

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START


class State(TypedDict):
    out: Annotated[list[str], operator.add]


builder = StateGraph(State)
builder.add_node("a", lambda s: {"out": ["a"]})
builder.add_node("b1", lambda s: {"out": ["b1"]})
builder.add_node("b2", lambda s: {"out": ["b2"]})
builder.add_node("join", lambda s: {"out": ["join"]}, defer=True)  # 모든 분기가 끝난 뒤 한 번 실행
builder.add_edge(START, "a")
builder.add_edge(START, "b1")
builder.add_edge("b1", "b2")
builder.add_edge("a", "join")
builder.add_edge("b2", "join")

print(builder.compile().invoke({"out": []}))
# {'out': ['a', 'b1', 'b2', 'join']}
```

### 타임아웃 (async 노드)

```python
import asyncio
from typing import TypedDict

from langgraph.errors import NodeTimeoutError
from langgraph.graph import StateGraph, START
from langgraph.types import TimeoutPolicy


class State(TypedDict):
    x: int


async def slow(state: State) -> dict:
    await asyncio.sleep(2)
    return {"x": 1}


builder = StateGraph(State)
builder.add_node("slow", slow, timeout=TimeoutPolicy(run_timeout=0.2))
builder.add_edge(START, "slow")
graph = builder.compile()

try:
    asyncio.run(graph.ainvoke({"x": 0}))
except NodeTimeoutError as e:
    print("timeout:", e.kind, e)  # timeout: run Node 'slow' exceeded its run timeout ...
```

## 주의사항

> [!WARNING]
> `timeout`은 **async 노드에서만** 동작합니다. 동기 함수 노드에 `timeout`을 주면 실행 시 `ValueError: Node timeouts are only supported for async nodes ...`가 발생합니다. 또한 async 노드 안에서 `time.sleep()` 같은 블로킹 호출을 하면 취소가 늦어집니다.

> [!WARNING]
> `destinations`는 `get_graph()` 시각화에 엣지를 그려 줄 뿐, 라우팅을 제한하거나 검증하지 않습니다. 실제 이동은 노드가 반환하는 `Command(goto=...)`가 결정합니다. 반환 타입 힌트 `-> Command[Literal["x", "y"]]`로도 같은 효과를 낼 수 있습니다.

> [!TIP]
> `retry_policy`의 기본 `retry_on`은 `ValueError`, `TypeError`, `KeyError` 같은 프로그래밍 오류는 재시도하지 **않습니다**. 테스트할 때는 `ConnectionError`처럼 재시도 대상 예외를 쓰세요.

## 관련 문서

- [정책: RetryPolicy / CachePolicy / TimeoutPolicy](/docs/langgraph/16-policies)
- [엣지](/docs/langgraph/05-edges)
- [Command](/docs/langgraph/06-command)
- [오류](/docs/langgraph/18-errors)
- [Runtime과 context_schema](/docs/langgraph/12-runtime-context)
