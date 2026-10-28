---
title: "Send"
description: "조건부 엣지에서 노드를 개별 입력으로 여러 번 실행하는 동적 팬아웃(map-reduce)"
order: 7
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#send"
tags: [send, map-reduce, fan-out, parallel]
---

`Send`는 "이 노드를 **이 입력으로** 실행하라"는 메시지입니다. 조건부 엣지 함수(또는 `Command(goto=...)`)가 `Send` 리스트를 반환하면, 각 `Send`가 다음 슈퍼스텝에서 병렬로 실행됩니다. 실행 개수를 런타임에 정할 수 있어 맵-리듀스(map-reduce) 패턴에 씁니다.

`Send`로 실행된 노드는 그래프 상태가 아니라 `arg`를 입력으로 받습니다. 결과는 일반 노드처럼 그래프 상태에 병합되므로, 수집 키에는 리듀서가 필요합니다.

## Import

```python
from langgraph.types import Send
```

## 시그니처

```python
class Send:
    def __init__(
        self,
        node: str,
        arg: Any,
        *,
        timeout: float | timedelta | TimeoutPolicy | None = None,
    ) -> None: ...
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `node` | `str` | (필수) | 실행할 노드 이름 |
| `arg` | `Any` | (필수) | 그 노드에 넘길 입력(그래프 상태와 다른 스키마도 가능) |
| `timeout` | `float \| timedelta \| TimeoutPolicy \| None` | `None` | 이 Send 실행에만 적용할 타임아웃. 노드의 `timeout`보다 우선. async 노드 전용 |

## 메서드와 반환값

속성 `node`, `arg`, `timeout`을 가진 값 객체입니다. 반환 위치:

| 위치 | 형태 |
|---|---|
| 조건부 엣지 함수 | `return [Send("worker", x) for x in items]` |
| 노드의 Command | `return Command(goto=[Send("worker", x) for x in items])` |

## 예제

### 맵-리듀스

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send


class State(TypedDict):
    topics: list[str]
    summaries: Annotated[list[str], operator.add]  # 병렬 결과 수집용 리듀서


class WorkerInput(TypedDict):
    topic: str


def fan_out(state: State) -> list[Send]:
    return [Send("summarize", {"topic": t}) for t in state["topics"]]


def summarize(item: WorkerInput) -> dict:
    return {"summaries": [f"{item['topic']} 요약"]}


def reduce(state: State) -> dict:
    print("수집 개수:", len(state["summaries"]))
    return {}


builder = StateGraph(State)
builder.add_node("summarize", summarize)
builder.add_node("reduce", reduce)
builder.add_conditional_edges(START, fan_out, ["summarize"])
builder.add_edge("summarize", "reduce")
builder.add_edge("reduce", END)

print(builder.compile().invoke({"topics": ["RAG", "Agent", "MCP"], "summaries": []}))
```

## 주의사항

> [!WARNING]
> 수집 키(`summaries`)에 리듀서가 없으면 여러 Send 결과가 같은 스텝에 쓰여 `InvalidUpdateError`가 납니다.

> [!WARNING]
> `Send` 대상 노드는 `arg`만 받습니다. 그래프 상태의 다른 키가 필요하면 `arg`에 직접 넣어 보내세요.

> [!TIP]
> `add_conditional_edges`의 세 번째 인자로 `["summarize"]`처럼 목적지를 알려 주면 `get_graph()` 시각화가 정확해집니다.

> [!TIP]
> 팬아웃 개수에 상한을 두세요. 입력 리스트가 크면 LLM 호출이 동시에 폭증합니다. 동시성은 `config={"max_concurrency": N}`으로 제한할 수 있습니다.

## 관련 문서

- [엣지와 조건부 엣지](/docs/langgraph/05-edges)
- [Command](/docs/langgraph/06-command)
- [상태와 리듀서](/docs/langgraph/02-state-reducers)
- [함수형 API](/docs/langgraph/13-functional-api): `task` 병렬 호출로 같은 패턴 구현
