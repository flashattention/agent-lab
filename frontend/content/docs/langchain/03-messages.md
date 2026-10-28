---
title: "메시지와 content_blocks"
description: "HumanMessage/AIMessage/SystemMessage/ToolMessage, 표준 콘텐츠 블록, 메시지 유틸리티"
order: 3
source: "https://docs.langchain.com/oss/python/langchain/messages"
tags: [messages, content-blocks, multimodal, trim]
---

메시지(Message)는 채팅 모델의 입력과 출력 단위입니다. v1에서는 제공자마다 다른 `content` 형식을 표준화한 **콘텐츠 블록(content_blocks)** 뷰가 추가되었습니다. `content`는 원본(제공자 형식) 그대로, `content_blocks`는 표준 타입(`text`, `reasoning`, `image`, `tool_call` …)의 리스트입니다.

## Import

```python
from langchain.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, RemoveMessage,
    AIMessageChunk, AnyMessage, ToolCall, UsageMetadata, trim_messages,
)
# 그 밖의 유틸리티
from langchain_core.messages import filter_messages, convert_to_messages, merge_message_runs
from langchain_core.messages.utils import count_tokens_approximately
```

## 시그니처

```python
HumanMessage(content: str | list[str | dict] | None = None,
             content_blocks: list[ContentBlock] | None = None,
             *, name: str | None = None, id: str | None = None,
             additional_kwargs: dict = {}, response_metadata: dict = {})

SystemMessage(content=None, content_blocks=None, *, name=None, id=None, ...)

AIMessage(content=None, content_blocks=None, *, name=None, id=None,
          tool_calls: list[ToolCall] = [], invalid_tool_calls: list[InvalidToolCall] = [],
          usage_metadata: UsageMetadata | None = None, ...)

ToolMessage(content=None, content_blocks=None, *, tool_call_id: str,
            artifact: Any = None, status: Literal["success", "error"] = "success",
            name: str | None = None, id: str | None = None, ...)

RemoveMessage(id: str)  # add_messages 리듀서에 삭제를 지시
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `content` | `str \| list[str \| dict]` | `None` | 원본 콘텐츠. 문자열 또는 블록 리스트. |
| `content_blocks` | `list[ContentBlock]` | `None` | 표준 블록으로 생성할 때 사용. 지정하면 `content`에 그대로 저장됩니다. |
| `name` | `str \| None` | `None` | 화자 이름(멀티 에이전트에서 구분용). 제공자에 따라 무시될 수 있습니다. |
| `id` | `str \| None` | `None` | 메시지 ID. `add_messages`는 같은 ID를 **교체**, `RemoveMessage(id)`는 **삭제**합니다. |
| `tool_calls` (AI) | `list[ToolCall]` | `[]` | `{"name", "args", "id", "type": "tool_call"}` dict 리스트. |
| `usage_metadata` (AI) | `UsageMetadata \| None` | `None` | `input_tokens`, `output_tokens`, `total_tokens`, `input_token_details`, `output_token_details`. |
| `tool_call_id` (Tool) | `str` | 필수 | 응답하는 `AIMessage.tool_calls[i]["id"]`. |
| `artifact` (Tool) | `Any` | `None` | 모델에는 보내지 않고 코드에서만 쓰는 부가 데이터. |
| `status` (Tool) | `"success" \| "error"` | `"success"` | 도구 실패 표시. |

## 메서드와 반환값

| 속성/메서드 | 설명 |
|---|---|
| `.text` | 텍스트 블록만 이어 붙인 문자열(프로퍼티). |
| `.content_blocks` | 표준 콘텐츠 블록 리스트. AIMessage는 `tool_calls`도 `{"type": "tool_call"}` 블록으로 포함합니다. |
| `.pretty_print()` | 콘솔용 보기 좋은 출력. |
| `AIMessageChunk + AIMessageChunk` | 스트리밍 청크 병합. |

표준 콘텐츠 블록 타입(`langchain.messages`에서 import 가능):

| 타입 | `type` 값 | 주요 키 |
|---|---|---|
| `TextContentBlock` | `"text"` | `text`, `annotations`(Citation) |
| `ReasoningContentBlock` | `"reasoning"` | `reasoning` |
| `ImageContentBlock` | `"image"` | `url` \| `base64` \| `file_id`, `mime_type` |
| `AudioContentBlock` / `VideoContentBlock` / `FileContentBlock` | `"audio"` / `"video"` / `"file"` | 이미지와 동일 |
| `PlainTextContentBlock` | `"text-plain"` | `text`, `mime_type` |
| `ToolCall` / `ToolCallChunk` / `InvalidToolCall` | `"tool_call"` … | `name`, `args`, `id` |
| `ServerToolCall` / `ServerToolResult` | `"server_tool_call"` / `"server_tool_result"` | 제공자 내장 도구(웹 검색 등) |
| `NonStandardContentBlock` | `"non_standard"` | `value` (제공자 고유 데이터) |

유틸리티:

| 함수 | 시그니처 요약 |
|---|---|
| `trim_messages` | `(messages, *, max_tokens, token_counter, strategy="last", allow_partial=False, end_on=None, start_on=None, include_system=False, text_splitter=None)` |
| `filter_messages` | `(messages, *, include_names, exclude_names, include_types, exclude_types, include_ids, exclude_ids, exclude_tool_calls)` |
| `count_tokens_approximately` | `(messages, *, chars_per_token=4.0, extra_tokens_per_message=3.0, count_name=True, tokens_per_image=85, use_usage_metadata_scaling=False, tools=None)` |
| `convert_to_messages` | dict/튜플/문자열을 메시지 객체로 변환 |

## 예제

```python
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

