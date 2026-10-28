---
title: "채팅 모델 메서드"
description: "BaseChatModel의 invoke/stream/batch, bind_tools, with_structured_output, with_retry, with_fallbacks"
order: 2
source: "https://docs.langchain.com/oss/python/langchain/models"
tags: [chat-model, invoke, stream, batch, tools, structured-output, retry]
---

모든 채팅 모델(`BaseChatModel` 하위 클래스)은 Runnable 인터페이스를 따릅니다. 입력은 문자열, 메시지 리스트, `PromptValue` 중 하나(`LanguageModelInput`)이고 출력은 `AIMessage`입니다. 각 메서드에는 비동기 버전(`ainvoke`, `astream`, `abatch`, `abatch_as_completed`)이 있습니다.

## Import

```python
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel  # 타입 힌트용
```

## 시그니처

```python
# langchain-core 1.7.0, BaseChatModel
def invoke(self, input: LanguageModelInput, config: RunnableConfig | None = None,
           *, stop: list[str] | None = None, **kwargs) -> AIMessage
def stream(self, input: LanguageModelInput, config: RunnableConfig | None = None,
           *, stop: list[str] | None = None, **kwargs) -> Iterator[AIMessageChunk]
def batch(self, inputs: list[Input], config: RunnableConfig | list[RunnableConfig] | None = None,
          *, return_exceptions: bool = False, **kwargs) -> list[Output]
def batch_as_completed(self, inputs: Sequence[Input], config=None,
                       *, return_exceptions: bool = False, **kwargs) -> Iterator[tuple[int, Output | Exception]]
def bind_tools(self, tools: Sequence[dict | type | Callable | BaseTool],
               *, tool_choice: str | None = None, **kwargs) -> Runnable[LanguageModelInput, AIMessage]
def with_structured_output(self, schema: dict | type,
                           *, include_raw: bool = False, **kwargs) -> Runnable[LanguageModelInput, dict | BaseModel]
def with_retry(self, *, retry_if_exception_type: tuple[type[BaseException], ...] | Callable[[BaseException], bool] = (Exception,),
               wait_exponential_jitter: bool = True,
               exponential_jitter_params: ExponentialJitterParams | None = None,
               stop_after_attempt: int = 3) -> Runnable
def with_fallbacks(self, fallbacks: Sequence[Runnable], *,
                   exceptions_to_handle: tuple[type[BaseException], ...] = (Exception,),
                   exception_key: str | None = None) -> RunnableWithFallbacks
```

## 파라미터

### invoke / stream / batch

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `input` | `str \| list[메시지 또는 dict] \| PromptValue` | | 문자열은 `HumanMessage` 하나로 변환됩니다. `{"role": "user", "content": "..."}` dict도 됩니다. |
| `config` | `RunnableConfig \| None` | `None` | `tags`, `metadata`, `callbacks`, `run_name`, `max_concurrency`(batch), `configurable` 등. |
| `stop` | `list[str] \| None` | `None` | 정지 시퀀스(stop sequence). |
| `return_exceptions` | `bool` | `False` | batch에서 실패한 항목을 예외 객체로 돌려주고 나머지는 계속 실행합니다. |
| `**kwargs` | | | 이번 호출에만 적용할 제공자 인자. |

### bind_tools

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `tools` | `Sequence[dict \| type \| Callable \| BaseTool]` | | `@tool` 함수, Pydantic 클래스, 일반 함수, OpenAI 형식 dict. |
| `tool_choice` | `str \| None` | `None` | `"auto"`, `"any"`/`"required"`(반드시 도구 호출), 특정 도구 이름. `ChatOpenAI`는 `dict \| str \| bool`도 받습니다. |
| `strict` (ChatOpenAI) | `bool \| None` | `None` | OpenAI strict 스키마 모드. |
| `parallel_tool_calls` (ChatOpenAI) | `bool \| None` | `None` | 병렬 도구 호출 허용 여부. |

### with_structured_output

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `schema` | `type[BaseModel] \| TypedDict \| dict` | | 출력 스키마. Pydantic이면 인스턴스, TypedDict/JSON Schema면 dict를 돌려줍니다. |
| `include_raw` | `bool` | `False` | `True`면 `{"raw": AIMessage, "parsed": ..., "parsing_error": ...}` 반환. |
| `method` (ChatOpenAI) | `"json_schema" \| "function_calling" \| "json_mode"` | `"json_schema"` | 제공자 네이티브 구조화 출력 방식. |
| `strict` (ChatOpenAI) | `bool \| None` | `None` | 스키마 엄격 검증. |

