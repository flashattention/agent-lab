---
title: "엣지와 조건부 엣지 (Edges)"
description: "add_edge, 다중 소스 조인, add_conditional_edges와 path_map, START/END"
order: 5
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#edges"
tags: [edge, conditional-edge, routing, start, end]
---

엣지(Edge)는 다음에 실행할 노드를 정합니다. LangGraph는 **슈퍼스텝(super-step)** 단위로 실행되며, 한 스텝에서 활성화된 노드들은 병렬로 실행되고 다음 스텝의 노드는 엣지로 결정됩니다.

| 종류 | API | 용도 |
|---|---|---|
| 고정 엣지 | `add_edge("a", "b")` | 항상 a → b |
| 조인 엣지 | `add_edge(["a", "b"], "c")` | a와 b가 **모두** 끝나면 c |
| 조건부 엣지 | `add_conditional_edges("a", router, path_map)` | 함수 반환값으로 분기(복수 반환 시 병렬) |
| 진입점 | `add_edge(START, "a")` | 그래프 시작 노드 |
| 종료 | `add_edge("a", END)` | 실행 종료 |

## Import

```python
from langgraph.graph import StateGraph, START, END
```

`START == "__start__"`, `END == "__end__"`인 문자열 상수입니다.

## 시그니처

```python
StateGraph.add_edge(start_key: str | list[str], end_key: str) -> Self

StateGraph.add_conditional_edges(
    source: str,
    path: Callable[..., Hashable | Sequence[Hashable]]
        | Callable[..., Awaitable[Hashable | Sequence[Hashable]]]
        | Runnable[Any, Hashable | Sequence[Hashable]],
    path_map: dict[Hashable, str] | list[str] | None = None,
) -> Self
```

## 파라미터

### add_edge

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `start_key` | `str \| list[str]` | (필수) | 출발 노드. 리스트면 모든 노드 완료를 기다리는 조인 |
| `end_key` | `str` | (필수) | 도착 노드 또는 `END` |

### add_conditional_edges

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `source` | `str` | (필수) | 분기 출발 노드(또는 `START`) |
| `path` | `callable \| Runnable` | (필수) | 상태를 받아 노드 이름, 노드 이름 리스트, 또는 `Send` 리스트를 반환 |
| `path_map` | `dict \| list[str] \| None` | `None` | `path` 반환값 → 노드 이름 매핑. 리스트면 가능한 목적지 목록. 생략 시 `path`의 반환 타입 힌트(`Literal[...]`)로 추론, 그것도 없으면 시각화 시 모든 노드로 연결된 것처럼 표시 |

## 메서드와 반환값

두 메서드 모두 `Self`를 반환합니다. 라우팅 함수 `path`의 반환값:

| 반환 | 동작 |
|---|---|
| `"node_name"` / `END` | 해당 노드로 이동 / 종료 |
| `["a", "b"]` | a, b를 다음 스텝에서 병렬 실행 |
| `[Send("node", arg), ...]` | 동적 팬아웃 ([Send](/docs/langgraph/07-send)) |
| `path_map`의 키 | 매핑된 노드로 이동 |

## 예제

### 조건부 엣지 + path_map

```python
from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    score: int
    result: str


def grade(state: State) -> dict:
    return {}


def route(state: State) -> Literal["pass", "fail"]:
    return "pass" if state["score"] >= 60 else "fail"


builder = StateGraph(State)
builder.add_node("grade", grade)
builder.add_node("celebrate", lambda s: {"result": "합격"})
builder.add_node("retry", lambda s: {"result": "재시험"})
builder.add_edge(START, "grade")
builder.add_conditional_edges("grade", route, {"pass": "celebrate", "fail": "retry"})
builder.add_edge(["celebrate"], END)
builder.add_edge("retry", END)
graph = builder.compile()

print(graph.invoke({"score": 72, "result": ""}))  # {'score': 72, 'result': '합격'}
print(graph.invoke({"score": 40, "result": ""}))  # {'score': 40, 'result': '재시험'}
```

### 병렬 분기와 조인

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    parts: Annotated[list[str], operator.add]


builder = StateGraph(State)
builder.add_node("search_web", lambda s: {"parts": ["web"]})
builder.add_node("search_docs", lambda s: {"parts": ["docs"]})
builder.add_node("merge", lambda s: {"parts": [f"merged({len(s['parts'])})"]})
builder.add_edge(START, "search_web")
builder.add_edge(START, "search_docs")
builder.add_edge(["search_web", "search_docs"], "merge")  # 둘 다 끝나야 실행
builder.add_edge("merge", END)

print(builder.compile().invoke({"parts": []}))
# {'parts': ['docs', 'web', 'merged(2)']}  (병렬 노드 결과 순서는 보장되지 않음)
```

## 주의사항

> [!WARNING]
> 루프(예: agent → tools → agent)를 만들면 반드시 종료 조건과 상한을 두세요. 상한은 `config={"recursion_limit": N}`(기본 25 슈퍼스텝)으로 걸리며, 초과 시 `GraphRecursionError`가 발생합니다.

> [!WARNING]
> 한 노드에서 고정 엣지와 조건부 엣지를 **같이** 걸면 둘 다 실행됩니다(분기가 아니라 병렬). 분기만 원하면 조건부 엣지 하나로 표현하세요.

> [!TIP]
> 라우팅과 상태 업데이트를 한 곳에서 하고 싶으면 조건부 엣지 대신 노드에서 [`Command`](/docs/langgraph/06-command)를 반환하세요.

## 관련 문서

- [StateGraph](/docs/langgraph/01-state-graph)
- [노드](/docs/langgraph/04-nodes): `defer=True`로 길이가 다른 분기 조인
- [Command](/docs/langgraph/06-command) · [Send](/docs/langgraph/07-send)
- [prebuilt tools_condition](/docs/langgraph/17-prebuilt)
- [오류: GraphRecursionError](/docs/langgraph/18-errors)
