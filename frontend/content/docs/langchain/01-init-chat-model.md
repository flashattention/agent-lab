---
title: "init_chat_model"
description: "제공자(provider) 문자열 하나로 어떤 채팅 모델이든 초기화하는 통합 팩토리 함수"
order: 1
source: "https://reference.langchain.com/python/langchain/chat_models/#langchain.chat_models.init_chat_model"
tags: [chat-model, model, provider, configurable]
---

`init_chat_model`은 `"provider:model"` 형식의 문자열로 채팅 모델(Chat Model) 인스턴스를 만드는 팩토리 함수입니다. 제공자별 클래스(`ChatOpenAI`, `ChatAnthropic` 등)를 직접 import하지 않아도 되고, `configurable_fields`를 지정하면 실행 시점(runtime)에 `config`로 모델을 바꿀 수 있는 **설정 가능 모델(Configurable Model)** 을 돌려줍니다.

`create_agent(model="openai:gpt-5-mini")`처럼 문자열을 넘기면 내부에서 이 함수가 호출됩니다.

## Import

```python
from langchain.chat_models import init_chat_model
```

## 시그니처

```python
def init_chat_model(
    model: str | None = None,
    *,
    model_provider: str | None = None,
    configurable_fields: Literal["any"] | list[str] | tuple[str, ...] | None = None,
    config_prefix: str | None = None,
    **kwargs: Any,
) -> BaseChatModel | _ConfigurableModel
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str \| None` | `None` | 모델 이름. `"openai:gpt-5-mini"`처럼 제공자 접두사(prefix)를 붙이는 형식을 권장합니다. 접두사 없이 `"gpt-5-mini"`만 넘기면 이름으로 제공자를 추론합니다(best-effort). |
| `model_provider` | `str \| None` | `None` | 제공자를 접두사 대신 따로 지정합니다. 예: `"openai"`, `"anthropic"`, `"azure_openai"`, `"google_genai"`, `"bedrock_converse"`, `"ollama"` 등. |
| `configurable_fields` | `"any" \| list[str] \| tuple[str, ...] \| None` | `None` | 실행 시 `config["configurable"]`로 바꿀 수 있는 필드 목록. `None`이면 고정 모델을 반환합니다. `model`을 생략하면 기본값이 `("model", "model_provider")`가 됩니다. `"any"`는 모든 필드(API 키, base_url 포함)를 열어 주므로 주의가 필요합니다. |
| `config_prefix` | `str \| None` | `None` | 설정 키 접두사. `"planner"`로 지정하면 `config["configurable"]["planner_model"]`처럼 읽습니다. 한 그래프에 설정 가능 모델이 여러 개일 때 씁니다. |
| `**kwargs` | `Any` | | 제공자 클래스 생성자에 그대로 전달됩니다. 예: `timeout`, `max_retries`, `max_tokens`, `base_url`, `rate_limiter`, `reasoning_effort`(OpenAI). |

## 메서드와 반환값

- `configurable_fields=None`이고 `model`이 주어지면 → 해당 제공자의 `BaseChatModel` 인스턴스(예: `ChatOpenAI`).
- 그 외 → `_ConfigurableModel`. 모든 Runnable 메서드(`invoke`, `stream`, `batch`, `bind_tools`, `with_structured_output` …)를 지원하며, 호출 시점의 `config`로 실제 모델을 만듭니다.

제공자 문자열과 필요한 패키지(일부):

| 제공자(`model_provider`) | 패키지 | 접두사 추론 |
|---|---|---|
| `openai` | `langchain-openai` | `gpt-…`, `o1…`, `o3…` |
| `anthropic` | `langchain-anthropic` | `claude…` |
| `azure_openai` | `langchain-openai` | |
| `google_genai` / `google_vertexai` | `langchain-google-genai` / `-vertexai` | `gemini…` → `google_vertexai` |
| `bedrock_converse` | `langchain-aws` | |
| `mistralai`, `groq`, `ollama`, `deepseek`, `xai` … | 각 파트너 패키지 | |

메서드 목록은 [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)를 보세요.

## 예제

고정 모델:

```python
import os
from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL, timeout=30, max_retries=2)

reply = llm.invoke("LangGraph를 한 문장으로 설명해 줘")
print(reply.text)
```

실행 시점에 모델을 바꾸는 설정 가능 모델:

```python
import os
from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# model을 생략하면 configurable_fields 기본값은 ("model", "model_provider")
llm = init_chat_model(configurable_fields=("model",), config_prefix="main")

reply = llm.invoke(
    "안녕?",
    config={"configurable": {"main_model": MODEL}},
)
print(reply.text)
```

## 주의사항

> [!WARNING]
> GPT-5 계열 추론(reasoning) 모델은 `temperature`를 지원하지 않습니다. `init_chat_model(MODEL, temperature=0)`처럼 넘기면 API가 거부할 수 있으니 이런 모델에는 넣지 마세요. 추론 강도는 `reasoning_effort` 같은 제공자 전용 인자로 조절합니다.

> [!WARNING]
> `configurable_fields="any"`로 만든 모델을 외부 입력으로 설정하게 두면, 사용자가 `api_key`나 `base_url`까지 바꿀 수 있습니다. 바꿀 필드를 명시적으로 나열하세요.

> [!TIP]
> 접두사 없는 이름의 제공자 추론은 보장되지 않습니다. 운영 코드는 `"openai:gpt-5-mini"`처럼 접두사를 붙이고, 모델 ID는 환경변수에서 읽으세요.

## 관련 문서

- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [create_agent](/docs/langchain/06-create-agent)
- [Rate Limiter](/docs/langchain/17-rate-limiters)
- [ChatOpenAI](/docs/integrations/01-openai-chat)
