---
title: "Redis"
description: "Redis 검색 기능으로 벡터를 저장·검색하는 langchain-redis의 RedisVectorStore"
order: 12
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/redis"
tags: [vector-db, redis, low-latency]
---

# Redis

Redis는 검색 모듈(Redis Stack, Redis 8 이상에 내장된 Query Engine)로 HNSW/FLAT 벡터 인덱스와 tag·numeric·text 필터를 지원합니다. 캐시·세션 저장소로 이미 Redis를 쓰고 있다면 낮은 지연의 벡터 검색을 같은 인프라에 올릴 수 있습니다. LangChain 연동은 `langchain-redis`이며 내부적으로 [RedisVL](https://docs.redisvl.com/)을 사용합니다.

> [!NOTE]
> `langchain-redis`는 AgentLab 샌드박스에 **설치되어 있지 않습니다.** 아래 코드는 참고용이며 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/redis)를 확인하세요.

## Import

```bash
pip install langchain-redis
# 로컬 서버: docker run -p 6379:6379 redis:8   (또는 redis/redis-stack)
```

```python
from langchain_redis import RedisConfig, RedisVectorStore
```

## 시그니처

```python
RedisVectorStore(
    embeddings,                      # Embeddings
    config: RedisConfig | None = None,
    **kwargs,                        # index_name=, redis_url=, metadata_schema= 등을 직접 넘길 수도 있음
)

RedisConfig(
    index_name: str = ...,
    redis_url: str = "redis://localhost:6379",
    metadata_schema: list[dict] | None = None,   # [{"name": "category", "type": "tag"}, ...]
    distance_metric: str = "COSINE",
    ...
)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `embeddings` | `Embeddings` | (필수) | 임베딩 객체 |
| `config.index_name` | `str` | 자동 | 검색 인덱스 이름 (키 접두사로도 사용) |
| `config.redis_url` | `str` | `"redis://localhost:6379"` | 연결 URL |
| `config.metadata_schema` | `list[dict]` | `None` | 필터에 쓸 메타데이터 필드와 타입(`tag`, `numeric`, `text`) |
| `config.distance_metric` | `str` | `"COSINE"` | `COSINE`, `IP`, `L2` |

## 메서드와 반환값

표준 인터페이스(`add_documents`, `similarity_search`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete`, `as_retriever`)를 따릅니다. 필터는 RedisVL 필터 표현식 객체(`Tag`, `Num`, `Text`)를 `&`, `|`로 조합해 `filter=`로 넘깁니다.

## 예제

```python
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_redis import RedisConfig, RedisVectorStore
from redisvl.query.filter import Num, Tag

config = RedisConfig(
    index_name="kb_docs",
    redis_url="redis://localhost:6379",
    metadata_schema=[
        {"name": "category", "type": "tag"},
        {"name": "year", "type": "numeric"},
    ],
)
store = RedisVectorStore(OpenAIEmbeddings(model="text-embedding-3-small"), config=config)
store.add_documents([Document(page_content="환불 정책", metadata={"category": "billing", "year": 2025})])

flt = (Tag("category") == "billing") & (Num("year") >= 2025)
docs = store.similarity_search("환불", k=3, filter=flt)
```

## 주의사항

> [!WARNING]
> `metadata_schema`에 선언하지 않은 메타데이터 필드로는 필터링할 수 없습니다. 인덱스 스키마는 생성 시점에 정해지므로, 필드를 추가하려면 인덱스를 다시 만들어야 합니다.

> [!WARNING]
> Redis는 기본적으로 데이터를 메모리에 둡니다. 대용량 벡터는 메모리 비용이 크므로 RDB/AOF 영속 설정과 메모리 한도를 함께 계획하세요.

> [!TIP]
> `langchain-redis`는 벡터 스토어 외에 LLM 시맨틱 캐시(`RedisSemanticCache`)와 대화 기록 저장소도 제공합니다.

## 관련 문서

- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [공식 문서: LangChain Redis](https://docs.langchain.com/oss/python/integrations/vectorstores/redis)
- [RedisVL 문서](https://docs.redisvl.com/)
