---
title: "MongoDB Atlas Vector Search"
description: "MongoDB Atlas의 $vectorSearch를 쓰는 langchain-mongodb의 MongoDBAtlasVectorSearch"
order: 11
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/mongodb_atlas"
tags: [vector-db, mongodb, atlas]
---

# MongoDB Atlas Vector Search

MongoDB Atlas는 컬렉션 문서에 임베딩 필드를 두고 **Atlas Vector Search 인덱스**와 `$vectorSearch` 집계 단계로 검색합니다. 운영 데이터가 이미 MongoDB에 있다면 별도 벡터 DB 없이 같은 문서에 벡터를 저장할 수 있습니다. LangChain 연동은 `langchain-mongodb`입니다.

> [!NOTE]
> `langchain-mongodb`는 AgentLab 샌드박스에 **설치되어 있지 않고**, Atlas 클러스터(또는 Atlas 로컬 배포)가 필요합니다. 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/mongodb_atlas)를 확인하세요.

## Import

```bash
pip install langchain-mongodb pymongo
```

```python
from langchain_mongodb import MongoDBAtlasVectorSearch
```

## 시그니처

```python
MongoDBAtlasVectorSearch(
    collection,                       # pymongo Collection
    embedding,                        # Embeddings
    index_name: str = "vector_index",
    text_key: str = "text",
    embedding_key: str = "embedding",
    relevance_score_fn: str = "cosine",
    ...
)
MongoDBAtlasVectorSearch.from_connection_string(connection_string, namespace="db.collection", embedding=..., index_name=...)
store.create_vector_search_index(dimensions: int, filters: list[str] | None = None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `collection` | `pymongo.collection.Collection` | (필수) | `MongoClient(uri)["db"]["coll"]` |
| `embedding` | `Embeddings` | (필수) | 임베딩 객체 |
| `index_name` | `str` | `"vector_index"` | Atlas Vector Search 인덱스 이름 |
| `text_key` | `str` | `"text"` | 본문 필드 |
| `embedding_key` | `str` | `"embedding"` | 벡터 필드 |
| `relevance_score_fn` | `str` | `"cosine"` | 인덱스의 similarity와 일치시켜야 함 (`cosine`, `euclidean`, `dotProduct`) |

## 메서드와 반환값

표준 인터페이스를 따르며, 필터는 `pre_filter=`(MQL 딕셔너리)로 넘깁니다. 필터에 쓰는 필드는 **인덱스 정의에 `filter` 타입으로 등록**되어 있어야 합니다. 하이브리드 검색은 `langchain_mongodb.retrievers`의 `MongoDBAtlasHybridSearchRetriever`(Atlas Search 전문 인덱스 필요)를 씁니다.

## 예제

```python
import os

from langchain_core.documents import Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_openai import OpenAIEmbeddings

store = MongoDBAtlasVectorSearch.from_connection_string(
    connection_string=os.environ["MONGODB_URI"],
    namespace="agentlab.docs",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    index_name="vector_index",
)
store.create_vector_search_index(dimensions=1536, filters=["category"])  # 한 번만

store.add_documents([Document(page_content="환불 정책", metadata={"category": "billing"})])
docs = store.similarity_search("환불", k=3, pre_filter={"category": {"$eq": "billing"}})
```

## 주의사항

> [!WARNING]
> Atlas 검색 인덱스는 **비동기로 빌드**됩니다. 인덱스 생성·문서 삽입 직후에는 검색 결과가 비어 있을 수 있습니다.

> [!WARNING]
> 인덱스에 `filter`로 등록하지 않은 필드를 `pre_filter`에 쓰면 오류가 납니다. 필터 필드를 추가하려면 인덱스 정의를 갱신하세요.

## 관련 문서

- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [리트리버](/docs/langchain/15-retrievers)
- [공식 문서: LangChain MongoDB Atlas](https://docs.langchain.com/oss/python/integrations/vectorstores/mongodb_atlas)
- [Atlas Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
