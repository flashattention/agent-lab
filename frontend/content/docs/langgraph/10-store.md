---
title: "Store (장기 기억)"
description: "스레드를 넘나드는 키-값 저장소 InMemoryStore: 네임스페이스, put/get/search/delete, 임베딩 인덱스 기반 시맨틱 검색"
order: 10
source: "https://docs.langchain.com/oss/python/langgraph/persistence#memory-store"
tags: [store, memory, long-term-memory, semantic-search]
---

체크포인터가 **스레드 내부**의 상태를 저장한다면, Store는 **스레드를 넘나드는** 장기 기억(long-term memory)을 저장합니다. 예: 사용자 선호, 학습된 사실, 프로필.

- 데이터는 `(namespace 튜플, key) → dict value` 구조입니다. 네임스페이스는 `("users", user_id, "memories")`처럼 계층적입니다.
- `index`를 설정하면 값을 임베딩해 **시맨틱 검색(semantic search)** 을 지원합니다.
- `compile(store=...)` 또는 `create_agent(store=...)`로 붙이면 노드에서는 `runtime.store`, 도구에서는 `runtime.store`(ToolRuntime) 또는 `InjectedStore`로 접근합니다.

## Import

```python
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore, Item, SearchItem, IndexConfig
```

## 시그니처

```python
InMemoryStore(*, index: IndexConfig | None = None)

class IndexConfig(TypedDict):
    dims: int
    embed: Embeddings | EmbeddingsFunc | AEmbeddingsFunc | str
    fields: NotRequired[list[str] | None]

BaseStore.put(namespace: tuple[str, ...], key: str, value: Mapping[str, Any],
              index: Literal[False] | list[str] | None = None, *, ttl: float | None = ...) -> None
BaseStore.get(namespace: tuple[str, ...], key: str, *, refresh_ttl: bool | None = None) -> Item | None
BaseStore.search(namespace_prefix: tuple[str, ...], /, *, query: str | None = None,
                 filter: dict[str, Any] | None = None, limit: int = 10, offset: int = 0,
                 refresh_ttl: bool | None = None) -> list[SearchItem]
BaseStore.delete(namespace: tuple[str, ...], key: str) -> None
BaseStore.list_namespaces(*, prefix=None, suffix=None, max_depth: int | None = None,
                          limit: int = 100, offset: int = 0) -> list[tuple[str, ...]]
```

## 파라미터

### IndexConfig (`index=`)

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `dims` | `int` | (필수) | 임베딩 차원. `text-embedding-3-small`은 1536 |
| `embed` | `Embeddings \| callable \| str` | (필수) | 임베딩 모델. `"openai:text-embedding-3-small"` 문자열도 가능(`init_embeddings`로 생성) |
| `fields` | `list[str] \| None` | `["$"]` | 임베딩할 값 필드(JSON 경로). 기본은 값 전체 |

### put / search

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `namespace` | `tuple[str, ...]` | (필수) | 계층 네임스페이스 |
| `key` | `str` | (필수) | 네임스페이스 내 고유 키. 같은 키로 put하면 덮어씀 |
| `value` | `dict` | (필수) | 저장할 JSON 직렬화 가능 dict |
| `index` | `False \| list[str] \| None` | `None` | 이 항목의 임베딩 필드 재정의. `False`면 임베딩 안 함 |
| `ttl` | `float \| None` | 미지정 | 만료 시간(분). 저장소가 TTL을 지원할 때만 |
| `namespace_prefix` | `tuple[str, ...]` | (필수) | 검색할 네임스페이스 접두어(위치 전용 인자) |
| `query` | `str \| None` | `None` | 자연어 질의. `index`가 있을 때 유사도 순 정렬 |
| `filter` | `dict \| None` | `None` | 값 필드 일치 필터 |
| `limit` / `offset` | `int` | `10` / `0` | 페이지네이션 |

## 메서드와 반환값

| 반환 타입 | 필드 |
|---|---|
| `Item` | `namespace`, `key`, `value`, `created_at`, `updated_at` |
| `SearchItem` | `Item` 필드 + `score: float \| None`(시맨틱 검색 시 유사도) |

모든 메서드에 `aput`, `aget`, `asearch`, `adelete`, `alist_namespaces` 비동기 버전과 일괄 처리용 `batch`/`abatch`가 있습니다.

## 예제

### 기본 CRUD + 시맨틱 검색

```python
from langchain_openai import OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(
    index={"embed": OpenAIEmbeddings(model="text-embedding-3-small"), "dims": 1536, "fields": ["text"]}
)

ns = ("users", "u-123", "memories")
store.put(ns, "food", {"text": "김치찌개를 좋아한다"})
store.put(ns, "job", {"text": "백엔드 파이썬 개발자"})
store.put(ns, "tmp", {"text": "임시 메모"}, index=False)  # 임베딩 제외

print(store.get(ns, "food").value)                        # {'text': '김치찌개를 좋아한다'}
for item in store.search(("users", "u-123"), query="좋아하는 음식", limit=2):
    print(item.key, item.score)                            # 유사도 순
print(store.list_namespaces(prefix=("users",)))            # [('users', 'u-123', 'memories')]

store.delete(ns, "tmp")
```

### 노드에서 Runtime으로 접근

```python
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore


@dataclass
class Ctx:
    user_id: str


class State(TypedDict):
    greeting: str


def greet(state: State, runtime: Runtime[Ctx]) -> dict:
    ns = ("users", runtime.context.user_id)
    profile = runtime.store.get(ns, "profile")
    name = profile.value["name"] if profile else "손님"
    runtime.store.put(ns, "last_seen", {"ok": True})
    return {"greeting": f"안녕하세요, {name}님"}


store = InMemoryStore()
store.put(("users", "u1"), "profile", {"name": "지민"})

graph = StateGraph(State, context_schema=Ctx).add_node("greet", greet).add_edge(START, "greet").compile(store=store)
print(graph.invoke({"greeting": ""}, context=Ctx(user_id="u1")))  # {'greeting': '안녕하세요, 지민님'}
```

## 주의사항

> [!WARNING]
> `search()`의 첫 인자는 **접두어(prefix)** 이고 위치 전용입니다. `store.search(namespace_prefix=...)`처럼 키워드로 넘기면 `TypeError`가 납니다.

> [!WARNING]
> `index` 없이 만든 Store에서 `query=`로 검색하면 유사도 정렬이 되지 않습니다(필터/최신 순 조회만 의미 있음). 시맨틱 검색에는 `index`가 필수입니다.

> [!TIP]
> `InMemoryStore`는 개발용입니다. 프로덕션은 `PostgresStore`(`langgraph-checkpoint-postgres`) 또는 LangGraph Server의 내장 Store를 쓰세요. 네임스페이스에 반드시 사용자 ID를 넣어 사용자 간 데이터가 섞이지 않게 하세요.

## 관련 문서

- [체크포인터](/docs/langgraph/09-checkpointers)
- [Runtime과 context_schema](/docs/langgraph/12-runtime-context)
- [prebuilt: InjectedStore](/docs/langgraph/17-prebuilt)
- [ToolRuntime](/docs/langchain/05-tool-runtime)
- [임베딩](/docs/langchain/13-embeddings)
