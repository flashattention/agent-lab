---
title: "Elasticsearch"
description: "BM25 전문 검색 엔진에 kNN 벡터 검색을 결합하는 ElasticsearchStore"
order: 10
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/elasticsearch"
tags: [vector-db, elasticsearch, hybrid-search, bm25]
---

# Elasticsearch

Elasticsearch는 전통적인 전문 검색(BM25) 엔진이며 `dense_vector` 필드와 kNN(HNSW) 검색을 지원합니다. 이미 ES로 로그·문서 검색을 운영하고 있다면 벡터 검색을 같은 클러스터에 추가할 수 있고, BM25와 kNN을 RRF로 섞는 하이브리드 검색이 강점입니다. LangChain 연동은 `langchain-elasticsearch`입니다.

> [!NOTE]
> `langchain-elasticsearch`는 AgentLab 샌드박스에 **설치되어 있지 않습니다.** 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/elasticsearch)를 확인하세요.

## Import

```bash
pip install langchain-elasticsearch
```

```python
from langchain_elasticsearch import ElasticsearchStore, DenseVectorStrategy, BM25Strategy
```

## 시그니처

```python
ElasticsearchStore(
    index_name: str,
    embedding=None,               # Embeddings
    es_url: str | None = None,    # "http://localhost:9200"
    es_cloud_id: str | None = None,
    es_api_key: str | None = None,
    es_user: str | None = None,
    es_password: str | None = None,
    strategy=DenseVectorStrategy(),   # 검색 전략
    ...
)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `index_name` | `str` | (필수) | ES 인덱스 이름 |
| `embedding` | `Embeddings \| None` | `None` | 임베딩 객체 (BM25 전략에서는 불필요) |
| `es_url` / `es_cloud_id` | `str \| None` | `None` | 셀프호스트 URL 또는 Elastic Cloud ID |
| `es_api_key` / `es_user` / `es_password` | `str \| None` | `None` | 인증 |
| `strategy` | 전략 객체 | `DenseVectorStrategy()` | `DenseVectorStrategy(hybrid=True)`, `SparseVectorStrategy()`(ELSER), `BM25Strategy()`, `DenseVectorScriptScoreStrategy()`(정확 검색) |

## 메서드와 반환값

표준 인터페이스(`add_documents`, `similarity_search`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete`, `as_retriever`)를 따릅니다. `filter=`에는 **Elasticsearch Query DSL 절의 리스트**를 넘깁니다. 메타데이터는 `metadata.*` 필드에 저장됩니다.

## 예제

```python
from langchain_core.documents import Document
from langchain_elasticsearch import DenseVectorStrategy, ElasticsearchStore
from langchain_openai import OpenAIEmbeddings

store = ElasticsearchStore(
    index_name="kb-docs",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    es_url="http://localhost:9200",
    strategy=DenseVectorStrategy(hybrid=True),  # BM25 + kNN, RRF 융합
)
store.add_documents([Document(page_content="에러 코드 E1234 해결법", metadata={"source": "runbook.md"})])
docs = store.similarity_search(
    "E1234",
    k=3,
    filter=[{"term": {"metadata.source.keyword": "runbook.md"}}],
)
```

## 주의사항

> [!WARNING]
> 문자열 메타데이터는 동적 매핑으로 `text` + `.keyword` 서브필드가 됩니다. 정확 일치 `term` 필터는 `metadata.source`가 아니라 `metadata.source.keyword`에 걸어야 합니다.

> [!WARNING]
> `hybrid=True`의 RRF는 Elasticsearch 라이선스/버전에 따라 사용 가능 여부가 다를 수 있습니다. 운영 클러스터의 버전과 구독 등급을 확인하세요.

## 관련 문서

- [벡터 검색 핵심 개념 — 하이브리드 검색](/docs/vector-db/01-concepts)
- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [공식 문서: LangChain Elasticsearch](https://docs.langchain.com/oss/python/integrations/vectorstores/elasticsearch)
- [Elasticsearch kNN 검색](https://www.elastic.co/docs/solutions/search/vector/knn)
