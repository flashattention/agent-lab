---
title: "RetryPolicy / CachePolicy / TimeoutPolicy"
description: "노드·task 단위 재시도, 결과 캐시(InMemoryCache, SqliteCache), 실행/유휴 타임아웃 정책"
order: 16
source: "https://docs.langchain.com/oss/python/langgraph/graph-api#retry-policies"
tags: [retry, cache, timeout, policy, reliability]
---

노드(`add_node`), 함수형 API(`@task`, `@entrypoint`), `Send`에 붙이는 실행 정책입니다.

| 정책 | 적용 위치 | 목적 |
|---|---|---|
| `RetryPolicy` | `add_node(retry_policy=)`, `@task`, `@entrypoint` | 일시적 오류 자동 재시도(지수 백오프) |
| `CachePolicy` | `add_node(cache_policy=)`, `@task`, `@entrypoint` | 같은 입력이면 이전 결과 재사용 |
| `TimeoutPolicy` | `add_node(timeout=)`, `@task`, `@entrypoint`, `Send(timeout=)` | 시도(attempt)당 실행/유휴 시간 제한 |

## Import

```python
from langgraph.types import RetryPolicy, CachePolicy, TimeoutPolicy
from langgraph.cache.memory import InMemoryCache
from langgraph.cache.sqlite import SqliteCache
```

## 시그니처

```python
class RetryPolicy(NamedTuple):
    initial_interval: float = 0.5
    backoff_factor: float = 2.0
    max_interval: float = 128.0
    max_attempts: int = 3
    jitter: bool = True
    retry_on: type[Exception] | Sequence[type[Exception]] | Callable[[Exception], bool] = default_retry_on

@dataclass
class CachePolicy:
    key_func: Callable[..., str | bytes] = default_cache_key
    ttl: int | None = None

@dataclass(frozen=True)
class TimeoutPolicy:
    run_timeout: float | timedelta | None = None
    idle_timeout: float | timedelta | None = None
    refresh_on: Literal["auto", "heartbeat"] = "auto"

InMemoryCache(*, serde: SerializerProtocol | None = None)
SqliteCache(*, path: str, serde: SerializerProtocol | None = None)
```

## 파라미터

### RetryPolicy

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `initial_interval` | `float` | `0.5` | 첫 재시도 전 대기(초) |
| `backoff_factor` | `float` | `2.0` | 재시도마다 대기 시간 배수 |
| `max_interval` | `float` | `128.0` | 최대 대기(초) |
| `max_attempts` | `int` | `3` | 최초 시도 포함 총 시도 횟수 |
| `jitter` | `bool` | `True` | 대기 시간에 무작위 지터 추가 |
| `retry_on` | 예외 타입 / 튜플 / 판별 함수 | `default_retry_on` | 재시도할 예외 |

`default_retry_on`: `ConnectionError`와 5xx `httpx.HTTPStatusError`/`requests.HTTPError`는 재시도, `ValueError`, `TypeError`, `ArithmeticError`, `ImportError`, `LookupError`, `NameError`, `SyntaxError`, `RuntimeError`, `ReferenceError`, `StopIteration`, `StopAsyncIteration`, `OSError`는 재시도 안 함, 그 밖의 예외는 재시도.

### CachePolicy

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `key_func` | `Callable` | `default_cache_key` | 노드 입력 → 캐시 키. 기본은 입력을 pickle로 해시 |
| `ttl` | `int \| None` | `None` | 만료(초). `None`이면 만료 없음 |

### TimeoutPolicy

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `run_timeout` | `float \| timedelta \| None` | `None` | 한 시도의 총 실행 시간 상한 |
| `idle_timeout` | `float \| timedelta \| None` | `None` | 진행 신호 없이 지속될 수 있는 최대 시간 |
| `refresh_on` | `"auto" \| "heartbeat"` | `"auto"` | idle 타이머 갱신 신호. `"auto"`: 상태 쓰기, 스트림 청크, 콜백 이벤트, 하트비트. `"heartbeat"`: `runtime.heartbeat()`만 |

