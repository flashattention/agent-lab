---
title: "CompiledStateGraph 메서드"
description: "invoke/stream/astream, get_state, get_state_history, update_state, bulk_update_state, get_graph, get_subgraphs, with_config, clear_cache와 StateSnapshot"
order: 15
source: "https://reference.langchain.com/python/langgraph/graphs/"
tags: [compiled-graph, invoke, state, time-travel, visualization]
---

`StateGraph.compile()`(및 `create_agent`, `@entrypoint`)이 반환하는 객체입니다. LangChain `Runnable` 인터페이스(`invoke`, `stream`, `batch`, `ainvoke`, `astream`, `abatch`, `astream_events`)에 더해 상태 조회·수정·시각화 메서드를 제공합니다.

## Import

```python
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot, StateUpdate, GraphOutput
```

## 시그니처

```python
invoke(input, config=None, *, context=None, stream_mode="values", print_mode=(),
       output_keys=None, interrupt_before=None, interrupt_after=None,
       durability=None, control=None, version: Literal["v1", "v2"] = "v1") -> dict | GraphOutput

stream(input, config=None, *, context=None, stream_mode=None, print_mode=(), output_keys=None,
       interrupt_before=None, interrupt_after=None, durability=None, control=None,
       subgraphs=False, debug=None, version="v1") -> Iterator

get_state(config: RunnableConfig, *, subgraphs: bool = False) -> StateSnapshot
get_state_history(config: RunnableConfig, *, filter: dict | None = None,
                  before: RunnableConfig | None = None, limit: int | None = None) -> Iterator[StateSnapshot]
update_state(config: RunnableConfig, values: dict | Any | None,
             as_node: str | None = None, task_id: str | None = None) -> RunnableConfig
bulk_update_state(config: RunnableConfig, supersteps: Sequence[Sequence[StateUpdate]]) -> RunnableConfig
get_graph(config: RunnableConfig | None = None, *, xray: int | bool = False) -> Graph
get_subgraphs(*, namespace: str | None = None, recurse: bool = False) -> Iterator[tuple[str, PregelProtocol]]
with_config(config: RunnableConfig | None = None, **kwargs) -> Self
clear_cache(nodes: Sequence[str] | None = None) -> None
```

각각 `aget_state`, `aget_state_history`, `aupdate_state`, `abulk_update_state`, `aclear_cache` 비동기 버전이 있습니다.

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `input` | `dict \| Command \| None` | (필수) | 초기 상태, `Command(resume=...)`, 또는 `None`(마지막 체크포인트에서 이어서) |
| `config` | `RunnableConfig \| None` | `None` | `configurable.thread_id`, `recursion_limit`(기본 25), `max_concurrency`, `tags`, `callbacks` 등 |
| `context` | `ContextT \| None` | `None` | 런타임 컨텍스트 |
| `stream_mode` (invoke) | `StreamMode` | `"values"` | invoke 내부 스트림 모드. 보통 변경하지 않음 |
| `version` | `"v1" \| "v2"` | `"v1"` | invoke: v2면 `GraphOutput(value, interrupts)` 반환 |
| `durability` | `Durability \| None` | `None`(→`"async"`) | [durability](/docs/langgraph/19-durability) |
| `as_node` | `str \| None` | `None` | `update_state`: 이 노드가 업데이트한 것처럼 기록. 다음 실행 노드가 이 노드의 엣지로 결정됨 |
| `filter` / `before` / `limit` | | `None` | `get_state_history`: 메타데이터 필터, 특정 체크포인트 이전, 최대 개수 |
| `xray` | `int \| bool` | `False` | `get_graph`: 서브그래프 펼치기(정수=깊이) |

### StateSnapshot 필드

