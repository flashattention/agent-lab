---
title: "ChatOpenAI"
description: "langchain-openai의 OpenAI 채팅 모델 클래스: 주요 파라미터, Responses API 자동 전환, 추론(reasoning) 설정"
order: 1
source: "https://docs.langchain.com/oss/python/integrations/chat/openai"
tags: [openai, chat-model, responses-api, reasoning]
---

`ChatOpenAI`는 OpenAI 채팅 모델을 LangChain `BaseChatModel` 인터페이스로 감싼 클래스입니다. `init_chat_model("openai:...")`이 내부에서 생성하는 것도 이 클래스이므로, `init_chat_model`에 넘기는 키워드 인자는 모두 아래 필드로 전달됩니다. Chat Completions API와 Responses API를 모두 지원하며, 조건에 따라 자동으로 Responses API로 전환합니다.

## Import

```python
from langchain_openai import ChatOpenAI          # pip install langchain-openai
from langchain.chat_models import init_chat_model  # 권장 진입점
```

## 시그니처

```python
ChatOpenAI(
    *,
    model: str = "gpt-3.5-turbo",              # alias: model_name
    reasoning_effort: str | None = None,
    reasoning: dict[str, Any] | None = None,
    verbosity: str | None = None,
    max_tokens: int | None = None,             # alias: max_completion_tokens
    timeout: float | tuple[float, float] | Any | None = None,  # 필드명 request_timeout
    max_retries: int | None = None,
    api_key: SecretStr | None | Callable[[], str] | Callable[[], Awaitable[str]] = <env OPENAI_API_KEY>,
    base_url: str | None = <env OPENAI_API_BASE → OPENAI_BASE_URL>,
    organization: str | None = <env OPENAI_ORG_ID>,
    use_responses_api: bool | None = None,
    output_version: str | None = <env LC_OUTPUT_VERSION>,
    use_previous_response_id: bool = False,
    store: bool | None = None,
    include: list[str] | None = None,
    service_tier: str | None = None,
    stream_usage: bool | None = None,
    streaming: bool = False,
    stream_chunk_timeout: float | None = 120.0,  # env LANGCHAIN_OPENAI_STREAM_CHUNK_TIMEOUT_S
    prompt_cache_options: dict[str, Any] | None = None,
    rate_limiter: BaseRateLimiter | None = None,
    model_kwargs: dict[str, Any] = {},
    extra_body: Mapping[str, Any] | None = None,
    temperature: float | None = None,
    # ... top_p, seed, stop, n, logprobs, frequency_penalty, presence_penalty,
    #     default_headers, default_query, http_client, http_async_client 등
)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str` | `"gpt-3.5-turbo"` | 모델 ID. 항상 명시하세요. 이 프로젝트는 `LAB_MODEL` 환경변수에서 읽습니다 |
| `reasoning_effort` | `str \| None` | `None` | 추론 모델의 추론 강도(`"minimal"`, `"low"`, `"medium"`, `"high"` 등, 모델마다 다름) |
| `reasoning` | `dict \| None` | `None` | Responses API용 추론 설정. 예: `{"effort": "low", "summary": "auto"}`. 설정하면 Responses API를 씀 |
| `verbosity` | `str \| None` | `None` | GPT-5 계열 응답 길이 힌트(`"low"`/`"medium"`/`"high"`) |
| `max_tokens` | `int \| None` | `None` | 최대 출력 토큰. `max_completion_tokens`로도 지정 가능 |
| `timeout` | `float \| tuple \| None` | `None` | HTTP 요청 타임아웃(초) |
| `max_retries` | `int \| None` | `None` | 실패 시 openai SDK 재시도 횟수(`None`이면 SDK 기본값) |
| `api_key` | `SecretStr \| Callable` | `OPENAI_API_KEY` | API 키. 동기/비동기 콜러블을 넘기면 요청마다 키를 가져옴 |
| `base_url` | `str \| None` | `OPENAI_API_BASE`, 없으면 `OPENAI_BASE_URL` | 프록시·호환 서버(vLLM, Azure 게이트웨이 등) 주소 |
| `use_responses_api` | `bool \| None` | `None` | `True`/`False`로 강제. `None`이면 자동 판단(아래 참고) |
| `output_version` | `str \| None` | `LC_OUTPUT_VERSION` 또는 `None` | `"v1"`이면 `AIMessage.content`를 표준 콘텐츠 블록으로, `"responses/v1"`이면 Responses 형식 블록으로 채움 |
| `use_previous_response_id` | `bool` | `False` | Responses API에서 직전 응답 ID를 `previous_response_id`로 보내 이전 턴을 재전송하지 않음 |
| `store` | `bool \| None` | `None` | Responses API 응답을 OpenAI에 저장할지 여부. 데이터 보존을 막으려면 `False` |
| `include` | `list[str] \| None` | `None` | 추가로 받을 필드. 예: `["reasoning.encrypted_content"]` |
| `service_tier` | `str \| None` | `None` | `"auto"`, `"default"`, `"flex"`, `"priority"` 등 |
| `stream_usage` | `bool \| None` | `None` | 스트리밍 시 토큰 사용량(`usage_metadata`) 포함 여부 |
| `streaming` | `bool` | `False` | `invoke`도 내부적으로 스트리밍 호출로 처리 |
| `stream_chunk_timeout` | `float \| None` | `120.0` | **비동기** 스트리밍에서 청크 사이 최대 대기(초). `None`/`0`이면 비활성 |
| `prompt_cache_options` | `dict \| None` | `None` | 프롬프트 캐시 모드. 예: `{"mode": "explicit", "ttl": "30m"}` |
| `rate_limiter` | `BaseRateLimiter \| None` | `None` | 요청 속도 제한기. [레이트 리미터](/docs/langchain/17-rate-limiters) 참고 |
| `model_kwargs` | `dict` | `{}` | 명시 필드에 없는 파라미터를 요청 본문 최상위로 전달 |
| `extra_body` | `Mapping \| None` | `None` | 요청 본문에 추가할 값(호환 서버 전용 파라미터 등) |
| `temperature` | `float \| None` | `None` | 샘플링 온도. **GPT-5 계열 추론 모델은 거부하므로 설정하지 않습니다** |

