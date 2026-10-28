---
title: "Milvus"
description: "대규모 분산 벡터 DB Milvus(및 Zilliz Cloud)와 langchain-milvus의 Milvus 클래스"
order: 9
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/milvus"
tags: [vector-db, milvus, zilliz]
---

# Milvus

Milvus는 수억~수십억 벡터 규모를 겨냥한 오픈소스 분산 벡터 DB입니다. HNSW, IVF 계열, DiskANN, GPU 인덱스 등 다양한 인덱스를 지원합니다. 배포 형태는 **Milvus Lite**(파이썬 내장, 로컬 `.db` 파일), Standalone(Docker), Distributed(Kubernetes), 관리형 Zilliz Cloud가 있습니다.

> [!NOTE]
> `langchain-milvus`는 AgentLab 샌드박스에 **설치되어 있지 않습니다.** 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/milvus)를 확인하세요.

## Import

```bash
pip install langchain-milvus   # pymilvus 포함 (Milvus Lite는 로컬 파일 URI로 사용)
```

```python
from langchain_milvus import Milvus
```

## 시그니처

```python
Milvus(
    embedding_function,                 # Embeddings
    collection_name: str = "LangChainCollection",
    connection_args: dict | None = None,    # {"uri": ..., "token": ...}
    index_params: dict | None = None,       # {"index_type": "HNSW", "metric_type": "COSINE", ...}
    drop_old: bool = False,
    auto_id: bool = False,
    ...
)
Milvus.from_documents(documents, embedding, collection_name=..., connection_args=..., ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `embedding_function` | `Embeddings` | (필수) | 임베딩 객체 |
| `collection_name` | `str` | `"LangChainCollection"` | 컬렉션 이름 |
| `connection_args` | `dict` | `None` | `{"uri": "./milvus.db"}`(Lite), `{"uri": "http://localhost:19530"}`, Zilliz는 `uri`+`token` |
| `index_params` | `dict \| None` | `None` | 인덱스 종류와 메트릭 (`L2`, `IP`, `COSINE`) |
| `drop_old` | `bool` | `False` | 기존 컬렉션 삭제 후 재생성 |
| `auto_id` | `bool` | `False` | 기본 키 자동 생성 |

## 메서드와 반환값

표준 인터페이스(`add_documents`, `similarity_search`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete`, `as_retriever`)를 따릅니다. 메타데이터 필터는 Milvus **불리언 표현식 문자열**을 `expr=`로 넘깁니다.

```text
category == "billing" and year >= 2025
source in ["a.pdf", "b.pdf"]
```

## 예제

```python
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_openai import OpenAIEmbeddings

store = Milvus(
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    collection_name="kb_docs",
    connection_args={"uri": "./milvus_demo.db"},   # Milvus Lite
    index_params={"index_type": "HNSW", "metric_type": "COSINE"},
    auto_id=True,
)
store.add_documents([Document(page_content="환불 정책", metadata={"category": "billing"})])
docs = store.similarity_search("환불", k=3, expr='category == "billing"')
```

## 주의사항

> [!WARNING]
> Milvus는 스키마가 있는 DB입니다. 첫 삽입 때 메타데이터 필드로 스키마가 정해지므로, 나중에 새 메타데이터 키를 추가하면 오류가 나거나 무시될 수 있습니다. 필요하면 동적 필드(`enable_dynamic_field=True`)를 검토하세요.

> [!TIP]
> 하이브리드 검색은 dense 필드와 sparse(BM25) 필드를 함께 두는 방식으로 지원됩니다(`langchain_milvus`의 `BM25BuiltInFunction` 등). 버전에 따라 API가 바뀌어 왔으니 공식 문서의 하이브리드 예제를 따르세요.

## 관련 문서

- [벡터 검색 핵심 개념 — 인덱스 유형](/docs/vector-db/01-concepts)
- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [공식 문서: LangChain Milvus](https://docs.langchain.com/oss/python/integrations/vectorstores/milvus)
- [Milvus 필터 표현식](https://milvus.io/docs/boolean.md)
