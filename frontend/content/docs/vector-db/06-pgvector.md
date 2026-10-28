---
title: "pgvector (langchain-postgres)"
description: "PostgreSQL pgvector 확장을 쓰는 PGVector와 신형 PGVectorStore/PGEngine"
order: 6
source: "https://docs.langchain.com/oss/python/integrations/vectorstores/pgvectorstore"
tags: [vector-db, pgvector, postgres]
---

# pgvector (langchain-postgres)

[pgvector](https://github.com/pgvector/pgvector)는 PostgreSQL에 `vector` 타입과 HNSW·IVFFlat 인덱스를 추가하는 확장입니다. 이미 Postgres를 운영 중이라면 별도 벡터 DB 없이 트랜잭션, 조인, 백업 체계를 그대로 쓸 수 있습니다. LangChain 연동은 `langchain-postgres` 패키지가 담당하며 클래스가 두 개입니다.

| 클래스 | 테이블 구조 | 상태 |
|---|---|---|
| `PGVectorStore` (+ `PGEngine`) | 사용자가 지정한 테이블. 메타데이터를 **실제 컬럼**으로 둘 수 있음 | 권장 (신규 프로젝트) |
| `PGVector` | `langchain_pg_collection` / `langchain_pg_embedding` 고정 테이블, 메타데이터는 JSONB | 구형. 마이그레이션 권장 |

> [!NOTE]
> `langchain-postgres`는 AgentLab 샌드박스에 **설치되어 있지 않고**, 실행 예제에서는 Postgres 같은 외부 서비스를 쓰지 않습니다. 아래 코드는 본문 참고용이며, 정확한 최신 시그니처는 [공식 문서](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvectorstore)를 확인하세요.

## Import

```bash
pip install langchain-postgres "psycopg[binary]"
# DB 쪽: CREATE EXTENSION IF NOT EXISTS vector;
```

```python
from langchain_postgres import PGEngine, PGVectorStore   # 권장
from langchain_postgres import PGVector                  # 구형
```

## 시그니처

```python
# 1) 연결 엔진
engine = PGEngine.from_connection_string(url="postgresql+psycopg://user:pw@host:5432/db")

# 2) 테이블 생성 (한 번만)
engine.init_vectorstore_table(
    table_name: str,
    vector_size: int,
    metadata_columns: list[Column] = [],   # 필터에 쓸 실제 컬럼
    ...
)

# 3) 스토어 생성
PGVectorStore.create_sync(engine, table_name: str, embedding_service: Embeddings, metadata_columns: list[str] = [], ...)
await PGVectorStore.create(engine, table_name, embedding_service, ...)   # 비동기
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `url` | `str` | (필수) | SQLAlchemy URL. 드라이버는 `postgresql+psycopg://`(psycopg 3) |
| `table_name` | `str` | (필수) | 벡터를 저장할 테이블 |
| `vector_size` | `int` | (필수) | 임베딩 차원. `text-embedding-3-small`은 1536 |
| `metadata_columns` | `list[Column]` / `list[str]` | `[]` | 메타데이터를 별도 컬럼으로 저장해 필터·인덱스에 활용 |
| `embedding_service` | `Embeddings` | (필수) | 임베딩 객체 |

구형 `PGVector(embeddings=..., collection_name=..., connection=..., use_jsonb=True)`는 컬렉션 이름으로 데이터를 구분합니다.

## 메서드와 반환값

표준 [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)를 따릅니다: `add_documents`, `similarity_search(query, k, filter=...)`, `similarity_search_with_score`, `max_marginal_relevance_search`, `delete(ids)`, `get_by_ids`, `as_retriever`, 그리고 `a`-접두 비동기 버전.

필터는 MongoDB 스타일 딕셔너리입니다: `$eq`, `$ne`, `$lt`, `$lte`, `$gt`, `$gte`, `$in`, `$nin`, `$between`, `$like`, `$ilike`, `$exists`, `$and`, `$or`, `$not`.

## 예제

```python
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import Column, PGEngine, PGVectorStore

engine = PGEngine.from_connection_string(url="postgresql+psycopg://lab:lab@localhost:5432/lab")
engine.init_vectorstore_table(
    table_name="docs",
    vector_size=1536,
    metadata_columns=[Column("category", "TEXT")],
)

store = PGVectorStore.create_sync(
    engine=engine,
    table_name="docs",
    embedding_service=OpenAIEmbeddings(model="text-embedding-3-small"),
    metadata_columns=["category"],
)
store.add_documents([Document(page_content="환불 정책", metadata={"category": "billing"})])
docs = store.similarity_search("환불", k=3, filter={"category": {"$eq": "billing"}})
```

## 주의사항

> [!WARNING]
> 데이터가 늘면 반드시 ANN 인덱스를 만드세요. 인덱스가 없으면 pgvector는 순차 스캔(전수 비교)을 합니다. HNSW가 일반적인 선택이며 `PGVectorStore`는 `apply_vector_index(...)`로 인덱스를 만들 수 있습니다(SQL로 `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`도 가능).

> [!WARNING]
> 드라이버는 psycopg 3(`postgresql+psycopg://`)입니다. `psycopg2` URL을 넣으면 연결에 실패합니다.

> [!TIP]
> 자주 필터링하는 메타데이터는 JSONB가 아니라 `metadata_columns`로 실제 컬럼에 두면 B-tree 인덱스를 걸 수 있어 필터 성능이 좋아집니다.

## 관련 문서

- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [체크포인터 (PostgresSaver)](/docs/langgraph/09-checkpointers) — 같은 Postgres를 에이전트 상태 저장에도 사용 가능
- [공식 문서: PGVectorStore](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvectorstore)
- [langchain-postgres GitHub](https://github.com/langchain-ai/langchain-postgres)