`timeout=5`처럼 숫자를 주면 `TimeoutPolicy(run_timeout=5)`로 변환됩니다.

## 메서드와 반환값

- 재시도가 모두 실패하면 마지막 예외가 전파됩니다(또는 `error_handler`가 있으면 핸들러 실행).
- 타임아웃 초과 시 `NodeTimeoutError`(`kind="run"|"idle"`, `elapsed`). 이 예외는 `TimeoutError`를 상속하지 않으므로 **기본 RetryPolicy로 재시도됩니다**.
- 캐시 적중 시 `stream_mode="updates"` 청크에 `"__metadata__": {"cached": True}`가 붙습니다.
- `graph.clear_cache(nodes=None)`로 캐시를 비웁니다.

## 예제

### 재시도 + 캐시

```python
from typing import TypedDict

from langgraph.cache.memory import InMemoryCache
from langgraph.graph import StateGraph, START
from langgraph.types import CachePolicy, RetryPolicy


class State(TypedDict):
    q: str
    a: str


calls = {"n": 0}


def flaky_search(state: State) -> dict:
    calls["n"] += 1
    if calls["n"] < 2:
        raise ConnectionError("일시 장애")  # default_retry_on이 재시도하는 예외
    return {"a": f"result for {state['q']}"}


builder = StateGraph(State)
builder.add_node(
    "search",
    flaky_search,
    retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.01),
    cache_policy=CachePolicy(ttl=300),
)
builder.add_edge(START, "search")
graph = builder.compile(cache=InMemoryCache())

print(graph.invoke({"q": "langgraph", "a": ""}))                      # 2번째 시도에 성공
print(list(graph.stream({"q": "langgraph", "a": ""}, stream_mode="updates")))
# [{'search': {...}, '__metadata__': {'cached': True}}]
print("호출 횟수:", calls["n"])                                        # 2 (캐시 적중)
```

### idle 타임아웃 + heartbeat

```python
import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.runtime import Runtime
from langgraph.types import TimeoutPolicy


class State(TypedDict):
    done: int


async def long_job(state: State, runtime: Runtime) -> dict:
    for _ in range(5):
        await asyncio.sleep(0.1)
        runtime.heartbeat()          # 진행 신호 → idle 타이머 갱신
    return {"done": 5}


builder = StateGraph(State)
builder.add_node(
    "long_job",
    long_job,
    timeout=TimeoutPolicy(idle_timeout=0.3, run_timeout=5, refresh_on="heartbeat"),
)
builder.add_edge(START, "long_job")
print(asyncio.run(builder.compile().ainvoke({"done": 0})))  # {'done': 5}
```

## 주의사항

> [!WARNING]
> 타임아웃은 asyncio 취소에 의존하므로 **async 노드/task에서만** 지원됩니다. 동기 노드에 지정하면 실행 시 `ValueError`가 납니다.

> [!WARNING]
> 기본 `retry_on`은 `ValueError`, `KeyError` 같은 버그성 예외를 재시도하지 않습니다. LLM 응답 파싱 오류처럼 `ValueError` 계열을 재시도하려면 `retry_on`을 명시하세요.

> [!TIP]
> `CachePolicy`는 `compile(cache=...)`(또는 `entrypoint(cache=...)`)가 없으면 아무 효과가 없습니다. 비결정적인 LLM 노드에 캐시를 걸면 같은 입력에 항상 같은 답이 나온다는 점을 기억하세요.

## 관련 문서

- [노드 (add_node)](/docs/langgraph/04-nodes)
- [함수형 API](/docs/langgraph/13-functional-api)
- [Runtime (heartbeat)](/docs/langgraph/12-runtime-context)
- [오류: NodeTimeoutError](/docs/langgraph/18-errors)
- [채팅 모델 with_retry](/docs/langchain/02-chat-model-methods)
