---
title: "서브그래프 (Subgraphs)"
description: "컴파일된 그래프를 노드로 넣거나 노드 안에서 호출하기, 상태 공유/변환, 체크포인터 설정, 서브그래프 스트리밍과 상태 조회"
order: 14
source: "https://docs.langchain.com/oss/python/langgraph/use-subgraphs"
tags: [subgraph, multi-agent, composition, namespace]
---

서브그래프(Subgraph)는 다른 그래프의 노드로 쓰이는 컴파일된 그래프입니다. 멀티 에이전트 시스템, 재사용 가능한 컴포넌트, 팀별 독립 개발에 씁니다. `create_agent`가 반환하는 에이전트도 컴파일된 그래프이므로 서브그래프로 넣을 수 있습니다.

| 방식 | 언제 | 방법 |
|---|---|---|
| 노드로 직접 추가 | 부모와 서브그래프가 **상태 키를 공유** | `builder.add_node("sub", compiled_sub)` |
| 노드 함수 안에서 호출 | 상태 스키마가 **다름** | 노드에서 입력 변환 → `sub.invoke()` → 출력 변환 |

## Import

```python
from langgraph.graph import StateGraph
from langgraph.types import Command
```

## 시그니처

```python
# 방식 1: 컴파일된 그래프를 action으로
StateGraph.add_node(node: str, action: CompiledStateGraph, ...) -> Self

# 서브그래프 compile 시 checkpointer 의미
sub_builder.compile(checkpointer: None | bool | BaseCheckpointSaver = None)
```

## 파라미터

서브그래프 `compile(checkpointer=...)` 값:

| 값 | 의미 |
|---|---|
| `None` (기본) | 부모의 체크포인터를 상속. 호출마다 새 상태로 시작(per-invocation). interrupt 가능 |
| `True` | 부모 체크포인터를 상속하고 서브그래프 상태를 **같은 스레드 내에서 호출 간 유지**(per-thread). 서브 에이전트가 이전 대화를 기억해야 할 때 |
| `False` | 체크포인트를 쓰지 않음. interrupt 불가, 상태 조회 불가 |
| `BaseCheckpointSaver` 인스턴스 | 서브그래프에 별도 체크포인터 지정(일반적이지 않음) |

관련 인자:

| 파라미터 | 위치 | 설명 |
|---|---|---|
| `subgraphs=True` | `stream()` | 서브그래프 내부 이벤트도 스트리밍 |
| `subgraphs=True` | `get_state()` | `StateSnapshot.tasks[*].state`에 서브그래프 스냅샷 포함 |
| `xray=True \| int` | `get_graph()` | 서브그래프 내부 구조까지 그리기 |
| `graph=Command.PARENT` | `Command` | 서브그래프 노드에서 부모 노드로 이동 |

## 메서드와 반환값

- 서브그래프 노드의 업데이트는 **공유 키만** 부모 상태에 반영됩니다(출력 스키마 기준).
- 스트리밍 시 서브그래프 이벤트의 네임스페이스는 `("부모노드명:<task_id>",)` 형태 튜플입니다.
- `CompiledStateGraph.get_subgraphs(namespace=None, recurse=False)`로 등록된 서브그래프 목록을 얻습니다.

## 예제

### 공유 키로 직접 추가 + 스트리밍

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START


class State(TypedDict):
    log: Annotated[list[str], operator.add]


sub = (
    StateGraph(State)
    .add_node("plan", lambda s: {"log": ["sub:plan"]})
    .add_node("act", lambda s: {"log": ["sub:act"]})
    .add_edge(START, "plan")
    .add_edge("plan", "act")
    .compile()
)

parent = (
    StateGraph(State)
    .add_node("worker", sub)                     # 컴파일된 그래프를 노드로
    .add_node("report", lambda s: {"log": ["report"]})
    .add_edge(START, "worker")
    .add_edge("worker", "report")
    .compile()
)

for part in parent.stream({"log": []}, stream_mode="updates", subgraphs=True, version="v2"):
    print(part["ns"], part["data"])
# ('worker:<id>',) {'plan': ...} / ('worker:<id>',) {'act': ...} / () {'worker': ...} / () {'report': ...}
```

### 스키마가 다른 서브그래프 (변환 래퍼)

```python
from typing import TypedDict

from langgraph.graph import StateGraph, START


class SubState(TypedDict):
    query: str
    hits: list[str]


class ParentState(TypedDict):
    question: str
    answer: str


search = (
    StateGraph(SubState)
    .add_node("search", lambda s: {"hits": [f"doc about {s['query']}"]})
    .add_edge(START, "search")
    .compile()
)


def call_search(state: ParentState) -> dict:
    out = search.invoke({"query": state["question"], "hits": []})  # 입력 변환
    return {"answer": "; ".join(out["hits"])}                      # 출력 변환


graph = StateGraph(ParentState).add_node("call_search", call_search).add_edge(START, "call_search").compile()
print(graph.invoke({"question": "LangGraph", "answer": ""}))
```

## 주의사항

> [!WARNING]
> 같은 부모 노드 안에서 체크포인트를 쓰는 서브그래프를 여러 번 호출하면 체크포인트 네임스페이스가 충돌해 `MULTIPLE_SUBGRAPHS` 오류가 날 수 있습니다. 병렬 호출이 필요하면 `Send`로 각각 다른 태스크에서 실행하거나 `checkpointer=False`로 컴파일하세요.

> [!WARNING]
> 부모에서 interrupt 후 재개하면, interrupt가 걸린 서브그래프를 **호출한 부모 노드도** 처음부터 다시 실행됩니다. 부모 노드의 서브그래프 호출 앞 코드에 부작용을 두지 마세요.

> [!TIP]
> 서브 에이전트별로 메시지 기록을 분리하고 싶다면 부모와 서브그래프가 `messages` 키를 공유하지 않도록 변환 래퍼 방식을 쓰세요.

## 관련 문서

- [Command (Command.PARENT)](/docs/langgraph/06-command)
- [스트리밍 (subgraphs=True)](/docs/langgraph/11-streaming)
- [CompiledStateGraph: get_state(subgraphs=True)](/docs/langgraph/15-compiled-graph)
- [langgraph-supervisor](/docs/integrations/07-supervisor) · [langgraph-swarm](/docs/integrations/08-swarm)
- [오류: MULTIPLE_SUBGRAPHS](/docs/langgraph/18-errors)
