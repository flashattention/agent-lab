---
title: "interrupt와 Human-in-the-loop"
description: "interrupt()로 실행을 멈추고 Command(resume=)로 재개하는 동적 인터럽트, interrupt_before/after 정적 브레이크포인트"
order: 8
source: "https://docs.langchain.com/oss/python/langgraph/interrupts"
tags: [interrupt, hitl, human-in-the-loop, resume, breakpoint]
---

`interrupt(value)`는 노드 실행 중에 그래프를 멈추고 `value`를 호출자에게 전달합니다. 호출자가 `graph.invoke(Command(resume=응답), config)`로 다시 실행하면, 해당 노드가 **처음부터 다시 실행**되고 이번에는 `interrupt()`가 응답 값을 반환합니다.

- 체크포인터(checkpointer)와 `thread_id`가 **필수**입니다.
- 정적 브레이크포인트 `interrupt_before` / `interrupt_after`는 노드 경계에서 멈추는 디버깅용 기능입니다.

## Import

```python
from langgraph.types import interrupt, Command, Interrupt
```

## 시그니처

```python
def interrupt(
    value: Any,
    *,
    response_schema: dict[str, Any] | type | None = None,
) -> Any: ...

class Interrupt:
    value: Any
    id: str
    response_schema: dict[str, Any] | None   # JSON Schema로 직렬화되어 보관
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `value` | `Any` | (필수) | 호출자에게 보여 줄 페이로드(JSON 직렬화 가능해야 함) |
| `response_schema` | `dict \| type \| None` | `None` | 재개 값의 스키마. Pydantic 모델/TypedDict/JSON Schema. Pydantic 모델이면 resume 값을 **검증해 모델 인스턴스로** 반환하고, 검증 실패 시 `ValidationError` |

정적 브레이크포인트(`compile()` 또는 `invoke()/stream()` 인자):

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `interrupt_before` | `"*" \| list[str] \| None` | `None` | 지정 노드 실행 직전 정지 |
| `interrupt_after` | `"*" \| list[str] \| None` | `None` | 지정 노드 실행 직후 정지 |

## 메서드와 반환값

- `interrupt()` 반환값: 재개 시 전달된 `resume` 값(또는 `response_schema` 모델 인스턴스).
- 멈춘 그래프의 `invoke()` 반환값(기본 `version="v1"`): 상태 dict에 `"__interrupt__": [Interrupt(...)]` 키가 포함됩니다.
- `invoke(..., version="v2")`: `GraphOutput(value=상태, interrupts=(Interrupt(...),))`를 반환합니다.
- `graph.get_state(config).interrupts` / `.next`로도 대기 중인 인터럽트를 확인할 수 있습니다.
- 여러 interrupt가 동시에 걸리면(병렬 노드) `Command(resume={interrupt.id: 값, ...})`로 ID별 재개.

## 예제

### 승인 요청

```python
from typing import TypedDict

from pydantic import BaseModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START
from langgraph.types import Command, interrupt


class State(TypedDict):
    action: str
    status: str


class Approval(BaseModel):
    approved: bool
    comment: str = ""


def review(state: State) -> dict:
    # 여기서 멈춘다. 재개되면 이 노드가 처음부터 다시 실행된다
    answer = interrupt({"question": f"'{state['action']}' 실행할까요?"}, response_schema=Approval)
    return {"status": "approved" if answer.approved else f"rejected: {answer.comment}"}


builder = StateGraph(State)
builder.add_node("review", review)
builder.add_edge(START, "review")
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "order-42"}}
first = graph.invoke({"action": "환불 10만원", "status": "pending"}, config)
print(first["__interrupt__"][0].value)  # {'question': "'환불 10만원' 실행할까요?"}

final = graph.invoke(Command(resume={"approved": True}), config)
print(final)  # {'action': '환불 10만원', 'status': 'approved'}
```

### 여러 인터럽트를 ID로 재개

```python
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START
from langgraph.types import Command, interrupt


class State(TypedDict):
    answers: Annotated[list[str], operator.add]


def ask(name: str):
    def node(state: State) -> dict:
        return {"answers": [f"{name}={interrupt(f'{name}?')}"]}
    return node


builder = StateGraph(State)
builder.add_node("ask_a", ask("a"))
builder.add_node("ask_b", ask("b"))
builder.add_edge(START, "ask_a")
builder.add_edge(START, "ask_b")  # 병렬 → 인터럽트 2개
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "multi"}}
out = graph.invoke({"answers": []}, config, version="v2")
resume = {intr.id: f"ans-{intr.value}" for intr in out.interrupts}
print(graph.invoke(Command(resume=resume), config))
```

### 정적 브레이크포인트

```python
# 위 예제의 builder 재사용
config = {"configurable": {"thread_id": "debug-1"}}
graph = builder.compile(checkpointer=InMemorySaver(), interrupt_before=["ask_b"])
# graph.invoke(...) 후 graph.get_state(config).next 로 멈춘 위치 확인,
# graph.invoke(None, config) 로 이어서 실행
```

## 주의사항

> [!WARNING]
> 재개 시 노드가 **처음부터 다시 실행**됩니다. `interrupt()` 앞에 있는 부작용(DB 쓰기, 결제, 이메일)은 두 번 실행됩니다. 부작용은 `interrupt()` 뒤로 옮기거나 별도 노드로 분리하세요.

> [!WARNING]
> 한 노드 안에서 여러 `interrupt()`를 호출하면 resume 값은 **호출 순서(인덱스)** 로 매칭됩니다. 조건문으로 interrupt 호출 순서가 실행마다 바뀌면 값이 엉킵니다. `interrupt()`를 `try/except`로 감싸지도 마세요(내부적으로 `GraphInterrupt` 예외를 사용).

> [!TIP]
> `create_agent`에서는 직접 interrupt를 쓰는 대신 `HumanInTheLoopMiddleware`로 도구 호출 승인/수정/거절을 구성할 수 있습니다([내장 미들웨어](/docs/langchain/07-built-in-middleware)).

## 관련 문서

- [Command](/docs/langgraph/06-command)
- [체크포인터](/docs/langgraph/09-checkpointers)
- [CompiledStateGraph: get_state / update_state](/docs/langgraph/15-compiled-graph)
- [오류: GraphInterrupt](/docs/langgraph/18-errors)
- [내장 미들웨어: HumanInTheLoopMiddleware](/docs/langchain/07-built-in-middleware)