| 필드 | 설명 |
|---|---|
| `values` | 해당 시점의 상태 값 |
| `next` | 다음에 실행될 노드 이름 튜플. `()`이면 종료 |
| `config` | 이 체크포인트를 가리키는 config(`thread_id`, `checkpoint_id`, `checkpoint_ns`) |
| `metadata` | `source`(`"input"`, `"loop"`, `"update"`, `"fork"`), `step`, 노드 쓰기 등 |
| `created_at` | 생성 시각(ISO 문자열) |
| `parent_config` | 이전 체크포인트 config |
| `tasks` | 이 스텝에서 실행할 `PregelTask` 튜플(`id`, `name`, `error`, `interrupts`, `state`, `result`) |
| `interrupts` | 대기 중인 `Interrupt` 튜플 |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `invoke` | `dict` / `GraphOutput` | 최종 상태(출력 스키마 기준). interrupt 시 `"__interrupt__"` 키 포함 |
| `get_state` | `StateSnapshot` | 스레드의 최신(또는 config의 `checkpoint_id`) 스냅샷 |
| `get_state_history` | `Iterator[StateSnapshot]` | 최신 → 과거 순 |
| `update_state` | `RunnableConfig` | 새 체크포인트를 만들고 그 config 반환(리듀서 적용됨) |
| `bulk_update_state` | `RunnableConfig` | 여러 슈퍼스텝 분량의 업데이트를 한 번에 적용 |
| `get_graph` | `Graph` | `.draw_mermaid()`, `.draw_mermaid_png()`, `.draw_ascii()`(grandalf 필요) |
| `get_subgraphs` | `Iterator[(name, graph)]` | 서브그래프 목록 |
| `with_config` | 새 그래프 | 기본 config 바인딩(예: `recursion_limit`) |
| `clear_cache` | `None` | 노드 캐시 삭제(`cache=` 필요) |

## 예제

### 상태 조회·수정·타임 트래블

```python
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START


class State(TypedDict):
    log: Annotated[list[str], operator.add]


builder = StateGraph(State)
builder.add_node("draft", lambda s: {"log": ["draft"]})
builder.add_node("publish", lambda s: {"log": ["publish"]})
builder.add_edge(START, "draft")
builder.add_edge("draft", "publish")
graph = builder.compile(checkpointer=InMemorySaver(), interrupt_before=["publish"])

cfg = {"configurable": {"thread_id": "doc-1"}}
graph.invoke({"log": []}, cfg)

snap = graph.get_state(cfg)
print(snap.next, snap.values)                 # ('publish',) {'log': ['draft']}

graph.update_state(cfg, {"log": ["edited-by-human"]})  # 리듀서 적용 → 추가됨
print(graph.invoke(None, cfg))                # None 입력 = 이어서 실행

for h in graph.get_state_history(cfg):        # 최신 → 과거
    print(h.metadata["step"], h.metadata["source"], h.next)

# 과거 체크포인트에서 포크(fork)하여 재실행
first = list(graph.get_state_history(cfg))[-2]  # step 0, next=('draft',)
print(graph.invoke(None, first.config))         # draft 재실행 후 publish 앞에서 다시 정지: {'log': ['draft']}
```

### 시각화

```python
from typing import TypedDict

from langgraph.graph import StateGraph, START


class State(TypedDict):
    x: int


graph = StateGraph(State).add_node("a", lambda s: {}).add_edge(START, "a").compile()
print(graph.get_graph().draw_mermaid())       # Mermaid 텍스트
# Jupyter: from IPython.display import Image; Image(graph.get_graph().draw_mermaid_png())
```

## 주의사항

> [!WARNING]
> `get_state`, `update_state`, `get_state_history`는 체크포인터가 없으면 `ValueError: No checkpointer set`이 발생합니다.

> [!WARNING]
> `update_state`의 값도 **리듀서를 거칩니다**. `operator.add` 키를 교체하려면 `Overwrite(...)`, 메시지 삭제는 `RemoveMessage`를 쓰세요. 또한 `as_node`를 생략하면 마지막으로 실행된 노드로 간주되어 `next`가 바뀔 수 있습니다.

> [!TIP]
> `draw_mermaid_png()`는 기본적으로 외부 mermaid.ink API를 호출합니다. 오프라인 환경에서는 `draw_mermaid()` 텍스트를 쓰세요.

## 관련 문서

- [StateGraph](/docs/langgraph/01-state-graph)
- [스트리밍](/docs/langgraph/11-streaming)
- [체크포인터](/docs/langgraph/09-checkpointers)
- [interrupt](/docs/langgraph/08-interrupt)
- [서브그래프](/docs/langgraph/14-subgraphs)
