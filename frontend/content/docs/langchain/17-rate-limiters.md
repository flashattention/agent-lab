---
title: "Rate Limiter"
description: "InMemoryRateLimiter로 채팅 모델의 초당 요청 수를 제한하기"
order: 17
source: "https://reference.langchain.com/python/langchain_core/rate_limiters/"
tags: [rate-limit, chat-model, throttling, production]
---

`InMemoryRateLimiter`는 토큰 버킷(token bucket) 방식으로 **요청 수**를 제한합니다. 채팅 모델 생성 시 `rate_limiter=`로 넘기면 모델 호출(`invoke`/`stream`/`batch`, 에이전트 내부 호출 포함) 직전에 버킷에서 토큰을 하나 꺼내고, 없으면 기다립니다. 여기서 "토큰"은 LLM 토큰이 아니라 요청 허용량입니다.

## Import

```python
from langchain_core.rate_limiters import InMemoryRateLimiter, BaseRateLimiter
```

## 시그니처

```python
class InMemoryRateLimiter(BaseRateLimiter):
    def __init__(
        self,
        *,
        requests_per_second: float = 1,
        check_every_n_seconds: float = 0.1,
        max_bucket_size: float = 1,
    ) -> None

    def acquire(self, *, blocking: bool = True) -> bool
    async def aacquire(self, *, blocking: bool = True) -> bool
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `requests_per_second` | `float` | `1` | 초당 버킷에 채워지는 토큰 수. `0.5`면 2초에 1회. |
| `check_every_n_seconds` | `float` | `0.1` | 토큰이 생겼는지 확인하는 주기(초). |
| `max_bucket_size` | `float` | `1` | 버킷 최대 크기(최소 1). 클수록 순간 폭주(burst)를 더 허용합니다. |
| `blocking` | `bool` | `True` | (`acquire`) `False`면 기다리지 않고 즉시 `True/False` 반환. |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `acquire(blocking=True)` | `bool` | 토큰을 얻으면 `True`. 블로킹 모드에서는 얻을 때까지 대기. |
| `aacquire(blocking=True)` | `bool` | 비동기 버전(`asyncio.sleep`으로 대기). |

채팅 모델의 `rate_limiter` 필드(`BaseChatModel.rate_limiter`)에 넣으면 모델이 자동으로 호출합니다.

## 예제

```python
import os
import time
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

limiter = InMemoryRateLimiter(requests_per_second=4, check_every_n_seconds=0.05, max_bucket_size=1)
llm = init_chat_model(MODEL, rate_limiter=limiter)

start = time.perf_counter()
for i in range(3):
    llm.invoke(f"{i}번째 요청")
    print(f"{i}: {time.perf_counter() - start:.2f}s")  # 실제 모델 기준 약 0.25초 간격
```

직접 사용(외부 API 호출 제한):

```python
import time
from langchain_core.rate_limiters import InMemoryRateLimiter

limiter = InMemoryRateLimiter(requests_per_second=10, max_bucket_size=2)
print(limiter.acquire(blocking=False))  # False: 버킷은 비어 있는 상태로 시작
time.sleep(0.5)                         # 0.5초 동안 5개가 채워지지만 최대 2개까지만 보관
print([limiter.acquire(blocking=False) for _ in range(4)])  # [True, True, False, False]
```

## 주의사항

> [!WARNING]
> `InMemoryRateLimiter`는 **프로세스 하나 안에서만** 동작합니다. 여러 워커/서버가 같은 API 키를 쓰면 전체 한도를 지킬 수 없습니다. 분산 환경에서는 Redis 기반 리미터나 API 게이트웨이를 쓰세요.

> [!WARNING]
> 요청 수만 제한하고 **토큰 수(TPM)** 는 제한하지 않습니다. OpenAI의 TPM 한도에 걸리는 경우는 재시도(`max_retries`, `ModelRetryMiddleware`)와 함께 쓰세요.

> [!TIP]
> 버킷은 **비어 있는 상태로 시작**하므로 첫 요청도 `1 / requests_per_second`초가량 기다릴 수 있습니다. 대량 `batch` 처리에는 `config={"max_concurrency": N}`과 함께 써서 동시성과 속도를 모두 제어하세요.

## 관련 문서

- [init_chat_model](/docs/langchain/01-init-chat-model)
- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [내장 미들웨어 (ModelRetryMiddleware)](/docs/langchain/07-built-in-middleware)
- [ChatOpenAI](/docs/integrations/01-openai-chat)
