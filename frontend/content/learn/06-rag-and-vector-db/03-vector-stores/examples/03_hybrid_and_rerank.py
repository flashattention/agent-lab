"""하이브리드 검색(BM25 + Dense)과 RRF 융합, 그리고 리랭킹(2단계 검색) 직접 만들기.

1. BM25 를 순수 파이썬으로 구현 (키워드/고유명사/에러코드에 강함)
2. Dense(임베딩) 검색 (의미/동의어에 강함)
3. RRF(Reciprocal Rank Fusion)로 두 순위를 합친다 — 점수 스케일이 달라도 순위만 쓰므로 안전
4. 리랭커로 상위 후보를 다시 정렬한다 (여기서는 학습용 경량 리랭커, 현업은 Cross-Encoder/Cohere 등)
5. Qdrant 의 네이티브 하이브리드(dense + sparse)도 인메모리로 실행
"""

import hashlib
import math
import re
import uuid
from collections import Counter

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, SparseEmbeddings, SparseVector
from qdrant_client import QdrantClient, models

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

docs = [
    Document(id="d1", page_content="ERR-4012 오류는 결제 토큰이 만료되었을 때 발생합니다. 앱을 재로그인하세요."),
    Document(id="d2", page_content="결제가 실패하면 카드 한도와 유효기간을 먼저 확인하세요."),
    Document(id="d3", page_content="ERR-5001 오류는 서버 점검 중에 표시됩니다."),
    Document(id="d4", page_content="로그인 세션은 30일 후 자동으로 만료됩니다."),
    Document(id="d5", page_content="결제 수단은 카드, 계좌이체, 간편결제를 지원합니다."),
]
query = "결제할 때 ERR-4012 가 떠요"


# ---------------------------------------------------------------------------
# 1) BM25 (Okapi) — 키워드 검색의 업계 표준 점수
# ---------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    """영문/숫자 단어 + 한글 단어 + 한글 2-gram (조사 붙은 단어도 부분 매칭되도록)."""
    words = re.findall(r"[a-z0-9]+|[가-힣]+", text.lower())
    grams = [w[i : i + 2] for w in words if re.match(r"[가-힣]", w) and len(w) > 2 for i in range(len(w) - 1)]
    return words + grams


class BM25:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in corpus]
        self.lengths = [sum(c.values()) for c in self.docs]
        self.avgdl = sum(self.lengths) / len(self.lengths)
        n = len(corpus)
        df = Counter(term for c in self.docs for term in c)  # 단어가 등장한 문서 수
        # IDF: 드문 단어일수록 큰 가중치 (ERR-4012 같은 희귀 토큰이 강해지는 이유)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, dl in zip(self.docs, self.lengths):
            s = 0.0
            for term in q:
                if term in tf:
                    f = tf[term]
                    # TF 포화(k1) + 문서 길이 정규화(b)
                    s += self.idf[term] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


bm25 = BM25([d.page_content for d in docs])
bm25_scores = bm25.scores(query)
bm25_rank = [docs[i].id for i in sorted(range(len(docs)), key=lambda i: -bm25_scores[i])]

# ---------------------------------------------------------------------------
# 2) Dense 검색
# ---------------------------------------------------------------------------
dense_store = InMemoryVectorStore(embedding=embeddings)
dense_store.add_documents(docs)
dense_rank = [d.id for d in dense_store.similarity_search(query, k=len(docs))]

print("=" * 60)
print(f"질의: {query}")
print("=" * 60)
print("BM25 순위 :", bm25_rank, "| 점수:", [round(s, 2) for s in sorted(bm25_scores, reverse=True)])
print("Dense 순위:", dense_rank)


# ---------------------------------------------------------------------------
# 3) RRF 융합: score(d) = Σ 1 / (k + rank)
# ---------------------------------------------------------------------------
def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """여러 순위 리스트를 합친다. k=60 은 원 논문의 관례값(상위권 차이를 완만하게)."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


hybrid = rrf([bm25_rank, dense_rank])
print("\nRRF 하이브리드:", [(i, round(s, 4)) for i, s in hybrid])


# ---------------------------------------------------------------------------
# 4) 리랭킹: 1단계(빠르고 넓게) 후보 → 2단계(느리지만 정확하게) 재정렬
# ---------------------------------------------------------------------------
def toy_rerank(question: str, candidates: list[Document], top_n: int = 2) -> list[tuple[Document, float]]:
    """학습용 경량 리랭커: 질문 토큰을 문서가 얼마나 '덮는지'(coverage)로 점수화.

    실제 Cross-Encoder 는 (질문, 문서) 쌍을 한 번에 모델에 넣어 관련도를 직접 예측합니다.
    인터페이스(질문 + 후보 → 점수 정렬)는 동일하므로 이 함수만 교체하면 됩니다.
    """
    q_terms = set(tokenize(question))
    scored = []
    for d in candidates:
        d_terms = set(tokenize(d.page_content))
        coverage = len(q_terms & d_terms) / max(len(q_terms), 1)
        scored.append((d, round(coverage, 3)))
    return sorted(scored, key=lambda x: -x[1])[:top_n]


by_id = {d.id: d for d in docs}
candidates = [by_id[i] for i, _ in hybrid[:4]]  # 1단계: 하이브리드 상위 4개
print("\n리랭킹 후 최종 top-2:")
for d, s in toy_rerank(query, candidates):
    print(f"  ({s}) [{d.id}] {d.page_content}")


# ---------------------------------------------------------------------------
# 5) Qdrant 네이티브 하이브리드 (dense + sparse 를 한 컬렉션에, 서버 쪽에서 RRF)
# ---------------------------------------------------------------------------
class HashedTFSparse(SparseEmbeddings):
    """학습용 희소(sparse) 임베딩: 토큰 해시 → 인덱스, 등장 횟수 → 값.
    현업에서는 FastEmbedSparse(model_name="Qdrant/bm25") 나 SPLADE 를 씁니다."""

    def _embed(self, text: str) -> SparseVector:
        counts: Counter[int] = Counter(int(hashlib.md5(t.encode()).hexdigest(), 16) % 2**20 for t in tokenize(text))
        return SparseVector(indices=list(counts), values=[float(v) for v in counts.values()])

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._embed(text)


client = QdrantClient(":memory:")
dim = len(embeddings.embed_query("dim"))
client.create_collection(
    "hybrid_docs",
    vectors_config={"dense": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
    sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},  # IDF 는 서버가 계산
)
qdrant_hybrid = QdrantVectorStore(
    client=client,
    collection_name="hybrid_docs",
    embedding=embeddings,
    sparse_embedding=HashedTFSparse(),
    retrieval_mode=RetrievalMode.HYBRID,
    vector_name="dense",
    sparse_vector_name="sparse",
)
# ⚠ Qdrant 의 point id 는 UUID 또는 정수만 허용 → 'd1' 같은 문자열 id 는 uuid5 로 결정적 변환
qdrant_hybrid.add_documents(docs, ids=[str(uuid.uuid5(uuid.NAMESPACE_URL, d.id)) for d in docs])
print("\nQdrant 네이티브 하이브리드 top-3:")
for d, s in qdrant_hybrid.similarity_search_with_score(query, k=3):
    print(f"  (fused={s:.3f}) {d.page_content}")
