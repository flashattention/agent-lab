---
title: "Chroma"
description: "langchain-chroma의 Chroma 벡터 스토어: EphemeralClient, 영속 저장, where 필터"
order: 5
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/chroma"
tags: [vector-db, chroma, filter]
---

# Chroma

Chroma는 파이썬 프로세스 안에 임베디드로 띄울 수 있는 오픈소스 벡터 DB입니다. 메모리 전용(Ephemeral), 로컬 디스크 영속(Persistent), 클라이언트–서버(HTTP), Chroma Cloud 네 가지 방식으로 연결할 수 있습니다.

## Import

```bash
pip install langchain-chroma chromadb   # AgentLab: langchain-chroma 1.1.0, chromadb 1.5.9
```

```python
import chromadb
from langchain_chroma import Chroma
```

## 시그니처

```python
Chroma(
    collection_name: str = "langchain",
    embedding_function: Embeddings | None = None,
    persist_directory: str | None = None,
    host: str | None = None,
    port: int | None = None,
    headers: dict[str, str] | None = None,
    chroma_cloud_api_key: str | None = None,
    tenant: str | None = None,
    database: str | None = None,
    client_settings: chromadb.config.Settings | None = None,
    collection_metadata: dict | None = None,
    collection_configuration: CreateCollectionConfiguration | None = None,
    client: chromadb.ClientAPI | None = None,
    relevance_score_fn: Callable[[float], float] | None = None,
    create_collection_if_not_exists: bool | None = True,
    *,
    ssl: bool = False,
)

Chroma.from_documents(documents, embedding=None, ids=None, collection_name="langchain",
                      persist_directory=None, client=None, collection_configuration=None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `collection_name` | `str` | `"langchain"` | 컬렉션 이름. **3자 이상** 규칙 등 Chroma 이름 제약을 따름 |
| `embedding_function` | `Embeddings \| None` | `None` | LangChain 임베딩 객체 (`from_documents`에서는 `embedding=`) |
| `persist_directory` | `str \| None` | `None` | 지정하면 로컬 디스크에 영속 저장 (PersistentClient) |
| `host` / `port` / `ssl` / `headers` | | `None` / `None` / `False` / `None` | Chroma 서버(HTTP) 연결 |
| `chroma_cloud_api_key` / `tenant` / `database` | `str \| None` | `None` | Chroma Cloud 연결 |
| `client` | `chromadb.ClientAPI \| None` | `None` | 직접 만든 클라이언트 (`EphemeralClient()`, `PersistentClient(path)`, `HttpClient(...)`) |
| `collection_metadata` | `dict \| None` | `None` | 컬렉션 메타데이터 |
| `collection_configuration` | `CreateCollectionConfiguration \| None` | `None` | 인덱스 설정. 예: `{"hnsw": {"space": "cosine"}}` (`cosine`, `l2`, `ip`) |
| `relevance_score_fn` | `Callable[[float], float] \| None` | `None` | 거리 → 0~1 관련도 변환 함수 직접 지정 |
| `create_collection_if_not_exists` | `bool \| None` | `True` | 없으면 생성 |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `add_documents(documents, ids=None)` / `add_texts(texts, metadatas=None, ids=None)` | `list[str]` | 업서트 |
| `similarity_search(query, k=4, filter=None)` | `list[Document]` | `filter` = Chroma `where` 딕셔너리 |
| `similarity_search_with_score(query, k=4, filter=None, where_document=None)` | `list[tuple[Document, float]]` | 점수 = **거리**(작을수록 유사) |
| `similarity_search_with_relevance_scores(query, k=4)` | `list[tuple[Document, float]]` | 0~1 관련도(클수록 유사) |
| `max_marginal_relevance_search(query, k=4, fetch_k=20, lambda_mult=0.5, filter=None, where_document=None)` | `list[Document]` | MMR |
| `get(ids=None, where=None, limit=None, offset=None, where_document=None, include=None)` | `dict` | 원시 조회 (`ids`, `documents`, `metadatas` …) |
| `get_by_ids(ids, /)` | `list[Document]` | ID 조회 |
| `update_document(id, doc)` / `update_documents(ids, docs)` | `None` | 갱신(재임베딩) |
| `delete(ids=None)` | `None` | 삭제 |
| `reset_collection()` / `delete_collection()` | `None` | 컬렉션 비우기 / 삭제 |
| `hybrid_search(search)` | `list[Document]` | Chroma Search API(`chromadb.Search`, `Knn`, `Rrf`) 기반 하이브리드 검색 |

### `where` 필터 문법

| 연산자 | 예 |
|---|---|
| 동등 (축약) | `{"category": "billing"}` |
| 비교 | `{"version": {"$gte": 2}}` — `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte` |
| 포함 | `{"lang": {"$in": ["ko", "en"]}}` — `$in`, `$nin` |
| 논리 결합 | `{"$and": [{...}, {...}]}`, `{"$or": [...]}` |
| 본문 조건 (`where_document`) | `{"$contains": "환불"}`, `{"$not_contains": "..."}` |

## 예제

```python
import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

