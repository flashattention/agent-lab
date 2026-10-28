---
title: "구조화 출력 전략"
description: "create_agent의 response_format: ToolStrategy, ProviderStrategy, AutoStrategy와 오류 처리"
order: 9
source: "https://docs.langchain.com/oss/python/langchain/structured-output"
tags: [structured-output, response-format, toolstrategy, providerstrategy, pydantic]
---

`create_agent(response_format=...)`는 에이전트의 최종 답을 스키마에 맞춘 객체로 돌려줍니다. 결과는 `result["structured_response"]`에 들어갑니다. 두 가지 전략이 있습니다.

- **ProviderStrategy**: 제공자 네이티브 구조화 출력(OpenAI `response_format` JSON Schema)을 사용. 가장 안정적이지만 지원 모델에서만 동작합니다.
- **ToolStrategy**: 스키마를 "가짜 도구"로 바인딩하고 모델이 그 도구를 호출하게 합니다. 도구 호출을 지원하는 모든 모델에서 동작하고, 검증 실패 시 자동 재시도합니다.

스키마 타입만 넘기면(`response_format=MySchema`) 내부적으로 `AutoStrategy`가 되어 모델이 네이티브를 지원하면 ProviderStrategy, 아니면 ToolStrategy를 고릅니다.

## Import

```python
from langchain.agents.structured_output import (
    ToolStrategy, ProviderStrategy, AutoStrategy,
    StructuredOutputError, StructuredOutputValidationError, MultipleStructuredOutputsError,
)
```

## 시그니처

```python
class ToolStrategy(Generic[SchemaT]):
    def __init__(
        self,
        schema: type[SchemaT] | UnionType | dict[str, Any],
        *,
        tool_message_content: str | None = None,
        handle_errors: bool | str | type[Exception] | tuple[type[Exception], ...]
                       | Callable[[Exception], str] = True,
    ) -> None

class ProviderStrategy(Generic[SchemaT]):
    def __init__(self, schema: type[SchemaT] | dict[str, Any], *, strict: bool | None = None) -> None

class AutoStrategy(Generic[SchemaT]):
    def __init__(self, schema: type[SchemaT] | dict[str, Any]) -> None
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `schema` | Pydantic 모델 \| dataclass \| TypedDict \| JSON Schema dict \| `A \| B` 유니온 | 필수 | 출력 스키마. ToolStrategy는 유니온(`Union[A, B]`)을 받아 스키마별 도구를 하나씩 만듭니다. |
| `tool_message_content` | `str \| None` | `None` | (ToolStrategy) 구조화 출력 도구 호출 뒤 대화에 추가되는 `ToolMessage` 내용. 기본은 자동 생성 문구. |
| `handle_errors` | `bool \| str \| type \| tuple \| Callable` | `True` | (ToolStrategy) 파싱·검증 실패 처리. `True`: 기본 오류 메시지로 모델에 재시도 요청. `str`: 그 메시지로 재시도. 예외 타입/튜플: 해당 예외만 처리. 함수: 예외 → 메시지. `False`: 예외 전파. |
| `strict` | `bool \| None` | `None` | (ProviderStrategy) 제공자 측 엄격 스키마 검증 요청. |

## 메서드와 반환값

| 스키마 종류 | `structured_response` 타입 |
|---|---|
| Pydantic 모델 | 모델 인스턴스 |
| dataclass | dataclass 인스턴스 |
| TypedDict / JSON Schema dict | `dict` |

예외(`langchain.agents.structured_output`):

| 예외 | 발생 조건 |
|---|---|
| `StructuredOutputError` | 기본 클래스. `.ai_message` 속성 보유. |
| `StructuredOutputValidationError` | 인자/JSON이 스키마 검증에 실패. `.tool_name`, `.source`. |
| `MultipleStructuredOutputsError` | 모델이 구조화 출력 도구를 여러 개 동시에 호출. `.tool_names`. |

ToolStrategy에서 `handle_errors`가 처리하는 경우 이 예외들은 밖으로 나오지 않고 모델에게 오류 `ToolMessage`로 전달되어 다시 시도합니다.

## 예제

```python
import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


class Ticket(BaseModel):
    """고객 문의 분류 결과."""
    category: Literal["billing", "bug", "other"] = Field(description="문의 유형")
    priority: int = Field(ge=1, le=5, description="1(낮음)~5(높음)")
    summary: str


agent = create_agent(
    MODEL,
    tools=[],
    response_format=ToolStrategy(Ticket, handle_errors="스키마에 맞게 다시 작성하세요."),
)
result = agent.invoke({"messages": [{"role": "user", "content": "결제가 두 번 됐어요. billing 문의입니다."}]})
ticket: Ticket = result["structured_response"]
print(ticket.category, ticket.priority, ticket.summary)
```

네이티브 구조화 출력(실제 OpenAI 모델):

```python
# 위 예제의 MODEL, Ticket을 그대로 사용
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy

agent = create_agent(MODEL, tools=[], response_format=ProviderStrategy(Ticket, strict=True))
```

## 주의사항

> [!WARNING]
> ToolStrategy에 **JSON Schema dict**를 넘기면 인자를 검증하지 않고 그대로 돌려줍니다. 따라서 `handle_errors` 재시도도 사실상 동작하지 않습니다. 검증이 필요하면 Pydantic/dataclass/TypedDict를 쓰세요.

> [!WARNING]
> 일부 모델은 도구 호출과 네이티브 구조화 출력을 동시에 지원하지 않습니다. `AutoStrategy`는 이를 고려해 전략을 고르지만, `ProviderStrategy`를 직접 지정하면 그 판단을 건너뜁니다.

> [!TIP]
> 에이전트 없이 모델 한 번만 호출한다면 `llm.with_structured_output(Schema)`가 더 간단합니다. [채팅 모델 메서드](/docs/langchain/02-chat-model-methods) 참고.

## 관련 문서

- [create_agent](/docs/langchain/06-create-agent)
- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [ChatOpenAI](/docs/integrations/01-openai-chat)
