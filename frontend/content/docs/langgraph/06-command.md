---
title: "Command"
description: "노드에서 상태 업데이트와 다음 노드 이동(goto)을 함께 지정하고, interrupt를 재개하는 제어 객체"
order: 6
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#command"
tags: [command, routing, goto, resume, handoff]
---

`Command`는 그래프 흐름을 제어하는 객체입니다. 세 가지 용도로 쓰입니다.

1. **노드 반환값**: `update`(상태 업데이트)와 `goto`(다음 노드)를 한 번에 지정. 조건부 엣지 없이 동적 라우팅.
2. **부모 그래프로 이동**: 서브그래프 노드에서 `graph=Command.PARENT`로 부모 그래프의 노드로 핸드오프(handoff).
3. **그래프 입력**: `graph.invoke(Command(resume=...))`로 [`interrupt`](/docs/langgraph/08-interrupt)를 재개.

도구(tool)에서도 `Command`를 반환해 에이전트 상태를 갱신할 수 있습니다([ToolRuntime](/docs/langchain/05-tool-runtime)).

## Import

```python
from langgraph.types import Command
```

## 시그니처

```python
@dataclass
class Command(Generic[N]):
    graph: str | None = None
    update: Any | None = None
    resume: dict[str, Any] | Any | None = None
    goto: Send | Sequence[Send | N] | N = ()

    PARENT: ClassVar[Literal["__parent__"]] = "__parent__"
```

모든 필드는 키워드 전용(keyword-only)입니다.

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `graph` | `str \| None` | `None` | 명령을 보낼 그래프. `None`=현재 그래프, `Command.PARENT`=가장 가까운 부모 그래프 |
| `update` | `Any \| None` | `None` | 상태 업데이트(dict 등). 리듀서가 적용됨 |
| `resume` | `Any \| None` | `None` | interrupt 재개 값. 단일 값이면 다음 interrupt에, `{interrupt_id: 값}` dict이면 ID별로 매핑 |
| `goto` | `str \| Send \| Sequence[str \| Send]` | `()` | 다음에 실행할 노드 이름(들) 또는 `Send`. `END` 가능 |

## 메서드와 반환값

노드에서 `Command`를 반환할 때는 반환 타입 힌트로 목적지를 선언하면 그래프 시각화에 엣지가 그려집니다.

```python
def node(state) -> Command[Literal["a", "b"]]: ...
```

또는 `add_node(..., destinations=("a", "b"))`로 선언합니다.

## 예제

### update + goto

```python
import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import StateGraph, START
from langgraph.types import Command


class State(TypedDict):
    amount: int
    trail: Annotated[list[str], operator.add]


def triage(state: State) -> Command[Literal["auto_approve", "manual_review"]]:
    target = "auto_approve" if state["amount"] < 100 else "manual_review"
    return Command(update={"trail": [f"triage->{target}"]}, goto=target)


builder = StateGraph(State)
builder.add_node("triage", triage)
builder.add_node("auto_approve", lambda s: {"trail": ["approved"]})
builder.add_node("manual_review", lambda s: {"trail": ["queued"]})
builder.add_edge(START, "triage")  # triage 이후 엣지는 Command가 결정
graph = builder.compile()

print(graph.invoke({"amount": 50, "trail": []}))
# {'amount': 50, 'trail': ['triage->auto_approve', 'approved']}
```

### 서브그래프에서 부모로 핸드오프

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START
from langgraph.types import Command


class State(TypedDict):
    trail: Annotated[list[str], operator.add]


def escalate(state: State) -> Command:
    # 부모 그래프의 "human" 노드로 이동. update 키는 부모 상태에 존재해야 한다
    return Command(graph=Command.PARENT, goto="human", update={"trail": ["escalated"]})


sub = StateGraph(State).add_node("escalate", escalate).add_edge(START, "escalate").compile()

parent = StateGraph(State)
parent.add_node("support", sub)
parent.add_node("human", lambda s: {"trail": ["human"]})
parent.add_edge(START, "support")
print(parent.compile().invoke({"trail": []}))
# {'trail': ['escalated', 'human']}
```

## 주의사항

> [!WARNING]
> `Command(goto=...)`를 반환하는 노드에 **고정 엣지도** 걸려 있으면 두 경로가 모두 실행됩니다. Command로 라우팅하는 노드에는 나가는 엣지를 두지 마세요.

> [!WARNING]
> `Command.PARENT`로 보낸 `update`는 부모 그래프 상태에 적용됩니다. 부모와 서브그래프가 같은 키를 공유하고 그 키에 리듀서가 없으면 충돌할 수 있으니, 공유 키에는 리듀서를 두세요. 또한 서브그래프가 `Command.PARENT`로 빠져나가면 그 서브그래프의 일반 상태 업데이트는 부모에 반영되지 않고 Command의 `update`만 반영됩니다.

> [!TIP]
> `Command(resume=...)`는 노드 반환값이 아니라 **그래프 입력**입니다. 노드에서 resume을 반환해도 interrupt가 재개되지 않습니다.

## 관련 문서

- [interrupt와 HITL](/docs/langgraph/08-interrupt)
- [Send](/docs/langgraph/07-send)
- [서브그래프](/docs/langgraph/14-subgraphs)
- [ToolRuntime과 InjectedToolCallId](/docs/langchain/05-tool-runtime)
- [langgraph-swarm](/docs/integrations/08-swarm): Command 기반 핸드오프
