---
title: "Qdrant"
description: "langchain-qdrant의 QdrantVectorStore: 로컬 :memory:부터 Qdrant Cloud까지, 필터와 하이브리드 검색"
order: 4
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant"
tags: [vector-db, qdrant, hybrid-search, filter]
---

# Qdrant

Qdrant는 Rust로 작성된 오픈소스 벡터 DB입니다. HNSW 인덱스, 강력한 페이로드(payload) 필터, 희소 벡터(sparse vector)를 이용한 하이브리드 검색을 지원합니다. `qdrant-client`는 **서버 없이 `:memory:`나 로컬 파일 모드**로도 동작하므로, 같은 코드를 로컬 개발에서 프로덕션 클러스터까지 그대로 쓸 수 있습니다.

## Import

```bash
pip install langchain-qdrant qdrant-client   # AgentLab: langchain-qdrant 1.1.0, qdrant-client 1.20
pip install "langchain-qdrant[fastembed]"   # FastEmbedSparse(BM25 등) 사용 시
```

```python
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse, SparseEmbeddings, SparseVector
from qdrant_client import QdrantClient, models
```

## 시그니처

```python
QdrantVectorStore(
    client: QdrantClient,
    collection_name: str,
    embedding: Embeddings | None = None,
    retrieval_mode: RetrievalMode = RetrievalMode.DENSE,
    vector_name: str = "",
    content_payload_key: str = "page_content",
    metadata_payload_key: str = "metadata",
    distance: models.Distance = models.Distance.COSINE,
    sparse_embedding: SparseEmbeddings | None = None,
    sparse_vector_name: str = "langchain-sparse",
    validate_embeddings: bool = True,
    validate_collection_config: bool = True,
)

# 컬렉션 생성까지 해 주는 팩토리
QdrantVectorStore.from_documents(documents, embedding, **kwargs)
QdrantVectorStore.from_texts(
    texts, embedding=None, metadatas=None, ids=None, collection_name=None,
    location=None, url=None, port=6333, grpc_port=6334, prefer_grpc=False,
    https=None, api_key=None, prefix=None, timeout=None, host=None, path=None,
    distance=models.Distance.COSINE, retrieval_mode=RetrievalMode.DENSE,
    sparse_embedding=None, collection_create_options=None, vector_params=None,
    sparse_vector_params=None, batch_size=64, force_recreate=False, ...,
)
QdrantVectorStore.from_existing_collection(collection_name, embedding=None, retrieval_mode=..., url=None, api_key=None, path=None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `client` | `QdrantClient` | (필수) | `QdrantClient(":memory:")`, `QdrantClient(path="./qdrant_data")`, `QdrantClient(url=..., api_key=...)` |
| `collection_name` | `str` | (필수) | 컬렉션 이름. 생성자는 **이미 존재하는** 컬렉션을 요구 |
| `embedding` | `Embeddings \| None` | `None` | 밀집 임베딩. DENSE/HYBRID에서 필수 |
| `retrieval_mode` | `RetrievalMode` | `DENSE` | `DENSE`, `SPARSE`, `HYBRID` |
| `vector_name` | `str` | `""` | 명명된 벡터(named vector) 이름. `""`는 기본(이름 없는) 벡터 |
| `content_payload_key` | `str` | `"page_content"` | 본문을 저장할 페이로드 키 |
| `metadata_payload_key` | `str` | `"metadata"` | 메타데이터를 저장할 페이로드 키 (필터 키 접두사가 됨) |
| `distance` | `models.Distance` | `COSINE` | `COSINE`, `DOT`, `EUCLID`, `MANHATTAN` |
| `sparse_embedding` | `SparseEmbeddings \| None` | `None` | 희소 임베딩. SPARSE/HYBRID에서 필수 |
| `sparse_vector_name` | `str` | `"langchain-sparse"` | 희소 벡터 이름 |
| `validate_embeddings` | `bool` | `True` | 모드에 맞는 임베딩이 주어졌는지 검사 |
| `validate_collection_config` | `bool` | `True` | 컬렉션의 차원·거리·벡터 이름이 설정과 일치하는지 검사 |

`from_texts`/`from_documents` 전용 키워드:

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `location` | `str \| None` | `None` | `":memory:"` 또는 URL |
| `url` / `api_key` | `str \| None` | `None` | 원격 서버 / Qdrant Cloud |
| `path` | `str \| None` | `None` | 로컬 파일 모드 저장 경로 |
| `collection_name` | `str \| None` | `None` | 생략하면 UUID 이름으로 생성 |
| `force_recreate` | `bool` | `False` | 기존 컬렉션을 지우고 다시 생성 |
| `vector_params` / `sparse_vector_params` | `dict \| None` | `None` | `VectorParams`/`SparseVectorParams`에 전달할 추가 설정(HNSW, 양자화 등) |
| `batch_size` | `int` | `64` | 업서트 배치 크기 |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `add_documents(documents, ids=None)` / `add_texts(texts, metadatas=None, ids=None, batch_size=64)` | `list[str \| int]` | 업서트. ID는 **UUID 문자열 또는 부호 없는 정수**만 허용 |
| `similarity_search(query, k=4, filter=None, search_params=None, offset=0, score_threshold=None, consistency=None, hybrid_fusion=None)` | `list[Document]` | 검색 |
| `similarity_search_with_score(...)` | `list[tuple[Document, float]]` | 점수 = 유사도(COSINE/DOT은 클수록 유사) |
| `similarity_search_by_vector(embedding, k=4, filter=None, ...)` | `list[Document]` | 벡터로 직접 검색 |
| `max_marginal_relevance_search(query, k=4, fetch_k=20, lambda_mult=0.5, filter=None, ...)` | `list[Document]` | MMR |
| `get_by_ids(ids, /)` | `list[Document]` | ID 조회 |
| `delete(ids=None)` | `bool \| None` | ID로 삭제 |
| `as_retriever(search_type=..., search_kwargs=...)` | `VectorStoreRetriever` | `similarity`, `mmr`, `similarity_score_threshold` 모두 지원 |
| `.client` | `QdrantClient` | 원시 클라이언트 접근 (페이로드 인덱스, 스냅샷 등) |

반환 `Document.metadata`에는 원래 메타데이터 외에 `_id`, `_collection_name`이 추가됩니다.

## 예제

### `:memory:` + 페이로드 필터

```python
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
client = QdrantClient(":memory:")

