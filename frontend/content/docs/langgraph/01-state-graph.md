---
title: "StateGraph"
description: "공유 상태(State)를 읽고 쓰는 노드로 그래프를 정의하는 빌더 클래스"
order: 1
source: "https://docs.langchain.com/oss/python/langgraph/graph-api"
tags: [graph, state, builder]
---

`StateGraph`는 LangGraph의 핵심 빌더(Builder)입니다. 상태 스키마(State schema)를 받아 노드(Node)와 엣지(Edge)를 등록하고, `compile()`로 실행 가능한 `CompiledStateGraph`를 만듭니다. 각 노드는 현재 상태를 입력으로 받아 **부분 업데이트(partial update)** 딕셔너리를 반환하고, 그 업데이트는 키별 리듀서(Reducer)를 거쳐 상태에 합쳐집니다.

`StateGraph` 자체는 실행할 수 없습니다. 반드시 `compile()`을 호출해야 합니다.

## Import

```python
from langgraph.graph import StateGraph, START, END
```

## 시그니처

```python
StateGraph(
    state_schema: type[StateT],
    context_schema: type[ContextT] | None = None,
    *,
    input_schema: type[InputT] | None = None,
    output_schema: type[OutputT] | None = None,
)

StateGraph.compile(
    checkpointer: Checkpointer = None,
    *,
    cache: BaseCache | None = None,
    store: BaseStore | None = None,
    interrupt_before: All | list[str] | None = None,
    interrupt_after: All | list[str] | None = None,
    debug: bool = False,
    name: str | None = None,
    transformers: Sequence[Callable[[tuple[str, ...]], Any]] | None = None,
) -> CompiledStateGraph
```

## 파라미터

### 생성자

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `state_schema` | `type` | (필수) | 그래프 전체 상태 스키마. `TypedDict`, `dataclass`, Pydantic `BaseModel` 가능. `Annotated[타입, 리듀서]`로 키별 리듀서 지정 |
| `context_schema` | `type \| None` | `None` | 실행 시 `context=`로 넘기는 불변 런타임 컨텍스트(Runtime context)의 스키마. [Runtime](/docs/langgraph/12-runtime-context) 참고 |
| `input_schema` | `type \| None` | `None` | 그래프 입력으로 받을 키 집합. 생략 시 `state_schema` |
| `output_schema` | `type \| None` | `None` | 그래프 출력으로 돌려줄 키 집합. 생략 시 `state_schema` |

> [!NOTE]
> v0.x의 `config_schema`, `input`, `output` 키워드는 deprecated입니다. `context_schema`, `input_schema`, `output_schema`를 쓰세요.

### compile()

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `checkpointer` | `BaseCheckpointSaver \| bool \| None` | `None` | 상태 영속화. `interrupt`, 대화 기억, 타임 트래블에 필수. 서브그래프에서는 `True`/`False`/`None` 의미가 다름([서브그래프](/docs/langgraph/14-subgraphs)) |
| `cache` | `BaseCache \| None` | `None` | 노드 `cache_policy`에 쓰일 캐시 백엔드(`InMemoryCache`, `SqliteCache` 등) |
| `store` | `BaseStore \| None` | `None` | 스레드를 넘나드는 장기 기억 저장소 |
| `interrupt_before` | `"*" \| list[str] \| None` | `None` | 해당 노드 **실행 전** 정지하는 정적 브레이크포인트 |
| `interrupt_after` | `"*" \| list[str] \| None` | `None` | 해당 노드 **실행 후** 정지 |
| `debug` | `bool` | `False` | 디버그 출력 |
| `name` | `str \| None` | `None` | 그래프 이름. 서브그래프/트레이스에서 표시 |
| `transformers` | `Sequence[Callable] \| None` | `None` | 스트림 변환기 팩토리(고급 기능) |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `add_node(name, action, **opts)` | `Self` | 노드 등록. [노드](/docs/langgraph/04-nodes) |
| `add_edge(start, end)` | `Self` | 고정 엣지. `start`에 리스트를 주면 조인(join) |
| `add_conditional_edges(source, path, path_map=None)` | `Self` | 조건부 분기. [엣지](/docs/langgraph/05-edges) |
| `add_sequence(nodes)` | `Self` | 노드 여러 개를 순서대로 등록하고 엣지 연결 |
| `set_entry_point(key)` | `Self` | `add_edge(START, key)`와 동일 |
| `set_conditional_entry_point(path, path_map=None)` | `Self` | `START`에서 조건부 분기 |
| `set_finish_point(key)` | `Self` | `add_edge(key, END)`와 동일 |
| `validate(interrupt=None)` | `Self` | 그래프 구조 검증(`compile()`이 자동 호출) |
| `compile(...)` | `CompiledStateGraph` | 실행 가능한 그래프. [CompiledStateGraph](/docs/langgraph/15-compiled-graph) |

