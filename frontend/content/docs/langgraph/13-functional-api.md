---
title: "함수형 API (entrypoint / task)"
description: "그래프 정의 없이 일반 파이썬 함수로 체크포인트·interrupt·병렬 실행을 쓰는 @entrypoint, @task, entrypoint.final"
order: 13
source: "https://docs.langchain.com/oss/python/langgraph/functional-api"
tags: [functional-api, entrypoint, task, workflow]
---

함수형 API(Functional API)는 `StateGraph` 없이 일반 제어 흐름(if, for, while)으로 워크플로를 작성합니다. 내부적으로 같은 Pregel 런타임을 쓰므로 체크포인트, `interrupt`, 스트리밍, 재시도를 그대로 사용할 수 있습니다.

- `@entrypoint`: 워크플로 진입 함수. 결과는 `Pregel` 객체로, `invoke`/`stream`/`get_state`를 가집니다.
- `@task`: 단위 작업. 호출하면 즉시 **future**를 반환하고 `.result()`로 값을 얻습니다. 결과는 체크포인트에 저장되어 재개 시 다시 실행되지 않습니다.

## Import

```python
from langgraph.func import entrypoint, task
```

## 시그니처

```python
class entrypoint:
    def __init__(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        cache: BaseCache | None = None,
        context_schema: type[ContextT] | None = None,
        cache_policy: CachePolicy | None = None,
        retry_policy: RetryPolicy | Sequence[RetryPolicy] | None = None,
        timeout: float | timedelta | TimeoutPolicy | None = None,
    ) -> None: ...

    @dataclass
    class final(Generic[R, S]):
        value: R   # 호출자에게 반환할 값
        save: S    # 다음 호출의 previous로 저장할 값

def task(
    __func_or_none__=None,
    *,
    name: str | None = None,
    retry_policy: RetryPolicy | Sequence[RetryPolicy] | None = None,
    cache_policy: CachePolicy | None = None,
    timeout: float | timedelta | TimeoutPolicy | None = None,
)
```

## 파라미터

### entrypoint

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `checkpointer` | `BaseCheckpointSaver \| None` | `None` | 영속화. `previous`, `interrupt`에 필요 |
| `store` | `BaseStore \| None` | `None` | 장기 기억 저장소 |
| `cache` | `BaseCache \| None` | `None` | task `cache_policy`용 캐시 |
| `context_schema` | `type \| None` | `None` | 런타임 컨텍스트 스키마 |
| `cache_policy` / `retry_policy` / `timeout` | | `None` | entrypoint 자체에 적용할 정책 |

entrypoint 함수가 받을 수 있는 키워드 인자: `previous`(이전 반환/저장값), `runtime`(`Runtime`: context, store, stream_writer 포함), `config`(`RunnableConfig`).

### task

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `name` | `str \| None` | `None` | 태스크 이름(기본 함수명) |
| `retry_policy` | `RetryPolicy \| Sequence \| None` | `None` | 재시도 |
| `cache_policy` | `CachePolicy \| None` | `None` | 결과 캐시 |
| `timeout` | `float \| timedelta \| TimeoutPolicy \| None` | `None` | 타임아웃(async task 전용) |

## 메서드와 반환값

- `@entrypoint` 결과: `Pregel` 인스턴스. `invoke(input, config)`, `stream`, `ainvoke`, `get_state`, `get_state_history` 등을 지원. 입력은 **위치 인자 하나**입니다(여러 값은 dict로).
- `@task` 호출 결과: `SyncAsyncFuture`. `.result()`로 동기 대기, async에서는 `await`.
- `entrypoint.final(value=..., save=...)`: 반환값과 다음 호출의 `previous`를 다르게 지정.

## 예제

### 병렬 task + previous 누적

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task


@task
def score(text: str) -> int:
    return len(text)


@entrypoint(checkpointer=InMemorySaver())
def workflow(texts: list[str], *, previous: int | None = None) -> entrypoint.final[dict, int]:
    futures = [score(t) for t in texts]          # 즉시 반환 → 병렬 실행
    total = sum(f.result() for f in futures)
    running = (previous or 0) + total
    # value는 호출자에게, save는 다음 호출의 previous로
    return entrypoint.final(value={"batch": total, "running": running}, save=running)


cfg = {"configurable": {"thread_id": "s1"}}
print(workflow.invoke(["ab", "cde"], cfg))  # {'batch': 5, 'running': 5}
print(workflow.invoke(["xyz"], cfg))        # {'batch': 3, 'running': 8}
```

### interrupt와 함께

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, interrupt


@task
def draft(topic: str) -> str:
    return f"[{topic}] 초안"


@entrypoint(checkpointer=InMemorySaver())
def write(topic: str) -> str:
    text = draft(topic).result()          # 재개 시 다시 실행되지 않음(체크포인트에 저장)
    feedback = interrupt({"draft": text})
    return f"{text} + 피드백: {feedback}"


cfg = {"configurable": {"thread_id": "w1"}}
for chunk in write.stream("LangGraph", cfg):
    print(chunk)                          # {'draft': ...}, {'__interrupt__': (...)}
print(write.invoke(Command(resume="좋아요"), cfg))
```

## 주의사항

> [!WARNING]
> 부작용(API 호출, 랜덤, 현재 시각)은 반드시 `@task` 안에서 실행하세요. entrypoint 본문은 재개 시 처음부터 다시 실행되므로, task 밖의 부작용은 중복 실행되고 비결정적 값은 달라집니다.

> [!WARNING]
> task 입력/출력과 entrypoint 반환값은 체크포인트에 저장되므로 직렬화 가능해야 합니다. 또한 `@task`는 entrypoint(또는 StateGraph 노드) **실행 중에만** 호출할 수 있습니다.

> [!TIP]
> 그래프 시각화, 조건부 라우팅 구조가 중요하면 Graph API, 기존 파이썬 코드에 영속성·HITL만 얹고 싶으면 함수형 API가 적합합니다. 두 API는 섞어 쓸 수 있습니다(StateGraph 노드에서 task 호출, 노드로 entrypoint 사용).

## 관련 문서

- [StateGraph](/docs/langgraph/01-state-graph)
- [interrupt](/docs/langgraph/08-interrupt)
- [정책 (RetryPolicy, CachePolicy)](/docs/langgraph/16-policies)
- [Runtime (previous)](/docs/langgraph/12-runtime-context)
- [durability 모드](/docs/langgraph/19-durability)
