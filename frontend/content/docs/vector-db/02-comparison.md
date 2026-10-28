---
title: "벡터 DB 비교"
description: "주요 벡터 DB의 호스팅 방식, 오픈소스 여부, 하이브리드·필터 지원, LangChain 패키지를 한눈에 비교"
order: 2
source: "https://docs.langchain.com/oss/python/integrations/vectorstores"
tags: [vector-db, comparison]
---

# 벡터 DB 비교

LangChain의 벡터 스토어는 모두 같은 [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)(`add_documents`, `similarity_search`, `as_retriever` …)를 구현하므로, **애플리케이션 코드는 거의 그대로 두고 DB만 교체**할 수 있습니다. 차이는 운영 방식, 필터 문법, 하이브리드 검색 지원에 있습니다.

> [!NOTE]
> 아래 표는 2026년 10월 기준 각 DB의 공식 문서에 근거한 **기능 요약**이며 성능 수치는 싣지 않습니다. 성능은 데이터·하드웨어·설정에 따라 크게 달라지므로 자신의 데이터로 측정하세요. 기능은 버전마다 빠르게 바뀌니 최종 결정 전에 공식 문서를 확인하세요.

## 비교표

| DB | 배포 형태 | 오픈소스 | 하이브리드 (dense+sparse) | 메타데이터 필터 | LangChain 패키지 / 클래스 | AgentLab 설치 |
|---|---|---|---|---|---|---|
| InMemoryVectorStore | 프로세스 메모리 | ✅ (langchain-core) | ❌ | Python 함수 | `langchain_core.vectorstores.InMemoryVectorStore` | ✅ |
| Qdrant | 셀프호스트 / Qdrant Cloud / 로컬(`:memory:`, 파일) | ✅ Apache-2.0 | ✅ (`RetrievalMode.HYBRID`) | ✅ 강력 (`models.Filter`) | `langchain-qdrant` / `QdrantVectorStore` | ✅ |
| Chroma | 임베디드 / 서버 / Chroma Cloud | ✅ Apache-2.0 | ⚠️ Search API(`hybrid_search`) 기반, 배포 형태에 따라 다름 | ✅ (`where`, `where_document`) | `langchain-chroma` / `Chroma` | ✅ |
| pgvector | PostgreSQL 확장 (셀프호스트, RDS/Cloud SQL/Supabase 등) | ✅ | ⚠️ Postgres 전문 검색(tsvector)과 직접 조합 | ✅ (SQL / JSONB) | `langchain-postgres` / `PGVector`, `PGVectorStore` | ❌ |
| Pinecone | 완전 관리형 SaaS (서버리스) | ❌ | ✅ (sparse-dense) | ✅ (`$eq`, `$in` 등) | `langchain-pinecone` / `PineconeVectorStore` | ❌ |
| Weaviate | 셀프호스트 / Weaviate Cloud | ✅ BSD-3 | ✅ (BM25 + vector, `alpha`) | ✅ | `langchain-weaviate` / `WeaviateVectorStore` | ❌ |
| Milvus / Zilliz | 셀프호스트(Lite/Standalone/Distributed) / Zilliz Cloud | ✅ Apache-2.0 | ✅ (다중 벡터 필드, BM25 함수) | ✅ (불리언 표현식) | `langchain-milvus` / `Milvus` | ❌ |
| Elasticsearch | 셀프호스트 / Elastic Cloud | ⚠️ 라이선스 혼합(AGPL/SSPL/Elastic) | ✅ (BM25 + kNN, RRF) | ✅ (Query DSL) | `langchain-elasticsearch` / `ElasticsearchStore` | ❌ |
| MongoDB Atlas | Atlas 관리형 (Atlas Vector Search) | ❌ (서비스) | ✅ (`$vectorSearch` + Atlas Search) | ✅ (pre-filter, 필드 인덱싱 필요) | `langchain-mongodb` / `MongoDBAtlasVectorSearch` | ❌ |
| Redis | Redis Stack / Redis 8+ / Redis Cloud | ⚠️ 버전별 라이선스 상이 | ⚠️ 텍스트 필드 + 벡터 조합 | ✅ (tag/numeric/text 필터) | `langchain-redis` / `RedisVectorStore` | ❌ |
| FAISS | 라이브러리 (서버 아님) | ✅ MIT | ❌ | ❌ (래퍼에서 사후 필터) | `langchain_community` / `FAISS` (이 프로젝트에서는 사용 금지) | ❌ |

## 선택 가이드

| 상황 | 추천 |
|---|---|
| 학습, 단위 테스트, 수천 건 이하 프로토타입 | [InMemoryVectorStore](/docs/vector-db/03-in-memory) |
| 로컬 개발 → 그대로 프로덕션, 강력한 필터와 하이브리드가 필요 | [Qdrant](/docs/vector-db/04-qdrant) |
| 가장 간단한 임베디드 DB, 노트북·데스크톱 앱 | [Chroma](/docs/vector-db/05-chroma) |
| 이미 PostgreSQL을 운영 중, 트랜잭션·조인과 함께 쓰고 싶음 | [pgvector](/docs/vector-db/06-pgvector) |
| 인프라 운영 없이 관리형 서버리스 | [Pinecone](/docs/vector-db/07-pinecone) |
| 하이브리드 검색과 모듈(벡터라이저)을 DB에서 처리 | [Weaviate](/docs/vector-db/08-weaviate) |
| 수억 건 이상, GPU 인덱스, 분산 클러스터 | [Milvus](/docs/vector-db/09-milvus) |
| 기존 전문 검색(BM25) 인프라에 벡터 추가 | [Elasticsearch](/docs/vector-db/10-elasticsearch) |
| 운영 데이터가 MongoDB에 있음 | [MongoDB Atlas](/docs/vector-db/11-mongodb-atlas) |
| 낮은 지연, 캐시·세션과 같은 인프라 공유 | [Redis](/docs/vector-db/12-redis) |
| 오프라인 배치, 연구용 라이브러리 | [FAISS](/docs/vector-db/13-faiss) |

## 공통 체크리스트

- **필터 문법**이 DB마다 다르므로 리트리버 생성 코드를 한곳에 모아 두면 교체가 쉽습니다.
- **ID 전략**: 문서 ID를 결정적으로(예: `출처 경로 + 청크 번호`의 해시) 만들어야 재색인 시 중복이 생기지 않습니다. Qdrant는 ID로 UUID 또는 정수만 허용합니다.
- **점수 방향**: 거리(작을수록 유사)인지 유사도(클수록 유사)인지 확인하세요.
- **백업·스냅샷·멀티테넌시·권한**은 관리형 서비스와 셀프호스트 간 차이가 가장 큰 영역입니다.

> [!TIP]
> 처음에는 InMemoryVectorStore나 Qdrant `:memory:`로 파이프라인을 완성하고, 평가 셋으로 품질을 확인한 뒤 운영 요구사항(규모, 관리 부담, 비용)에 맞춰 DB를 고르세요.

## 관련 문서

- [벡터 검색 핵심 개념](/docs/vector-db/01-concepts)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [리트리버](/docs/langchain/15-retrievers)
- [LangChain 벡터 스토어 통합 목록](https://docs.langchain.com/oss/python/integrations/vectorstores)