모든 빌더 메서드가 `Self`를 반환하므로 메서드 체이닝이 가능합니다.

## 예제

### 기본 그래프

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    topic: str
    steps: Annotated[list[str], operator.add]  # 리듀서: 리스트 이어 붙이기


def research(state: State) -> dict:
    return {"steps": [f"research:{state['topic']}"]}


def write(state: State) -> dict:
    return {"steps": ["write"]}


graph = (
    StateGraph(State)
    .add_node("research", research)
    .add_node("write", write)
    .add_edge(START, "research")
    .add_edge("research", "write")
    .add_edge("write", END)
    .compile(name="writer")
)

print(graph.invoke({"topic": "LangGraph", "steps": []}))
# {'topic': 'LangGraph', 'steps': ['research:LangGraph', 'write']}
```

### 입력/출력 스키마 분리

```python
from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class InputState(TypedDict):
    question: str


class OutputState(TypedDict):
    answer: str


class OverallState(InputState, OutputState):
    scratch: str  # 내부 전용 키


def think(state: InputState) -> dict:
    return {"scratch": state["question"].upper()}


def answer(state: OverallState) -> dict:
    return {"answer": f"답: {state['scratch']}"}


builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_sequence([think, answer])  # 함수 이름이 노드 이름이 됨
builder.add_edge(START, "think")
builder.add_edge("answer", END)
graph = builder.compile()

print(graph.invoke({"question": "hi"}))  # {'answer': '답: HI'}  (scratch는 출력에서 제외)
```

## 주의사항

> [!WARNING]
> 노드는 상태 전체가 아니라 **바뀐 키만** 담은 딕셔너리를 반환해야 합니다. 리듀서가 없는 키는 반환한 값으로 덮어써지고, 리듀서가 있는 키(예: `operator.add`)는 상태 전체를 반환하면 값이 중복됩니다.

> [!WARNING]
> `compile()`하지 않은 `StateGraph`에는 `invoke`가 없습니다. 또한 `START`에서 나가는 엣지가 없으면(`Graph must have an entrypoint`) 또는 등록되지 않은 노드로 엣지를 걸면(`Found edge ending at unknown node`) `compile()` 시점에 `ValueError`가 발생합니다. 반면 `END`로 가는 엣지가 없는 노드는 허용되며, 나가는 엣지가 없으면 그 경로에서 실행이 끝납니다.

> [!TIP]
> `MessageGraph`는 v1에서 제거 대상(deprecated)입니다. 메시지 기반 그래프는 `StateGraph(MessagesState)`를 쓰세요.

## 관련 문서

- [상태와 리듀서](/docs/langgraph/02-state-reducers)
- [MessagesState](/docs/langgraph/03-messages-state)
- [노드](/docs/langgraph/04-nodes) · [엣지](/docs/langgraph/05-edges)
- [CompiledStateGraph 메서드](/docs/langgraph/15-compiled-graph)
- [create_agent](/docs/langchain/06-create-agent): 미리 만들어진 에이전트 그래프
