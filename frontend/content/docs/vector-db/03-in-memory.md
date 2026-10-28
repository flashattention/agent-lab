---
title: "InMemoryVectorStore"
description: "langchain-core에 내장된 의존성 없는 인메모리 벡터 스토어"
order: 3
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/in_memory"
tags: [vector-db, in-memory, langchain-core]
---

# InMemoryVectorStore

`langchain-core`에 포함된 가장 단순한 벡터 스토어입니다. 문서와 벡터를 파이썬 딕셔너리에 저장하고 **전수 코사인 유사도(Flat)** 로 검색합니다. 별도 서버나 패키지가 필요 없어 학습, 단위 테스트, 수천 건 이하 프로토타입에 적합합니다.

## Import

```bash
pip install langchain-core  # langchain 설치 시 함께 설치됨
```

```python
from langchain_core.vectorstores import InMemoryVectorStore
```

## 시그니처

```python
InMemoryVectorStore(embedding: Embeddings) -> None

# 클래스 메서드
InMemoryVectorStore.from_texts(texts: list[str], embedding: Embeddings,
                               metadatas: list[dict] | None = None, **kwargs) -> InMemoryVectorStore
InMemoryVectorStore.from_documents(documents: list[Document], embedding: Embeddings, **kwargs)
InMemoryVectorStore.load(path: str, embedding: Embeddings, **kwargs) -> InMemoryVectorStore
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `embedding` | `Embeddings` | (필수) | 문서·질의를 벡터로 바꿀 임베딩 객체. 예: `OpenAIEmbeddings(model="text-embedding-3-small")` |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `add_documents(documents, ids=None)` | `list[str]` | 문서 추가. `ids` 생략 시 UUID 생성. 같은 ID면 덮어씀 |
| `add_texts(texts, metadatas=None, ids=None)` | `list[str]` | 텍스트 리스트 추가 |
| `similarity_search(query, k=4, filter=None)` | `list[Document]` | 코사인 유사도 상위 k개 |
| `similarity_search_with_score(query, k=4, filter=None)` | `list[tuple[Document, float]]` | 점수는 코사인 유사도(클수록 유사) |
| `similarity_search_by_vector(embedding, k=4, **kwargs)` | `list[Document]` | 이미 계산한 벡터로 검색 (`filter=`는 kwargs로 전달) |
| `max_marginal_relevance_search(query, k=4, fetch_k=20, lambda_mult=0.5, filter=None)` | `list[Document]` | MMR로 다양성 확보 |
| `get_by_ids(ids, /)` | `list[Document]` | ID로 조회 |
| `delete(ids=None)` | `None` | ID로 삭제 |
| `dump(path)` / `load(path, embedding)` | `None` / 스토어 | JSON 파일로 저장·복원 |
| `as_retriever(**kwargs)` | `VectorStoreRetriever` | `search_type="similarity"` 또는 `"mmr"` |
| `asimilarity_search`, `aadd_documents` … | 코루틴 | 비동기 버전 |

- `filter`는 딕셔너리가 아니라 **`Callable[[Document], bool]` 함수**입니다.
- 반환되는 `Document`의 `id` 필드에 저장 ID가 채워집니다.

## 예제

### 추가·필터 검색·삭제

```python
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
store = InMemoryVectorStore(embedding=embeddings)

ids = store.add_documents(
    [
        Document(page_content="LangGraph는 상태 기반 그래프 런타임이다.", metadata={"topic": "langgraph"}),
        Document(page_content="Qdrant는 Rust로 작성된 벡터 DB다.", metadata={"topic": "vectordb"}),
        Document(page_content="체크포인터는 스레드별 상태를 저장한다.", metadata={"topic": "langgraph"}),
    ],
    ids=["d1", "d2", "d3"],
)

# 메타데이터 필터는 Document -> bool 함수
docs = store.similarity_search(
    "그래프 상태 저장", k=2, filter=lambda d: d.metadata["topic"] == "langgraph"
)
for d in docs:
    print(d.id, d.page_content)

for doc, score in store.similarity_search_with_score("벡터 DB", k=1):
    print(f"{score:.3f}", doc.page_content)

print(store.get_by_ids(["d2"])[0].metadata)
store.delete(ids=["d2"])
```

### MMR 리트리버

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

store = InMemoryVectorStore.from_texts(
    ["파이썬 리스트", "파이썬 리스트 컴프리헨션", "파이썬 딕셔너리", "자바 스트림", "러스트 소유권"],
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)

mmr = store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 3, "fetch_k": 5, "lambda_mult": 0.3},  # lambda↓ = 다양성↑
)
print([d.page_content for d in mmr.invoke("파이썬 자료구조")])
```

## 주의사항

> [!WARNING]
> `as_retriever(search_type="similarity_score_threshold")`는 InMemoryVectorStore에서 **`NotImplementedError`** 가 납니다. relevance score 함수(`_select_relevance_score_fn`)를 구현하지 않았기 때문입니다. 임계값 필터가 필요하면 `similarity_search_with_score` 결과를 직접 거르거나 Qdrant/Chroma를 쓰세요.

> [!WARNING]
> 프로세스가 끝나면 데이터가 사라집니다. `dump()`는 JSON에 벡터를 그대로 쓰므로 수만 건 이상에서는 파일이 커지고 느립니다. 검색도 O(N) 전수 비교라 운영용이 아닙니다.

> [!TIP]
> 테스트에서는 `langchain_core.embeddings.DeterministicFakeEmbedding(size=...)`과 조합하면 API 호출 없이 결정적인 결과를 얻을 수 있습니다.

## 관련 문서

- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [리트리버](/docs/langchain/15-retrievers)
- [Qdrant](/docs/vector-db/04-qdrant) — 같은 코드를 영속 DB로 옮길 때
- [공식 문서: InMemoryVectorStore](https://docs.langchain.com/oss/python/integrations/vectorstores/in_memory)
