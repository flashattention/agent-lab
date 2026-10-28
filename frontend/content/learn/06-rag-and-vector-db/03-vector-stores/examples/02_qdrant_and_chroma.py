"""실전 벡터 DB 두 가지를 인메모리 모드로 체험하기: Qdrant 와 Chroma.

- Qdrant: QdrantClient(":memory:") — 서버 없이 같은 API 로 동작 (프로덕션은 URL 만 바꾼다)
- Chroma: chromadb.EphemeralClient() — 프로세스 안의 임시 DB (컬렉션 이름은 3자 이상)

두 DB 의 '필터 문법'과 '점수 의미'가 다르다는 점에 주목하세요.
"""

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
DIM = len(embeddings.embed_query("차원 확인용"))  # 컬렉션을 만들려면 벡터 차원을 알아야 한다

docs = [
    Document(page_content="환불은 상품 수령 후 7일 이내에 신청할 수 있습니다.", metadata={"category": "refund", "year": 2026, "tenant": "acme"}),
    Document(page_content="환불 금액은 3~5 영업일 후 카드사로 돌아갑니다.", metadata={"category": "refund", "year": 2025, "tenant": "acme"}),
    Document(page_content="환불은 구매 후 14일 이내 가능합니다.", metadata={"category": "refund", "year": 2026, "tenant": "globex"}),
    Document(page_content="배송은 평균 2일 걸립니다.", metadata={"category": "shipping", "year": 2026, "tenant": "acme"}),
]
ids = [f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, len(docs) + 1)]  # Qdrant id 는 UUID 또는 정수
query = "환불은 언제까지 신청할 수 있나요?"

# ===========================================================================
# 1) Qdrant (인메모리)
# ===========================================================================
print("=" * 60)
print("1) Qdrant :memory:")
print("=" * 60)
client = QdrantClient(":memory:")  # 프로덕션: QdrantClient(url="http://qdrant:6333", api_key=...)
client.create_collection(
    collection_name="support_docs",
    vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
)
qdrant = QdrantVectorStore(client=client, collection_name="support_docs", embedding=embeddings)
qdrant.add_documents(docs, ids=ids)

# Qdrant 필터: 메타데이터는 payload 의 "metadata.*" 아래에 저장된다
acme_only = models.Filter(
    must=[
        models.FieldCondition(key="metadata.tenant", match=models.MatchValue(value="acme")),  # 권한(테넌트) 필터
        models.FieldCondition(key="metadata.year", range=models.Range(gte=2026)),  # 범위 필터
    ]
)
for doc, score in qdrant.similarity_search_with_score(query, k=3, filter=acme_only):
    print(f"  (cosine={score:.3f}) tenant={doc.metadata['tenant']} year={doc.metadata['year']} | {doc.page_content}")

print("  필터 없이 검색하면 다른 테넌트(globex) 문서도 섞입니다:")
for doc in qdrant.similarity_search(query, k=3):
    print(f"    tenant={doc.metadata['tenant']} | {doc.page_content}")

# 프로덕션 팁: 필터에 자주 쓰는 필드는 payload 인덱스를 만든다 (인메모리 모드에서는 효과 없음)
# client.create_payload_index("support_docs", field_name="metadata.tenant", field_schema=models.PayloadSchemaType.KEYWORD)

# ===========================================================================
# 2) Chroma (Ephemeral)
# ===========================================================================
print("\n" + "=" * 60)
print("2) Chroma EphemeralClient")
print("=" * 60)
chroma_client = chromadb.EphemeralClient()  # 프로덕션: chromadb.HttpClient(host=..., port=8000)
chroma = Chroma(
    client=chroma_client,
    collection_name="support_docs",  # 3자 이상이어야 함
    embedding_function=embeddings,
    collection_metadata={"hnsw:space": "cosine"},  # 거리 척도 지정 (기본은 l2)
)
chroma.add_documents(docs, ids=ids)

# Chroma 필터: MongoDB 스타일 where 절 ($and, $or, $eq, $gte, $in ...)
where = {"$and": [{"tenant": {"$eq": "acme"}}, {"year": {"$gte": 2026}}]}
for doc, dist in chroma.similarity_search_with_score(query, k=3, filter=where):
    print(f"  (distance={dist:.3f}) tenant={doc.metadata['tenant']} | {doc.page_content}")
print("  ⚠ Chroma 의 similarity_search_with_score 는 '거리'(작을수록 유사)를 돌려줍니다.")

for doc, rel in chroma.similarity_search_with_relevance_scores(query, k=2):
    print(f"  (relevance={rel:.3f}) {doc.page_content}  ← 0~1, 클수록 유사로 변환된 값")

# ===========================================================================
# 3) 같은 인터페이스: 어떤 저장소든 retriever 로 바꾸면 에이전트 코드는 동일
# ===========================================================================
print("\n" + "=" * 60)
print("3) 공통 Retriever 인터페이스")
print("=" * 60)
for name, vs in [("qdrant", qdrant), ("chroma", chroma)]:
    r = vs.as_retriever(search_kwargs={"k": 1})
    print(f"  {name:6s} → {r.invoke('배송 기간')[0].page_content}")
