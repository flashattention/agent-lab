---
title: "상태와 리듀서 (State & Reducers)"
description: "Annotated 리듀서, add_messages, operator.add, Overwrite로 상태 병합 방식을 제어"
order: 2
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#reducers"
tags: [state, reducer, add-messages, overwrite]
---

상태 스키마의 각 키는 **채널(Channel)** 입니다. 노드가 반환한 업데이트는 키별 **리듀서(Reducer)** 로 기존 값과 합쳐집니다.

- 리듀서 없음: 마지막 값으로 덮어쓰기(LastValue). 한 슈퍼스텝(super-step)에서 두 노드가 같은 키를 쓰면 `InvalidUpdateError`.
- 리듀서 있음: `reducer(기존값, 새값)`의 결과로 교체. 병렬 노드가 같은 키를 써도 안전합니다.

리듀서는 `Annotated[타입, 리듀서함수]`로 지정합니다.

## Import

```python
from typing import Annotated
import operator

from langgraph.graph import add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Overwrite
from langchain.messages import RemoveMessage
```

## 시그니처

```python
def add_messages(
    left: Messages,
    right: Messages,
    *,
    format: Literal["langchain-openai"] | None = None,
) -> Messages: ...

class Overwrite:
    value: Any
    type: Literal["__overwrite__"] = "__overwrite__"

REMOVE_ALL_MESSAGES = "__remove_all__"
```

## 파라미터

### add_messages

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `left` | `Messages` | (필수) | 기존 메시지 리스트 |
| `right` | `Messages` | (필수) | 병합할 메시지(단일 메시지 또는 리스트). 튜플 `("user", "...")`, dict, 문자열도 메시지로 변환 |
| `format` | `"langchain-openai" \| None` | `None` | `"langchain-openai"`면 콘텐츠를 OpenAI 형식 블록으로 정규화. `Annotated[list, add_messages(format="langchain-openai")]`처럼 부분 적용으로 사용 |

### Overwrite

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `value` | `Any` | (필수) | 리듀서를 우회하고 채널에 그대로 쓸 값 |

## 메서드와 반환값

`add_messages` 병합 규칙:

| 입력 | 동작 |
|---|---|
| ID가 없는 새 메시지 | UUID를 부여해 뒤에 추가(append) |
| 기존 메시지와 같은 `id` | 해당 위치의 메시지를 **교체** |
| `RemoveMessage(id="...")` | 해당 ID 메시지 삭제 |
| `RemoveMessage(id=REMOVE_ALL_MESSAGES)` | 그 앞까지의 모든 메시지 삭제 후, 뒤에 오는 메시지만 남김 |

자주 쓰는 리듀서:

| 리듀서 | 용도 |
|---|---|
| `operator.add` | 리스트 이어 붙이기, 숫자 합산 |
| `add_messages` | 메시지 리스트(ID 기반 upsert/삭제) |
| 사용자 정의 `def f(a, b) -> c` | 딕셔너리 병합, 중복 제거, 최대값 유지 등 |

## 예제

### operator.add와 사용자 정의 리듀서

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START


def merge_dict(left: dict, right: dict) -> dict:
    """얕은 병합 리듀서. 오른쪽 값이 우선한다."""
    return {**(left or {}), **(right or {})}


class State(TypedDict):
    logs: Annotated[list[str], operator.add]
    total: Annotated[int, operator.add]
    meta: Annotated[dict, merge_dict]


def a(state: State) -> dict:
    return {"logs": ["a"], "total": 1, "meta": {"a": True}}


def b(state: State) -> dict:
    return {"logs": ["b"], "total": 10, "meta": {"b": True}}


builder = StateGraph(State)
builder.add_node("a", a)
builder.add_node("b", b)
builder.add_edge(START, "a")  # a와 b는 같은 슈퍼스텝에서 병렬 실행
builder.add_edge(START, "b")
graph = builder.compile()

print(graph.invoke({"logs": [], "total": 0, "meta": {}}))
# {'logs': ['a', 'b'], 'total': 11, 'meta': {'a': True, 'b': True}}
```

### Overwrite와 메시지 삭제

```python
import operator
from typing import Annotated, TypedDict

from langchain.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph import StateGraph, START, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Overwrite


class State(TypedDict):
    items: Annotated[list[str], operator.add]


def reset(state: State) -> dict:
    # 리듀서(operator.add)를 우회해 값을 통째로 교체
    return {"items": Overwrite(["reset"])}


builder = StateGraph(State)
builder.add_node("reset", reset)
builder.add_edge(START, "reset")
print(builder.compile().invoke({"items": ["a", "b"]}))  # {'items': ['reset']}

# add_messages는 순수 함수로도 호출할 수 있다
history = [HumanMessage("안녕", id="1"), AIMessage("반가워요", id="2")]
print(add_messages(history, [RemoveMessage(id="1")]))  # id=2만 남음
print(add_messages(history, [RemoveMessage(id=REMOVE_ALL_MESSAGES), HumanMessage("새 대화")]))
```

## 주의사항

> [!WARNING]
> 리듀서가 없는 키를 병렬 노드 두 개가 동시에 쓰면 `InvalidUpdateError: At key '...': Can receive only one value per step`가 납니다. 병렬로 쓰는 키에는 반드시 리듀서를 지정하세요.

> [!WARNING]
> 한 슈퍼스텝에서 같은 키에 `Overwrite`가 두 번 이상 오면 `InvalidUpdateError`가 발생합니다.

> [!TIP]
> 리듀서는 `invoke`에 넘긴 **초기 입력에도** 적용됩니다. `operator.add` 키에 초기값을 넣고 다시 같은 스레드로 호출하면 값이 누적되니 주의하세요.

## 관련 문서

- [StateGraph](/docs/langgraph/01-state-graph)
- [MessagesState](/docs/langgraph/03-messages-state)
- [Send](/docs/langgraph/07-send): 맵-리듀스 결과 수집에 리듀서 필수
- [오류](/docs/langgraph/18-errors): `InvalidUpdateError`
- [메시지](/docs/langchain/03-messages)