store = Chroma(
    collection_name="kb_docs",  # 3자 이상
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    client=chromadb.EphemeralClient(),
    collection_configuration={"hnsw": {"space": "cosine"}},  # 거리 함수 지정
)
store.add_documents(
    [
        Document(page_content="환불은 7일 이내 가능", metadata={"category": "billing", "version": 2}),
        Document(page_content="비밀번호 재설정 방법", metadata={"category": "account", "version": 1}),
        Document(page_content="환불 수수료 정책", metadata={"category": "billing", "version": 1}),
    ],
    ids=["a", "b", "c"],
)

# 조건이 2개 이상이면 반드시 $and/$or로 감싼다
docs = store.similarity_search(
    "환불", k=3, filter={"$and": [{"category": "billing"}, {"version": {"$gte": 2}}]}
)
print([d.page_content for d in docs])

# 본문 텍스트 조건은 where_document
pairs = store.similarity_search_with_score("정책", k=2, where_document={"$contains": "환불"})
print([(d.page_content, round(s, 3)) for d, s in pairs])  # s는 거리

print(store.get(where={"category": "account"}, include=["metadatas"]))
print(store.similarity_search_with_relevance_scores("환불", k=1))  # 0~1 관련도
```

영속 저장:

```python
# 영구 저장 (import는 위 예제와 동일)
store = Chroma(
    collection_name="kb_docs",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./chroma_db",   # 자동 저장, persist() 호출 불필요
)
```

## 주의사항

> [!WARNING]
> `filter={"category": "billing", "version": 2}`처럼 **최상위에 키를 2개 이상** 두면 Chroma가 `ValueError`를 냅니다. `{"$and": [{"category": "billing"}, {"version": 2}]}`로 쓰세요.

> [!WARNING]
> 컬렉션 이름은 3~512자, 영숫자로 시작·끝 등 제약이 있습니다. `"kb"` 같은 2자 이름은 실패합니다.

> [!WARNING]
> `similarity_search_with_score`의 점수는 **거리**입니다(작을수록 유사). 임계값을 걸 때 방향을 헷갈리지 마세요. `similarity_search_with_relevance_scores`와 `search_type="similarity_score_threshold"`는 컬렉션의 `space` 설정으로 변환 함수를 고르므로, `collection_configuration={"hnsw": {"space": ...}}`를 지정하거나 `relevance_score_fn`을 넘기세요.

> [!TIP]
> 메타데이터 값은 `str`, `int`, `float`, `bool`(및 최근 버전의 일부 배열)만 허용됩니다. 중첩 딕셔너리는 평탄화하거나 JSON 문자열로 저장하세요.

> [!NOTE]
> 구버전의 `persist()` 메서드와 `langchain_community.vectorstores.Chroma`는 쓰지 않습니다. `persist_directory`를 주면 자동으로 디스크에 기록됩니다.

## 관련 문서

- [벡터 검색 핵심 개념](/docs/vector-db/01-concepts)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [리트리버](/docs/langchain/15-retrievers)
- [공식 문서: LangChain Chroma](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma)
- [Chroma 필터 문서](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
