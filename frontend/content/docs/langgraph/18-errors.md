---
title: "오류 (Errors)"
description: "langgraph.errors의 예외 클래스: GraphRecursionError, InvalidUpdateError, GraphInterrupt, NodeTimeoutError, GraphDrained 등과 ErrorCode"
order: 18
source: "https://docs.langchain.com/oss/python/langgraph/errors"
tags: [errors, exceptions, recursion-limit, troubleshooting]
---

LangGraph 실행 중 발생하는 예외는 `langgraph.errors`에 정의되어 있습니다. 일부는 사용자에게 보이는 실패이고, 일부(`GraphBubbleUp` 계열)는 interrupt/Command 전달을 위한 **내부 제어 흐름용** 예외입니다.

## Import

```python
from langgraph.errors import (
    GraphRecursionError, InvalidUpdateError, GraphInterrupt, NodeInterrupt,
    GraphBubbleUp, ParentCommand, EmptyInputError, EmptyChannelError, TaskNotFound,
    NodeTimeoutError, NodeCancelledError, GraphDrained, NodeError, ErrorCode,
)
from langgraph.runtime import RunControl
```

## 시그니처

```python
class GraphRecursionError(RecursionError): ...
class InvalidUpdateError(Exception): ...
class GraphBubbleUp(Exception): ...
class GraphInterrupt(GraphBubbleUp): ...
class ParentCommand(GraphBubbleUp): ...
class NodeTimeoutError(Exception):   # TimeoutError 비상속
    def __init__(self, node: str, elapsed: float, *, kind: Literal["idle", "run"],
                 idle_timeout: float | None = None, run_timeout: float | None = None): ...
class GraphDrained(GraphBubbleUp):
    def __init__(self, reason: str = "shutdown"): ...

@dataclass(frozen=True)
class NodeError:            # 예외가 아니라 error_handler에 주입되는 컨텍스트
    node: str
    error: BaseException
```

## 파라미터

| 클래스 | 언제 발생 | 대응 |
|---|---|---|
| `GraphRecursionError` | 슈퍼스텝 수가 `recursion_limit`(기본 25)을 초과 | 루프 종료 조건 점검, `config={"recursion_limit": N}` |
| `InvalidUpdateError` | 리듀서 없는 키에 한 스텝에서 여러 값, 노드가 dict 아닌 값 반환, `Overwrite` 중복 | 리듀서 추가, 반환 형식 수정 |
| `GraphInterrupt` | `interrupt()` 호출 시 내부적으로 발생 | 잡지 말 것. 체크포인터 + `Command(resume=)` |
| `NodeInterrupt` | (deprecated, `GraphInterrupt` 하위) v0.x 노드 내 인터럽트 | `interrupt()` 사용 |
| `GraphBubbleUp` | interrupt/부모 Command 전파용 기반 클래스 | 잡지 말 것 |
| `ParentCommand` | `Command(graph=Command.PARENT)` 전달용 | 잡지 말 것 |
| `EmptyInputError` | 그래프에 빈 입력 | 입력 확인 |
| `EmptyChannelError` | 값이 없는 채널 읽기(내부) | |
| `TaskNotFound` | 분산 실행에서 태스크를 찾지 못함 | |
| `NodeTimeoutError` | 노드가 `timeout`(run/idle) 초과. 속성 `node`, `elapsed`, `kind`, `idle_timeout`, `run_timeout` | `TimeoutPolicy` 조정. 기본 RetryPolicy 재시도 대상 |
| `NodeCancelledError` | 노드 본문이 `asyncio.CancelledError`를 직접 발생 | 실패로 보고됨 |
| `GraphDrained` | `RunControl.request_drain()`으로 슈퍼스텝 경계에서 협조적 중단. 체크포인트 저장됨. `GraphBubbleUp` 하위 클래스 | 같은 thread로 `invoke(None, config)` 재개 |

### ErrorCode

`ErrorCode` 값은 오류 메시지의 트러블슈팅 링크(`https://docs.langchain.com/oss/python/langgraph/<CODE>`)에 쓰입니다.