## 메서드와 반환값

`BaseChatModel`의 모든 메서드를 그대로 씁니다. 자세한 내용은 [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)를 참고하세요.

| 메서드 | 반환 | 비고 |
|---|---|---|
| `invoke(input)` / `ainvoke` | `AIMessage` | `usage_metadata`, `response_metadata`(모델명, finish_reason 등) 포함 |
| `stream(input)` / `astream` | `Iterator[AIMessageChunk]` | 청크를 `+`로 합칠 수 있음 |
| `bind_tools(tools, *, tool_choice=None, strict=None, parallel_tool_calls=None, response_format=None)` | `Runnable` | `strict=True`면 OpenAI 구조화 도구 호출 사용 |
| `with_structured_output(schema, *, method="json_schema", include_raw=False, strict=None, tools=None)` | `Runnable` | 기본 method가 `"json_schema"`(OpenAI 네이티브 구조화 출력) |
| `get_num_tokens_from_messages(messages, tools=None)` | `int` | tiktoken 기반 토큰 수 추정 |

**Responses API 자동 전환 규칙**(`use_responses_api=None`일 때): `output_version="responses/v1"`, `reasoning`, `include`, `context_management`, `truncation`, `use_previous_response_id` 중 하나가 설정되었거나, 내장 도구(`{"type": "web_search"}` 같은 비 function 도구)를 바인딩했거나, Responses 전용 모델(`gpt-5-pro`, `*-codex` 등)이면 Responses API를 사용합니다.

## 예제

```python
import os

from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# init_chat_model의 키워드 인자는 ChatOpenAI 필드로 전달된다
llm = init_chat_model(MODEL, timeout=30, max_retries=2)

msg = llm.invoke("LangGraph를 한 문장으로 설명해 줘")
print(msg.content)
print("토큰 사용량:", msg.usage_metadata)
```

```python
from langchain_openai import ChatOpenAI

# 추론 강도 + 추론 요약 (Responses API로 자동 전환)
llm = ChatOpenAI(
    model="gpt-5-mini",
    reasoning={"effort": "low", "summary": "auto"},
    output_version="v1",  # content를 표준 콘텐츠 블록 리스트로
)
msg = llm.invoke("17 * 23은?")
for block in msg.content_blocks:
    print(block["type"], "|", block.get("text") or block.get("reasoning"))
```

```python
from langchain_openai import ChatOpenAI

# OpenAI 내장 웹 검색 도구 (Responses API 필요, 실제 키 필요 — Mock 모드는 내장 도구 미지원)
llm = ChatOpenAI(model="gpt-5-mini")
llm_with_search = llm.bind_tools([{"type": "web_search"}])
print(llm_with_search.invoke("오늘 서울 날씨 요약").text)
```

## 주의사항

> [!WARNING]
> GPT-5 계열(추론 모델)에 `temperature`, `top_p`를 지정하면 API가 요청을 거부합니다. 출력 다양성은 프롬프트로 조절하고, 추론량은 `reasoning_effort`로 조절하세요.

> [!WARNING]
> `stream_chunk_timeout`은 비동기 스트리밍(`astream`, `astream_events`, 에이전트의 `ainvoke` 스트리밍)에만 적용됩니다. 기본 120초 동안 콘텐츠 청크가 없으면 `StreamChunkTimeoutError`(`asyncio.TimeoutError` 하위 클래스)가 발생합니다. 매우 긴 추론이 예상되면 값을 늘리세요.

> [!TIP]
> 데이터 보존을 원하지 않는 조직(ZDR)은 `use_responses_api=True, store=False, include=["reasoning.encrypted_content"]` 조합을 씁니다. 추론 내용을 암호화된 형태로 받아 다음 턴에 다시 보냅니다.

> [!NOTE]
> `max_retries`는 openai SDK 수준 재시도입니다. 에이전트 단위 재시도는 `ModelRetryMiddleware`([내장 미들웨어](/docs/langchain/07-built-in-middleware)) 또는 `.with_retry()`를 쓰세요. 둘을 동시에 크게 잡으면 재시도 횟수가 곱해집니다.

## 관련 문서

- [init_chat_model](/docs/langchain/01-init-chat-model)
- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [메시지와 콘텐츠 블록](/docs/langchain/03-messages)
- [OpenAIEmbeddings](/docs/integrations/02-openai-embeddings)
- [공식 문서: ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)
