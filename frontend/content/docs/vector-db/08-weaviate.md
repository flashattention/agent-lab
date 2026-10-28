---
title: "Weaviate"
description: "BM25+벡터 하이브리드 검색을 내장한 오픈소스 벡터 DB Weaviate와 WeaviateVectorStore"
order: 8
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/weaviate"
tags: [vector-db, weaviate, hybrid-search]
---

# Weaviate

Weaviate는 오픈소스 벡터 DB로, **BM25 키워드 검색과 벡터 검색을 결합한 하이브리드 검색**을 기본 제공합니다. 셀프호스트(Docker/Kubernetes)나 Weaviate Cloud로 운영합니다. LangChain 연동은 `langchain-weaviate`이며 Weaviate Python 클라이언트 **v4** 기준입니다.

> [!NOTE]
> `langchain-weaviate`는 AgentLab 샌드박스에 **설치되어 있지 않습니다.** 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/weaviate)를 확인하세요.

## Import

```bash
pip install langchain-weaviate   # weaviate-client v4 포함
```

```python
import weaviate
from langchain_weaviate import WeaviateVectorStore
```

## 시그니처

```python
WeaviateVectorStore(
    client,                 # weaviate.WeaviateClient (v4)
    index_name: str,        # 컬렉션 이름 (대문자로 시작)
    text_key: str,          # 본문 속성 이름
    embedding=None,         # Embeddings
    ...
)
WeaviateVectorStore.from_documents(documents, embedding, client=client, index_name=None, ...)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `client` | `weaviate.WeaviateClient` | (필수) | `weaviate.connect_to_local()`, `weaviate.connect_to_weaviate_cloud(...)` |
| `index_name` | `str` | (필수) | Weaviate 컬렉션 이름 |
| `text_key` | `str` | (필수) | `page_content`를 저장할 속성 |
| `embedding` | `Embeddings \| None` | `None` | LangChain 쪽에서 임베딩을 계산할 때 지정 |

## 메서드와 반환값

표준 인터페이스(`add_documents`, `similarity_search`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete`, `as_retriever`)를 따릅니다. `similarity_search`는 내부적으로 **하이브리드 쿼리**를 실행하며 `alpha`로 비중을 조절합니다.

| 키워드 | 설명 |
|---|---|
| `alpha` | `0` = 순수 BM25, `1` = 순수 벡터, 그 사이 = 가중 결합 |
| `filters` | `weaviate.classes.query.Filter` 객체 |
| `tenant` | 멀티테넌시가 켜진 컬렉션의 테넌트 이름 |

## 예제

```python
import weaviate
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.classes.query import Filter

client = weaviate.connect_to_local()  # docker로 띄운 localhost:8080
try:
    store = WeaviateVectorStore.from_documents(
        [Document(page_content="에러 코드 E1234 해결법", metadata={"category": "ops"})],
        OpenAIEmbeddings(model="text-embedding-3-small"),
        client=client,
    )
    docs = store.similarity_search(
        "E1234",
        k=3,
        alpha=0.5,  # 키워드와 벡터를 반반
        filters=Filter.by_property("category").equal("ops"),
    )
finally:
    client.close()
```

## 주의사항

> [!WARNING]
> v4 클라이언트는 연결을 명시적으로 닫아야 합니다(`client.close()` 또는 `with weaviate.connect_to_local() as client:`). 닫지 않으면 리소스 경고가 납니다. v3 클라이언트(`weaviate.Client`) 예제는 더 이상 동작하지 않습니다.

> [!TIP]
> 고유명사·코드가 많은 문서는 `alpha`를 0.3~0.5 정도로 낮춰 키워드 비중을 높여 보고, 평가 셋으로 비교하세요.

## 관련 문서

- [벡터 검색 핵심 개념 — 하이브리드 검색](/docs/vector-db/01-concepts)
- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [공식 문서: LangChain Weaviate](https://docs.langchain.com/oss/python/integrations/vectorstores/weaviate)
- [Weaviate 하이브리드 검색](https://docs.weaviate.io/weaviate/search/hybrid)
