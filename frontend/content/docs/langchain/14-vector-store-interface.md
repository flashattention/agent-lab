---
title: "VectorStore 인터페이스"
description: "모든 벡터 스토어가 공유하는 add/search/delete/as_retriever 메서드"
order: 14
source: "https://docs.langchain.com/oss/python/integrations/vectorstores"
tags: [vectorstore, rag, similarity-search, mmr, retriever]
---

`VectorStore`는 LangChain의 벡터 스토어 추상 클래스입니다. Qdrant, Chroma, PGVector, Pinecone 등 모든 통합이 같은 메서드를 구현하므로 백엔드를 바꿔도 RAG 코드가 거의 그대로입니다. 각 DB 고유 기능(필터 문법, 하이브리드 검색)은 `**kwargs`로 전달됩니다. DB별 상세는 [벡터 DB](/docs/vector-db/01-concepts) 섹션을 보세요.

## Import

```python
from langchain_core.vectorstores import VectorStore, InMemoryVectorStore, VectorStoreRetriever
from langchain_core.documents import Document
```

## 시그니처

```python
class VectorStore(ABC):
    embeddings: Embeddings | None  # 프로퍼티

    def add_documents(self, documents: list[Document], **kwargs) -> list[str]
    def add_texts(self, texts: Iterable[str], metadatas: list[dict] | None = None, *,
                  ids: list[str] | None = None, **kwargs) -> list[str]
    def delete(self, ids: list[str] | None = None, **kwargs) -> bool | None
    def get_by_ids(self, ids: Sequence[str], /) -> list[Document]

    def similarity_search(self, query: str, k: int = 4, **kwargs) -> list[Document]
    def similarity_search_with_score(self, *args, **kwargs) -> list[tuple[Document, float]]
    def similarity_search_with_relevance_scores(self, query: str, k: int = 4, **kwargs) -> list[tuple[Document, float]]
    def similarity_search_by_vector(self, embedding: list[float], k: int = 4, **kwargs) -> list[Document]
    def max_marginal_relevance_search(self, query: str, k: int = 4, fetch_k: int = 20,
                                      lambda_mult: float = 0.5, **kwargs) -> list[Document]
    def search(self, query: str, search_type: str, **kwargs) -> list[Document]

    def as_retriever(self, **kwargs) -> VectorStoreRetriever

    @classmethod
    def from_documents(cls, documents: list[Document], embedding: Embeddings, **kwargs) -> Self
    @classmethod
    def from_texts(cls, texts: list[str], embedding: Embeddings, metadatas=None, *, ids=None, **kwargs)
    # 모든 메서드에 a* 비동기 버전 존재 (aadd_documents, asimilarity_search, ...)

InMemoryVectorStore(embedding: Embeddings)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `documents` | `list[Document]` | 필수 | `Document(page_content, metadata, id)`. `id`가 있으면 그 ID로 저장(upsert). |
| `ids` | `list[str] \| None` | `None` | 문서 ID. 지정하지 않으면 UUID가 생성됩니다. 같은 ID로 다시 넣으면 덮어씁니다. |
| `query` | `str` | 필수 | 검색어. 내부에서 `embed_query`로 임베딩. |
| `k` | `int` | `4` | 반환 개수. |
| `fetch_k` | `int` | `20` | (MMR) 다양성 재정렬 전에 가져올 후보 수. |
| `lambda_mult` | `float` | `0.5` | (MMR) 1에 가까울수록 관련성, 0에 가까울수록 다양성. |
| `filter` (kwargs) | DB별 | | 메타데이터 필터. `InMemoryVectorStore`는 `Callable[[Document], bool]`, Qdrant는 `models.Filter`, Chroma는 dict 등 **DB마다 다릅니다**. |

### as_retriever 인자

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `search_type` | `"similarity" \| "mmr" \| "similarity_score_threshold"` | `"similarity"` | 검색 방식. |
| `search_kwargs` | `dict` | `{}` | `k`, `filter`, `fetch_k`, `lambda_mult`, `score_threshold`(threshold 방식 필수). |
| `tags` / `metadata` | | | 트레이싱 태그/메타데이터. |

## 메서드와 반환값

| 메서드 | 반환 | 점수 의미 |
|---|---|---|
| `similarity_search` | `list[Document]` | |
| `similarity_search_with_score` | `list[(Document, float)]` | DB 고유 점수(거리일 수도, 유사도일 수도 있음). |
| `similarity_search_with_relevance_scores` | `list[(Document, float)]` | 0~1로 정규화된 관련도(클수록 관련). |
| `as_retriever()` | `VectorStoreRetriever` | `invoke(query) -> list[Document]` Runnable. |

`InMemoryVectorStore` 추가 메서드: `dump(path)`, `InMemoryVectorStore.load(path, embedding)`.

## 예제

```python
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

store = InMemoryVectorStore(OpenAIEmbeddings(model="text-embedding-3-small"))
ids = store.add_documents([
    Document("LangGraph는 상태 그래프 런타임이다.", metadata={"topic": "langgraph"}, id="d1"),
    Document("체크포인터는 스레드별 상태를 저장한다.", metadata={"topic": "langgraph"}, id="d2"),
    Document("Qdrant는 Rust로 만든 벡터 DB다.", metadata={"topic": "vectordb"}, id="d3"),
])
print(ids)

for doc, score in store.similarity_search_with_score("상태 저장", k=2):
    print(round(score, 3), doc.id, doc.page_content)

# InMemoryVectorStore의 filter는 Document를 받는 함수
only_db = store.similarity_search("데이터베이스", k=2, filter=lambda d: d.metadata["topic"] == "vectordb")
print([d.id for d in only_db])

retriever = store.as_retriever(search_type="mmr", search_kwargs={"k": 2, "fetch_k": 3})
print([d.id for d in retriever.invoke("LangGraph")])

store.delete(ids=["d3"])
print(store.get_by_ids(["d1", "d3"]))  # 삭제된 d3는 빠짐
```

## 주의사항

> [!WARNING]
> `filter` 형식은 DB마다 다릅니다. 같은 `as_retriever(search_kwargs={"filter": ...})` 코드라도 백엔드를 바꾸면 필터 객체를 다시 써야 합니다.

> [!WARNING]
> `similarity_search_with_score`의 점수는 DB와 거리 함수에 따라 "작을수록 가깝다"(거리)일 수도, "클수록 가깝다"(유사도)일 수도 있습니다. 임계값 필터링에는 정규화된 `similarity_search_with_relevance_scores`나 `search_type="similarity_score_threshold"`를 쓰세요.

> [!TIP]
> 재색인 시 중복을 막으려면 원문 경로·청크 번호 같은 **결정적 ID**를 지정하세요. 같은 ID로 다시 넣으면 덮어쓰기(upsert)가 됩니다.

## 관련 문서

- [Retriever](/docs/langchain/15-retrievers)
- [임베딩](/docs/langchain/13-embeddings)
- [InMemoryVectorStore](/docs/vector-db/03-in-memory)
- [Qdrant](/docs/vector-db/04-qdrant)
- [Chroma](/docs/vector-db/05-chroma)
- [벡터 DB 비교](/docs/vector-db/02-comparison)
