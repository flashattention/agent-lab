"""실습: 테넌트 격리 + 하이브리드 검색기 만들기 (Qdrant 인메모리)

여러 고객사(tenant)의 문서가 한 컬렉션에 들어 있습니다.
다른 고객사 문서가 절대 섞이지 않으면서, 키워드와 의미를 함께 쓰는 검색기를 완성하세요.

과제
1. `rrf(rankings, k=60)`: 여러 순위 리스트(문서 id 리스트)를 RRF 로 합쳐 (id, 점수) 를 점수 내림차순으로 반환
2. `tenant_filter(tenant)`: Qdrant Filter 를 만들어 metadata.tenant == tenant 인 문서만 검색되게 하기
3. `hybrid_search(query, tenant, k)`:
   - dense 순위: vector_store.similarity_search(query, k=10, filter=tenant_filter(tenant)) 의 doc_id 목록
   - keyword 순위: keyword_rank(query, tenant) (이미 구현됨)
   - 두 순위를 rrf 로 합쳐 상위 k 개의 doc_id 리스트 반환
"""

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

DOCS = [
    ("a-1", "acme", "ACME 환불은 수령 후 7일 이내 신청할 수 있습니다."),
    ("a-2", "acme", "ACME 배송은 평균 2일 걸립니다."),
    ("a-3", "acme", "ACME 오류 코드 E-77 은 결제 토큰 만료입니다."),
    ("g-1", "globex", "GLOBEX 환불은 수령 후 30일 이내 신청할 수 있습니다."),
    ("g-2", "globex", "GLOBEX 오류 코드 E-77 은 재고 부족입니다."),
]
docs = [Document(page_content=t, metadata={"doc_id": i, "tenant": ten}) for i, ten, t in DOCS]

client = QdrantClient(":memory:")
client.create_collection(
    "tenant_docs",
    vectors_config=models.VectorParams(size=len(embeddings.embed_query("x")), distance=models.Distance.COSINE),
)
vector_store = QdrantVectorStore(client=client, collection_name="tenant_docs", embedding=embeddings)
vector_store.add_documents(docs)


def keyword_rank(query: str, tenant: str) -> list[str]:
    """(제공됨) 아주 단순한 키워드 순위: 질의 단어가 문서에 몇 개 들어 있는지."""
    words = query.lower().split()
    pool = [d for d in docs if d.metadata["tenant"] == tenant]
    scored = sorted(pool, key=lambda d: -sum(w in d.page_content.lower() for w in words))
    return [d.metadata["doc_id"] for d in scored]


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    # TODO: 각 순위 리스트에서 rank(1부터 시작)마다 1/(k+rank) 를 더하고, 점수 내림차순 정렬해 반환
    return []


def tenant_filter(tenant: str) -> models.Filter | None:
    # TODO: models.Filter(must=[models.FieldCondition(key="metadata.tenant", match=models.MatchValue(value=...))])
    return None


def hybrid_search(query: str, tenant: str, k: int = 2) -> list[str]:
    # TODO: dense 순위(필터 적용) + keyword 순위를 rrf 로 합친 뒤 상위 k 개 doc_id 반환
    return []


result = hybrid_search("E-77 오류 코드 의미", tenant="acme", k=2)
print("acme 하이브리드 결과:", result)

# ---------------------------------------------------------------------------
# 자가 채점
# ---------------------------------------------------------------------------
fused = rrf([["x", "y", "z"], ["y", "x"]])
assert [i for i, _ in fused][:2] in (["x", "y"], ["y", "x"]), "x, y 가 상위 2개여야 합니다"
assert abs(dict(fused)["z"] - 1 / 63) < 1e-9, "z 는 한 리스트에서 3위 → 1/(60+3)"
assert abs(dict(fused)["x"] - (1 / 61 + 1 / 62)) < 1e-9, "x 는 1위와 2위 → 1/61 + 1/62"
assert fused[0][1] >= fused[-1][1], "점수 내림차순"

f = tenant_filter("acme")
assert isinstance(f, models.Filter), "Qdrant models.Filter 를 반환해야 합니다"
leak = vector_store.similarity_search("환불 신청", k=10, filter=f)
assert leak and all(d.metadata["tenant"] == "acme" for d in leak), "다른 테넌트 문서가 섞이면 안 됩니다"

assert len(result) == 2, "k 개를 반환해야 합니다"
assert all(r.startswith("a-") for r in result), "acme 문서만 나와야 합니다"
assert "a-3" in result, "E-77 키워드가 있는 acme 문서가 포함돼야 합니다"
print("✅ 모든 테스트 통과!")