### with_retry / with_fallbacks

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `retry_if_exception_type` | `tuple[type] \| Callable` | `(Exception,)` | 재시도할 예외 종류 또는 판별 함수. |
| `wait_exponential_jitter` | `bool` | `True` | 지수 백오프 + 지터(jitter). |
| `exponential_jitter_params` | `ExponentialJitterParams \| None` | `None` | `initial`, `max`, `exp_base`, `jitter` 값. |
| `stop_after_attempt` | `int` | `3` | 최초 시도를 포함한 최대 시도 횟수. |
| `fallbacks` | `Sequence[Runnable]` | | 순서대로 시도할 대체 Runnable. |
| `exceptions_to_handle` | `tuple[type]` | `(Exception,)` | 이 예외가 나면 다음 fallback으로 넘어갑니다. |
| `exception_key` | `str \| None` | `None` | 지정하면 앞 단계 예외를 입력 dict의 이 키로 전달합니다(입력이 dict여야 함). |

## 메서드와 반환값

| 메서드 | 반환 | 비고 |
|---|---|---|
| `invoke` / `ainvoke` | `AIMessage` | `.text`, `.content_blocks`, `.tool_calls`, `.usage_metadata` |
| `stream` / `astream` | `Iterator[AIMessageChunk]` | 청크끼리 `+`로 합칠 수 있습니다. |
| `batch` / `abatch` | `list[AIMessage]` | 입력 순서 유지. `config={"max_concurrency": N}`로 동시성 제한. |
| `batch_as_completed` | `Iterator[(index, 결과)]` | 끝난 순서대로. |
| `bind_tools` | `Runnable` | 도구 스키마를 묶은 새 Runnable. 원본은 그대로입니다. |
| `with_structured_output` | `Runnable` | 출력이 스키마 객체. |
| `with_retry` / `with_fallbacks` | `Runnable` | 감싼 새 Runnable. `bind_tools` 등은 감싸기 **전에** 호출해야 합니다. |
| `get_num_tokens_from_messages(messages, tools=None)` | `int` | 토큰 수 추정. |
| `stream_events(input, version="v2")` | 이벤트 이터레이터 | `version="v3"`(beta)은 `.text`, `.reasoning`, `.tool_calls`, `.output` 프로젝션을 가진 `ChatModelStream`을 반환합니다. |

## 예제

```python
import os
from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)

# 1) invoke
msg = llm.invoke([{"role": "system", "content": "짧게 답하라"}, {"role": "user", "content": "RAG란?"}])
print(msg.text, msg.usage_metadata)

# 2) stream: 청크를 누적하면 최종 메시지가 된다
full = None
for chunk in llm.stream("LangGraph 장점 3가지"):
    print(chunk.text, end="", flush=True)
    full = chunk if full is None else full + chunk
print()

# 3) batch: 동시성 제한
results = llm.batch(["1+1?", "2+2?", "3+3?"], config={"max_concurrency": 2})
print([r.text for r in results])
```

도구 바인딩과 구조화 출력:

```python
import os
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회한다."""
    return f"{city}: 맑음"


ai = llm.bind_tools([get_weather]).invoke("서울 날씨 알려줘")
for call in ai.tool_calls:
    print(call["name"], call["args"], call["id"])


class Movie(BaseModel):
    title: str = Field(description="영화 제목")
    year: int = Field(description="개봉 연도")


movie = llm.with_structured_output(Movie).invoke("인셉션 정보")
print(movie.title, movie.year)
```

재시도와 대체 모델:

```python
import os
from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
primary = init_chat_model(MODEL, max_retries=0)
backup = init_chat_model("openai:gpt-5-nano")

robust = primary.with_retry(stop_after_attempt=2).with_fallbacks([backup])
print(robust.invoke("안녕").text)
```

## 주의사항

> [!WARNING]
> `with_retry()`/`with_fallbacks()`가 반환한 객체는 채팅 모델이 아니라 일반 Runnable이므로 `bind_tools`가 없습니다. `llm.bind_tools(tools).with_retry()` 순서로 쓰고, fallback 모델에도 각각 `bind_tools`를 해야 합니다.

> [!WARNING]
> `ChatOpenAI`는 자체 `max_retries`(SDK 재시도)를 가집니다. `with_retry`와 겹치면 재시도 횟수가 곱해지니 하나만 쓰세요.

> [!TIP]
> `AIMessage.text`는 v1부터 **프로퍼티**입니다(`msg.text`). `msg.text()`처럼 메서드로 부르는 방식은 langchain-core 1.0부터 deprecated이고 2.0에서 제거될 예정입니다.

> [!TIP]
> 에이전트 안에서 재시도/대체가 필요하면 Runnable 래퍼보다 [ModelRetryMiddleware / ModelFallbackMiddleware](/docs/langchain/07-built-in-middleware)를 쓰는 편이 도구 바인딩과 충돌하지 않습니다.

## 관련 문서

- [init_chat_model](/docs/langchain/01-init-chat-model)
- [메시지와 content_blocks](/docs/langchain/03-messages)
- [도구](/docs/langchain/04-tools)
- [구조화 출력](/docs/langchain/09-structured-output)
- [Runnable과 LCEL](/docs/langchain/11-runnables-lcel)
- [ChatOpenAI](/docs/integrations/01-openai-chat)
