---
title: "프롬프트 템플릿"
description: "ChatPromptTemplate, PromptTemplate, MessagesPlaceholder로 변수 기반 프롬프트 만들기"
order: 10
source: "https://reference.langchain.com/python/langchain_core/prompts/"
tags: [prompts, chatprompttemplate, template, messagesplaceholder]
---

프롬프트 템플릿(Prompt Template)은 변수를 채워 메시지 리스트(또는 문자열)를 만드는 Runnable입니다. `prompt | llm`처럼 LCEL로 모델과 연결합니다. 에이전트(`create_agent`)에서는 보통 `system_prompt` 문자열이나 `dynamic_prompt` 미들웨어를 쓰므로, 템플릿은 주로 단일 모델 호출 체인·RAG 프롬프트·요약 프롬프트에 씁니다.

## Import

```python
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, MessagesPlaceholder
```

## 시그니처

```python
ChatPromptTemplate.from_messages(
    messages: Sequence[MessageLikeRepresentation],
    template_format: Literal["f-string", "mustache", "jinja2"] = "f-string",
) -> ChatPromptTemplate

ChatPromptTemplate(messages: Sequence[MessageLikeRepresentation], *,
                   template_format: PromptTemplateFormat = "f-string", ...)

PromptTemplate.from_template(template: str, *, template_format: PromptTemplateFormat = "f-string",
                             partial_variables: dict[str, Any] | None = None, **kwargs) -> PromptTemplate

MessagesPlaceholder(variable_name: str, *, optional: bool = False, n_messages: int | None = None)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `messages` | `Sequence[MessageLikeRepresentation]` | 필수 | `("system", "…{var}…")` 튜플, 메시지 객체, `MessagesPlaceholder`, 템플릿 객체의 리스트. 역할: `system`, `human`/`user`, `ai`/`assistant`, `placeholder`. |
| `template_format` | `"f-string" \| "mustache" \| "jinja2"` | `"f-string"` | 변수 문법. f-string은 `{var}`, mustache는 `{{var}}`. |
| `partial_variables` | `dict \| None` | `None` | 미리 채워 둘 변수(값 또는 무인자 함수). |
| `variable_name` | `str` | 필수 | (MessagesPlaceholder) 메시지 리스트를 받을 변수 이름. |
| `optional` | `bool` | `False` | (MessagesPlaceholder) 값이 없어도 오류 없이 빈 리스트로 처리. |
| `n_messages` | `int \| None` | `None` | (MessagesPlaceholder) 마지막 N개 메시지만 사용. |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `invoke(dict)` | `ChatPromptValue` / `StringPromptValue` | 모델에 바로 넘길 수 있는 값. `.to_messages()`, `.to_string()`. |
| `format_messages(**kwargs)` | `list[BaseMessage]` | 메시지 리스트로 직접 포맷. |
| `format(**kwargs)` | `str` | 문자열로 포맷. |
| `partial(**kwargs)` | 템플릿 | 일부 변수를 채운 새 템플릿. |
| `.input_variables` / `.optional_variables` | `list[str]` | 필수/선택 변수 이름. |
| `pretty_print()` | | 템플릿 구조 출력. |

## 예제

```python
import os
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 {domain} 전문가다. {style}로 답하라."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
]).partial(style="세 문장 이내")

print(prompt.input_variables, prompt.optional_variables)  # ['domain', 'question'] ['history']

chain = prompt | init_chat_model(MODEL)
reply = chain.invoke({
    "domain": "벡터 데이터베이스",
    "history": [("human", "HNSW가 뭐야?"), ("ai", "그래프 기반 근사 최근접 탐색 인덱스입니다.")],
    "question": "IVF와 차이는?",
})
print(reply.text)
```

RAG 프롬프트(문자열 템플릿):

```python
from langchain_core.prompts import PromptTemplate

rag = PromptTemplate.from_template(
    "다음 문맥만 사용해 답하라.\n\n문맥:\n{context}\n\n질문: {question}"
)
print(rag.format(context="- LangGraph는 상태 그래프 프레임워크다.", question="LangGraph란?"))
```

## 주의사항

> [!WARNING]
> f-string 템플릿에서 JSON 예시처럼 중괄호를 그대로 쓰려면 `{{`와 `}}`로 이스케이프해야 합니다. 그렇지 않으면 변수로 인식되어 `KeyError`가 납니다.

> [!WARNING]
> `jinja2` 형식은 신뢰할 수 없는 템플릿 문자열에 쓰지 마세요. 사용자 입력은 템플릿이 아니라 **변수 값**으로만 넣어야 합니다.

> [!TIP]
> `("placeholder", "{history}")` 튜플은 `MessagesPlaceholder("history", optional=True)`의 축약형입니다.

## 관련 문서

- [Runnable과 LCEL](/docs/langchain/11-runnables-lcel)
- [메시지](/docs/langchain/03-messages)
- [커스텀 미들웨어 (dynamic_prompt)](/docs/langchain/08-custom-middleware)
- [Retriever](/docs/langchain/15-retrievers)
