---
title: "Durability 모드"
description: "체크포인트를 언제 저장할지 정하는 durability 인자: sync / async / exit"
order: 19
source: "https://docs.langchain.com/oss/python/langgraph/durable-execution"
tags: [durability, checkpoint, durable-execution, performance]
---

`durability`는 체크포인터가 있을 때 **각 슈퍼스텝의 상태를 언제 저장할지** 정합니다. 내구성(장애 시 복구 지점)과 성능(저장 지연) 사이의 트레이드오프입니다. `invoke`, `stream`, `ainvoke`, `astream`의 키워드 인자로 실행마다 지정합니다.

| 모드 | 저장 시점 | 장애 복구 | 성능 |
|---|---|---|---|
| `"sync"` | 다음 스텝 시작 **전에** 동기적으로 저장 완료 | 가장 강함: 모든 스텝에서 재개 가능 | 가장 느림 |
| `"async"` (기본) | 다음 스텝 실행과 **병행**하여 비동기 저장 | 대부분 안전. 저장 중 프로세스가 죽으면 마지막 스텝 유실 가능 | 균형 |
| `"exit"` | 그래프 **종료 시(완료·오류·interrupt)에만** 저장 | 실행 도중 크래시 시 중간 상태 없음 | 가장 빠름 |

## Import

```python
from langgraph.types import Durability   # Literal["sync", "async", "exit"]
```

## 시그니처

```python
Durability = Literal["sync", "async", "exit"]

graph.invoke(input, config, *, durability: Durability | None = None, ...)
graph.stream(input, config, *, durability: Durability | None = None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `durability` | `"sync" \| "async" \| "exit" \| None` | `None` | `None`이면 config의 설정, 없으면 `"async"` |

> [!NOTE]
> v0.x의 `checkpoint_during` 인자는 deprecated입니다. `checkpoint_during=True` → `"async"`, `False` → `"exit"`로 매핑되며, `durability`와 함께 쓰면 `ValueError`입니다.

## 메서드와 반환값

반환값은 바뀌지 않습니다. 영향을 받는 것은 `get_state_history()`에 남는 체크포인트 수와 장애 시 재개 지점입니다. `"exit"` 모드에서는 중간 스텝 체크포인트가 남지 않으므로 타임 트래블 지점도 줄어듭니다.

## 예제

```python
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START


class State(TypedDict):
    n: int


builder = StateGraph(State)
builder.add_sequence([("s1", lambda s: {"n": s["n"] + 1}),
                      ("s2", lambda s: {"n": s["n"] + 1}),
                      ("s3", lambda s: {"n": s["n"] + 1})])
builder.add_edge(START, "s1")
graph = builder.compile(checkpointer=InMemorySaver())

for mode in ("sync", "async", "exit"):
    cfg = {"configurable": {"thread_id": mode}}
    out = graph.invoke({"n": 0}, cfg, durability=mode)
    history = list(graph.get_state_history(cfg))
    print(f"{mode:5} result={out} checkpoints={len(history)}")
```

## 주의사항

> [!WARNING]
> 수 분 이상 걸리는 장기 실행 작업, 외부 부작용이 큰 워크플로에서 `"exit"`를 쓰면 크래시 시 처음부터 다시 실행해야 합니다. 이런 경우 `"sync"` 또는 기본값을 쓰고, 부작용은 `@task`/노드 단위로 분리하세요.

> [!TIP]
> 짧고 재실행 비용이 낮은 그래프(예: 단일 LLM 호출 + 후처리)는 `"exit"`로 저장 I/O를 줄일 수 있습니다. interrupt 시점에는 `"exit"`에서도 저장되므로 HITL은 정상 동작합니다.

## 관련 문서

- [체크포인터](/docs/langgraph/09-checkpointers)
- [함수형 API (task로 부작용 분리)](/docs/langgraph/13-functional-api)
- [CompiledStateGraph 메서드](/docs/langgraph/15-compiled-graph)
- [interrupt](/docs/langgraph/08-interrupt)
