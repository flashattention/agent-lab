---
title: "MessagesState"
description: "add_messages 리듀서가 붙은 messages 키 하나를 가진 미리 정의된 상태 스키마"
order: 3
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#messagesstate"
tags: [state, messages, chat]
---

`MessagesState`는 채팅형 그래프를 위한 미리 정의된 `TypedDict`입니다. 정의는 다음 한 줄이 전부입니다.

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

키를 더 추가하려면 상속해서 확장합니다.

## Import

```python
from langgraph.graph import MessagesState
```

## 시그니처

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `messages` | `list[AnyMessage]` | (필수 키) | 대화 메시지 목록. 업데이트는 [`add_messages`](/docs/langgraph/02-state-reducers)로 병합(ID 기준 추가/교체/삭제) |

## 메서드와 반환값

`TypedDict`이므로 메서드는 없습니다. 노드는 `{"messages": [새 메시지]}` 또는 `{"messages": 단일메시지}`를 반환하면 됩니다. 입력에는 메시지 객체 외에 `("user", "텍스트")` 튜플이나 `{"role": "user", "content": "..."}` dict도 쓸 수 있으며 자동으로 `HumanMessage` 등으로 변환됩니다.

> [!NOTE]
> `create_agent`가 쓰는 상태는 `langchain.agents.AgentState`입니다. 이 역시 `messages` 키(+ `jump_to`, `structured_response` 등)를 갖습니다. 에이전트 커스텀 상태는 `AgentState`를 상속하세요.

## 예제

### 최소 챗봇

```python
import os

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END, MessagesState

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def chatbot(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


graph = (
    StateGraph(MessagesState)
    .add_node("chatbot", chatbot)
    .add_edge(START, "chatbot")
    .add_edge("chatbot", END)
    .compile()
)

result = graph.invoke({"messages": [("user", "LangGraph를 한 문장으로 설명해줘")]})
result["messages"][-1].pretty_print()
```

### 키 확장

```python
from langgraph.graph import MessagesState


class State(MessagesState):
    summary: str        # 리듀서 없음: 덮어쓰기
    turn_count: int
```

## 주의사항

> [!WARNING]
> `{"messages": state["messages"] + [new]}`처럼 전체 리스트를 반환하지 마세요. `add_messages`는 ID가 같은 메시지를 교체하므로 결과적으로 동작은 하지만, 불필요한 비교 비용이 들고 의도가 흐려집니다. **새 메시지만** 반환하세요.

> [!TIP]
> 메시지를 지우려면 빈 리스트를 반환하는 것이 아니라 `RemoveMessage(id=...)`를 반환해야 합니다. 리듀서가 붙어 있으므로 `[]`는 "변경 없음"입니다.

## 관련 문서

- [상태와 리듀서](/docs/langgraph/02-state-reducers)
- [메시지와 content_blocks](/docs/langchain/03-messages)
- [prebuilt (ToolNode, tools_condition)](/docs/langgraph/17-prebuilt)
- [create_agent](/docs/langchain/06-create-agent)