# 생성자를 쓸 때는 컬렉션을 직접 만들어야 한다 (차원 = 임베딩 길이)
dim = len(embeddings.embed_query("dim check"))
client.create_collection(
    collection_name="docs",
    vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
)

store = QdrantVectorStore(client=client, collection_name="docs", embedding=embeddings)
store.add_documents(
    [
        Document(page_content="2024년 매출 보고서", metadata={"year": 2024, "dept": "finance"}),
        Document(page_content="2025년 매출 보고서", metadata={"year": 2025, "dept": "finance"}),
        Document(page_content="2025년 채용 계획", metadata={"year": 2025, "dept": "hr"}),
    ]
)

# 메타데이터는 metadata_payload_key("metadata") 아래에 중첩 저장된다
flt = models.Filter(
    must=[
        models.FieldCondition(key="metadata.dept", match=models.MatchValue(value="finance")),
        models.FieldCondition(key="metadata.year", range=models.Range(gte=2025)),
    ]
)
for doc, score in store.similarity_search_with_score("매출", k=3, filter=flt):
    print(f"{score:.3f}", doc.page_content, doc.metadata)
```

`models.Filter`는 `must`(AND), `should`(OR), `must_not`(NOT)을 조합합니다. 조건: `MatchValue`, `MatchAny(any=[...])`, `MatchText`, `Range`, `DatetimeRange`, `IsEmptyCondition`, `HasIdCondition` 등.

### 하이브리드 검색 (dense + sparse, RRF)

```python
import hashlib

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, SparseEmbeddings, SparseVector


class ToySparse(SparseEmbeddings):
    """학습용 희소 임베딩: 공백 토큰을 해시해 인덱스로 쓴다 (실서비스는 FastEmbedSparse)."""

    def _encode(self, text: str) -> SparseVector:
        counts: dict[int, float] = {}
        for tok in text.lower().split():
            idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % 100_000
            counts[idx] = counts.get(idx, 0.0) + 1.0
        return SparseVector(indices=list(counts), values=list(counts.values()))

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._encode(t) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._encode(text)


store = QdrantVectorStore.from_documents(
    [Document(page_content=t) for t in ["에러 코드 E1234 해결법", "배포 가이드", "E1234 로그 분석"]],
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    sparse_embedding=ToySparse(),
    retrieval_mode=RetrievalMode.HYBRID,  # dense + sparse → 기본 RRF 융합
    location=":memory:",
    collection_name="hybrid_docs",
)
for d in store.similarity_search("e1234", k=2):
    print(d.page_content)
```

실서비스에서는 `FastEmbedSparse(model_name="Qdrant/bm25")`를 씁니다(`fastembed` 패키지 필요, AgentLab에는 미설치). 융합 방식은 `hybrid_fusion=models.FusionQuery(fusion=models.Fusion.DBSF)`처럼 바꿀 수 있습니다.

### 프로덕션 연결

```python
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings

store = QdrantVectorStore.from_existing_collection(
    collection_name="docs",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    url="https://<cluster>.cloud.qdrant.io",
    api_key="...",          # 환경변수에서 읽으세요
)
# 자주 필터링하는 필드에는 페이로드 인덱스 생성
store.client.create_payload_index("docs", field_name="metadata.dept", field_schema="keyword")
```

## 주의사항

> [!WARNING]
> 생성자 `QdrantVectorStore(client=..., collection_name=...)`는 컬렉션을 **만들지 않습니다.** 없는 컬렉션이면 오류가 납니다. 처음 만들 때는 `client.create_collection(...)`을 먼저 호출하거나 `from_documents`/`from_texts`를 쓰세요.

> [!WARNING]
> 필터 키는 `"dept"`가 아니라 **`"metadata.dept"`** 입니다. LangChain이 메타데이터를 `metadata` 페이로드 키 아래에 중첩 저장하기 때문입니다. 접두사를 빼면 오류 없이 결과가 0건이 됩니다.

> [!WARNING]
> 포인트 ID는 UUID 또는 정수여야 합니다. `"doc-1"` 같은 임의 문자열은 거부되므로 `uuid.uuid5(NAMESPACE, key)`로 결정적 UUID를 만드세요.

> [!TIP]
> `QdrantClient(":memory:")`와 `path=` 로컬 모드는 개발용입니다. 동시 접근·대용량은 서버(Docker `qdrant/qdrant`)나 Qdrant Cloud를 쓰세요. 로컬 모드는 한 프로세스만 같은 경로를 열 수 있습니다.

> [!NOTE]
> `langchain_qdrant.Qdrant`는 구버전 클래스입니다. 새 코드에서는 `QdrantVectorStore`를 쓰세요.

## 관련 문서

- [벡터 검색 핵심 개념](/docs/vector-db/01-concepts)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [리트리버](/docs/langchain/15-retrievers)
- [공식 문서: LangChain Qdrant](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)
- [Qdrant 필터링 문서](https://qdrant.tech/documentation/concepts/filtering/)
