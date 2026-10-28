---
title: "스트리밍 (Streaming)"
description: "stream_mode 7종(values/updates/messages/custom/checkpoints/tasks/debug), 다중 모드, subgraphs, get_stream_writer, version=v2 출력 형식"
order: 11
source: "https://docs.langchain.com/oss/python/langgraph/streaming"
tags: [streaming, stream-mode, tokens, custom, stream-writer]
---

`graph.stream()` / `graph.astream()`은 실행 중간 결과를 이터레이터로 내보냅니다. `stream_mode`로 무엇을 받을지 정합니다.

| stream_mode | 내보내는 것 | 주 용도 |
|---|---|---|
| `"values"` | 매 스텝 후 **전체 상태** | 상태 변화 관찰 |
| `"updates"` | 매 스텝 **노드별 업데이트** `{node: update}` | 진행 상황 표시(stream 기본값) |
| `"messages"` | LLM 토큰 `(message_chunk, metadata)` 튜플 | 채팅 UI 토큰 스트리밍 |
| `"custom"` | 노드/도구에서 `get_stream_writer()`로 쓴 임의 데이터 | 진행률, 중간 로그 |
| `"checkpoints"` | 체크포인트 생성 이벤트(체크포인터 필요) | 영속화 관찰 |
| `"tasks"` | 태스크 시작/종료 이벤트(입력, 결과, 오류) | 실행 추적 |
| `"debug"` | checkpoints + tasks를 합친 상세 이벤트 | 디버깅 |

## Import

```python
from langgraph.config import get_stream_writer
from langgraph.types import StreamMode   # Literal 타입
```

## 시그니처

```python
CompiledStateGraph.stream(
    input: InputT | Command | None,
    config: RunnableConfig | None = None,
    *,
    context: ContextT | None = None,
    stream_mode: StreamMode | Sequence[StreamMode] | None = None,
    print_mode: StreamMode | Sequence[StreamMode] = (),
    output_keys: str | Sequence[str] | None = None,
    interrupt_before: All | Sequence[str] | None = None,
    interrupt_after: All | Sequence[str] | None = None,
    durability: Durability | None = None,
    control: RunControl | None = None,
    subgraphs: bool = False,
    debug: bool | None = None,
    version: Literal["v1", "v2"] = "v1",
) -> Iterator[dict[str, Any] | Any]

def get_stream_writer() -> Callable[[Any], None]
```

`astream()`도 같은 인자를 받고 `AsyncIterator`를 반환합니다.

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `stream_mode` | `StreamMode \| list[StreamMode] \| None` | `None` (→ 그래프 기본 `"updates"`) | 하나 또는 여러 모드 |
| `subgraphs` | `bool` | `False` | `True`면 서브그래프 내부 이벤트도 내보냄(네임스페이스 포함) |
| `version` | `"v1" \| "v2"` | `"v1"` | 출력 청크 형식(아래 표) |
| `print_mode` | `StreamMode \| Sequence` | `()` | 지정 모드를 콘솔에 출력(반환 청크에는 영향 없음) |
| `output_keys` | `str \| Sequence[str] \| None` | `None` | values/updates에 포함할 키 제한 |
| `durability` | `"sync" \| "async" \| "exit" \| None` | `None` | [durability](/docs/langgraph/19-durability) |
| `control` | `RunControl \| None` | `None` | 협조적 중단(drain) 제어([오류: GraphDrained](/docs/langgraph/18-errors)) |

### 청크 형식 (실제 출력 기준)

| 조건 | `version="v1"` | `version="v2"` |
|---|---|---|
| 단일 모드 | `chunk` | `{"type": mode, "ns": (), "data": chunk}` |
| 다중 모드 | `(mode, chunk)` | `{"type": mode, "ns": (...), "data": chunk}` |
| `subgraphs=True` | `(namespace, chunk)` 또는 `(namespace, mode, chunk)` | `{"type", "ns", "data"}` (ns에 서브그래프 경로) |

`v2`는 모드·서브그래프 조합과 무관하게 항상 같은 dict 형태라 파싱이 단순합니다.

## 메서드와 반환값

- `get_stream_writer()`: 현재 실행의 custom 스트림 writer를 반환합니다. 노드, `@task`, 도구 내부에서 호출합니다. `stream_mode`에 `"custom"`이 없으면 쓴 값은 버려집니다. 노드에서는 `runtime.stream_writer`도 같은 기능입니다.
- `"messages"` 모드 metadata에는 `langgraph_node`, `langgraph_step`, `tags` 등이 들어 있어 특정 노드의 토큰만 거를 수 있습니다.
- `astream_events(version="v2")`는 LangChain 콜백 이벤트 단위의 더 세밀한 스트림입니다.

## 예제

### updates + custom 다중 모드

```python
import operator
from typing import Annotated, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START


class State(TypedDict):
    docs: Annotated[list[str], operator.add]


def retrieve(state: State) -> dict:
    writer = get_stream_writer()
    for i in range(3):
        writer({"progress": f"{i + 1}/3"})  # custom 모드로 전송
    return {"docs": ["d1", "d2", "d3"]}


graph = StateGraph(State).add_node("retrieve", retrieve).add_edge(START, "retrieve").compile()

for mode, chunk in graph.stream({"docs": []}, stream_mode=["updates", "custom"]):
    print(mode, chunk)
# custom {'progress': '1/3'} ... updates {'retrieve': {'docs': ['d1', 'd2', 'd3']}}

for part in graph.stream({"docs": []}, stream_mode=["updates", "custom"], version="v2"):
    print(part["type"], part["ns"], part["data"])
```

### LLM 토큰 스트리밍 (messages)

```python
import os

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, MessagesState

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def chat(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}  # invoke여도 토큰이 스트리밍된다


graph = StateGraph(MessagesState).add_node("chat", chat).add_edge(START, "chat").compile()

for token, meta in graph.stream({"messages": [("user", "안녕")]}, stream_mode="messages"):
    if meta["langgraph_node"] == "chat" and token.content:
        print(token.content, end="|", flush=True)
print()
```

## 주의사항

> [!WARNING]
> 다중 모드(`stream_mode=[...]`)나 `subgraphs=True`를 켜면 v1 청크가 튜플로 바뀝니다. 단일 모드용 코드를 그대로 두면 언패킹 오류가 납니다. 새 코드에서는 `version="v2"`를 권장합니다.

> [!WARNING]
> `"checkpoints"`와 `"debug"`의 체크포인트 이벤트는 체크포인터가 있어야 나옵니다. 체크포인터 없이 `"checkpoints"`만 요청하면 아무것도 나오지 않습니다.

> [!TIP]
> `invoke()`도 `version="v2"`를 받습니다. 이때 반환값은 `GraphOutput(value=..., interrupts=(...))`입니다.

## 관련 문서

- [CompiledStateGraph 메서드](/docs/langgraph/15-compiled-graph)
- [Runtime (stream_writer)](/docs/langgraph/12-runtime-context)
- [서브그래프 스트리밍](/docs/langgraph/14-subgraphs)
- [채팅 모델 stream/astream](/docs/langchain/02-chat-model-methods)