| 값 | 의미 |
|---|---|
| `GRAPH_RECURSION_LIMIT` | 재귀 한도 초과 |
| `INVALID_CONCURRENT_GRAPH_UPDATE` | 같은 스텝에서 리듀서 없는 키에 동시 쓰기 |
| `INVALID_GRAPH_NODE_RETURN_VALUE` | 노드가 dict/Command가 아닌 값 반환 |
| `MULTIPLE_SUBGRAPHS` | 한 노드에서 체크포인트 쓰는 서브그래프 여러 번 호출 |
| `INVALID_CHAT_HISTORY` | tool_calls에 대응하는 ToolMessage 누락 등 메시지 기록 오류 |

## 메서드와 반환값

`RunControl` (협조적 중단):

| 멤버 | 설명 |
|---|---|
| `request_drain(reason="shutdown")` | 현재 슈퍼스텝이 끝나면 멈추도록 요청(스레드 안전) |
| `drain_requested` | 요청 여부 `bool` |
| `drain_reason` | 사유 문자열 또는 `None` |

`invoke(..., control=RunControl())` / `stream(..., control=...)`로 전달하며, 실행마다 새 인스턴스를 만듭니다.

## 예제

### GraphRecursionError

```python
from typing import TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import StateGraph, START


class State(TypedDict):
    n: int


builder = StateGraph(State)
builder.add_node("loop", lambda s: {"n": s["n"] + 1})
builder.add_edge(START, "loop")
builder.add_conditional_edges("loop", lambda s: "loop")  # 종료 조건 없는 루프
graph = builder.compile()

try:
    graph.invoke({"n": 0}, {"recursion_limit": 5})
except GraphRecursionError as e:
    print("멈춤:", str(e).splitlines()[0])
```

### InvalidUpdateError

```python
from typing import TypedDict

from langgraph.errors import InvalidUpdateError
from langgraph.graph import StateGraph, START


class State(TypedDict):
    value: str  # 리듀서 없음


builder = StateGraph(State)
builder.add_node("a", lambda s: {"value": "a"})
builder.add_node("b", lambda s: {"value": "b"})
builder.add_edge(START, "a")
builder.add_edge(START, "b")  # 같은 스텝에서 같은 키에 쓰기

try:
    builder.compile().invoke({"value": ""})
except InvalidUpdateError as e:
    print(type(e).__name__, str(e).splitlines()[0])
```

### GraphDrained로 우아한 종료

```python
import threading
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphDrained
from langgraph.graph import StateGraph, START
from langgraph.runtime import RunControl


class State(TypedDict):
    steps: int


control = RunControl()


def step(state: State) -> dict:
    if state["steps"] == 2:
        control.request_drain("SIGTERM")  # 예: 시그널 핸들러에서 호출
    return {"steps": state["steps"] + 1}


builder = StateGraph(State)
builder.add_node("step", step)
builder.add_edge(START, "step")
builder.add_conditional_edges("step", lambda s: "step" if s["steps"] < 5 else "__end__")
graph = builder.compile(checkpointer=InMemorySaver())
cfg = {"configurable": {"thread_id": "job-1"}}

try:
    graph.invoke({"steps": 0}, cfg, control=control)
except GraphDrained as e:
    print("drained:", e, graph.get_state(cfg).values)
print("resumed:", graph.invoke(None, cfg))  # 체크포인트에서 이어서 완료
```

## 주의사항

> [!WARNING]
> 노드 안에서 `except Exception:`으로 모든 예외를 삼키면 `interrupt()`가 던지는 `GraphInterrupt`까지 잡혀 HITL이 동작하지 않습니다. 넓은 except를 쓴다면 `GraphBubbleUp`은 다시 raise 하세요.

> [!TIP]
> `NodeTimeoutError`는 내장 `TimeoutError`를 상속하지 않습니다. `except TimeoutError`로는 잡히지 않으니 명시적으로 import 하세요.

## 관련 문서

- [엣지 (루프와 recursion_limit)](/docs/langgraph/05-edges)
- [상태와 리듀서](/docs/langgraph/02-state-reducers)
- [노드 (error_handler, NodeError)](/docs/langgraph/04-nodes)
- [정책 (TimeoutPolicy)](/docs/langgraph/16-policies)
- [interrupt](/docs/langgraph/08-interrupt)
