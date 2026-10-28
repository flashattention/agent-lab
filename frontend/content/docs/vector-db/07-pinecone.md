---
title: "Pinecone"
description: "완전 관리형 서버리스 벡터 DB Pinecone과 langchain-pinecone의 PineconeVectorStore"
order: 7
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/pinecone"
tags: [vector-db, pinecone, managed]
---

# Pinecone

Pinecone은 완전 관리형(Fully managed) 벡터 DB SaaS입니다. 인프라 운영 없이 인덱스(Index)를 만들고, 네임스페이스(Namespace)로 테넌트를 분리하며, 메타데이터 필터와 sparse-dense 하이브리드 검색을 제공합니다.

> [!NOTE]
> `langchain-pinecone`은 AgentLab 샌드박스에 **설치되어 있지 않고**, 클라우드 계정과 API 키가 필요합니다. 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/pinecone)를 확인하세요.

## Import

```bash
pip install langchain-pinecone   # pinecone SDK 포함
export PINECONE_API_KEY=...
```

```python
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
```

## 시그니처

```python
PineconeVectorStore(
    index=None,            # pinecone Index 객체
    embedding=None,        # Embeddings
    text_key="text",       # 본문을 저장할 메타데이터 키
    namespace=None,        # 기본 네임스페이스
    index_name=None,       # index 대신 이름으로 지정 가능
    ...
)
PineconeVectorStore.from_documents(documents, embedding, index_name=..., namespace=None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `index` | `pinecone.Index` | `None` | `pc.Index("name")`으로 얻은 인덱스 |
| `embedding` | `Embeddings` | `None` | 임베딩 객체. 차원이 인덱스 `dimension`과 같아야 함 |
| `text_key` | `str` | `"text"` | `page_content`가 저장되는 메타데이터 키 |
| `namespace` | `str \| None` | `None` | 테넌트·데이터셋 분리 단위 |
| `index_name` | `str \| None` | `None` | 인덱스 이름 (환경변수 `PINECONE_API_KEY` 사용) |

## 메서드와 반환값

표준 인터페이스: `add_documents(documents, ids=None, namespace=None)`, `similarity_search(query, k=4, filter=None, namespace=None)`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete(ids=None, delete_all=None, namespace=None, filter=None)`, `as_retriever`.

필터 연산자: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`, `$and`, `$or`.

## 예제

```python
import os

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
if not pc.has_index("agentlab-docs"):
    pc.create_index(
        name="agentlab-docs",
        dimension=1536,                       # text-embedding-3-small
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

store = PineconeVectorStore(
    index=pc.Index("agentlab-docs"),
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
store.add_documents(
    [Document(page_content="환불 정책", metadata={"category": "billing"})],
    namespace="tenant-a",
)
docs = store.similarity_search(
    "환불", k=3, filter={"category": {"$eq": "billing"}}, namespace="tenant-a"
)
```

## 주의사항

> [!WARNING]
> 인덱스의 `dimension`과 `metric`은 생성 후 바꿀 수 없습니다. 임베딩 모델을 바꾸면 새 인덱스를 만드세요.

> [!WARNING]
> Pinecone은 쓰기 후 검색에 반영되기까지 짧은 지연이 있을 수 있습니다(eventual consistency). 업서트 직후 검색하는 테스트는 간헐적으로 실패할 수 있습니다.

> [!TIP]
> 멀티테넌시는 메타데이터 필터보다 **네임스페이스**가 격리·삭제 측면에서 단순합니다. 네임스페이스 단위로 한 번에 삭제할 수 있습니다.

## 관련 문서

- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [공식 문서: LangChain Pinecone](https://docs.langchain.com/oss/python/integrations/vectorstores/pinecone)
- [Pinecone 메타데이터 필터](https://docs.pinecone.io/guides/search/filter-by-metadata)