msgs = [
    SystemMessage("너는 간결한 비서다."),
    HumanMessage(content_blocks=[
        {"type": "text", "text": "이 이미지를 설명해 줘"},
        {"type": "image", "url": "https://example.com/cat.png"},
    ]),
    AIMessage(content="", tool_calls=[{"name": "search", "args": {"q": "cat"}, "id": "call_1"}]),
    ToolMessage("고양이 사진", tool_call_id="call_1"),
]
for m in msgs:
    print(type(m).__name__, m.content_blocks)
```

토큰 기준으로 최근 대화만 남기기:

```python
from langchain.messages import AIMessage, HumanMessage, SystemMessage, trim_messages

history = [SystemMessage("규칙")] + [
    HumanMessage(f"질문 {i}") if i % 2 == 0 else AIMessage(f"답변 {i}") for i in range(20)
]
trimmed = trim_messages(
    history,
    max_tokens=60,
    token_counter="approximate",  # count_tokens_approximately 사용
    strategy="last",
    start_on="human",             # 잘린 결과가 HumanMessage로 시작하도록
    include_system=True,
)
print(len(history), "→", len(trimmed))
```

## 주의사항

> [!WARNING]
> `ToolMessage` 없이 `tool_calls`가 있는 `AIMessage`만 남기면 OpenAI가 400 오류를 냅니다. 대화를 자를 때는 `start_on="human"` 등으로 AI–Tool 쌍이 깨지지 않게 하세요.

> [!WARNING]
> `content`(제공자 원본)와 `content_blocks`(표준)는 다를 수 있습니다. 제공자 독립 코드는 `content_blocks`나 `.text`를 읽으세요.

> [!TIP]
> 그래프 상태에서 메시지를 지우려면 `RemoveMessage(id=m.id)`를 `add_messages` 채널에 반환합니다. 전부 지우려면 `RemoveMessage(id=REMOVE_ALL_MESSAGES)`(`langgraph.graph.message`)를 씁니다.

## 관련 문서

- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [도구](/docs/langchain/04-tools)
- [State와 리듀서](/docs/langgraph/02-state-reducers)
- [MessagesState](/docs/langgraph/03-messages-state)
