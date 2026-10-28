"""InMemoryVectorStore로 벡터 저장소의 공통 인터페이스 익히기.

LangChain의 모든 VectorStore(Qdrant, Chroma, pgvector, Pinecone ...)는 같은 메서드를 공유합니다.
  add_documents / similarity_search / similarity_search_with_score
  max_marginal_relevance_search / delete / as_retriever
여기서 익힌 코드는 저장소만 바꾸면 그대로 프로덕션 DB에서도 동작합니다.
"""

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
store = InMemoryVectorStore(embedding=embeddings)

docs = [
    Document(id="p1", page_content="환불은 상품 수령 후 7일 이내에 신청할 수 있습니다.", metadata={"category": "refund", "year": 2026}),
    Document(id="p2", page_content="환불 신청은 마이페이지 주문 내역에서 할 수 있습니다.", metadata={"category": "refund", "year": 2026}),
    Document(id="p3", page_content="환불 신청은 마이페이지 주문 내역 메뉴에서 가능합니다.", metadata={"category": "refund", "year": 2024}),
    Document(id="p4", page_content="환불 금액은 3~5 영업일 후 카드사로 돌아갑니다.", metadata={"category": "refund", "year": 2026}),
    Document(id="s1", page_content="배송은 평균 2일 걸리며 도서산간은 하루 더 걸립니다.", metadata={"category": "shipping", "year": 2026}),
    Document(id="a1", page_content="비밀번호 재설정은 로그인 화면에서 할 수 있습니다.", metadata={"category": "account", "year": 2025}),
]

# 1) 추가: id 를 직접 지정하면 같은 id 로 다시 넣을 때 '갱신(upsert)'처럼 동작
ids = store.add_documents(docs)
print("저장된 id:", ids)

query = "환불 신청 방법"

# 2) 기본 유사도 검색 (+ 점수)
print("\n" + "=" * 60)
print("2) similarity_search_with_score — 점수는 코사인 유사도(클수록 유사)")
print("=" * 60)
for doc, score in store.similarity_search_with_score(query, k=3):
    print(f"  ({score:.3f}) [{doc.id}] {doc.page_content}")
print("  → p2와 p3는 사실상 같은 내용(중복)입니다. top-3 중 2자리를 같은 정보가 차지했죠.")

# 3) 메타데이터 필터: InMemoryVectorStore 는 'Document -> bool' 함수를 받는다
print("\n" + "=" * 60)
print("3) 메타데이터 필터 (2026년 문서만)")
print("=" * 60)
for doc in store.similarity_search(query, k=3, filter=lambda d: d.metadata["year"] >= 2026):
    print(f"  [{doc.id}] year={doc.metadata['year']} {doc.page_content}")

# 4) MMR: 관련성 + 다양성
print("\n" + "=" * 60)
print("4) MMR (fetch_k=6 후보에서 k=3 선택, lambda_mult=0.3 → 다양성 중시)")
print("=" * 60)
for doc in store.max_marginal_relevance_search(query, k=3, fetch_k=6, lambda_mult=0.3):
    print(f"  [{doc.id}] {doc.page_content}")
print("  → 중복(p2/p3)이 한 자리로 줄고, 다른 관점의 문서가 들어옵니다.")

# 5) Retriever: 에이전트/체인에 꽂는 표준 인터페이스 (Runnable 이라 .invoke 사용)
print("\n" + "=" * 60)
print("5) as_retriever — 검색 설정을 묶어 '검색기' 객체로")
print("=" * 60)
retriever = store.as_retriever(search_type="mmr", search_kwargs={"k": 2, "fetch_k": 6})
for doc in retriever.invoke("환불 기간"):
    print(f"  [{doc.id}] {doc.page_content}")

# 점수 임계값: InMemoryVectorStore 는 relevance score 변환을 지원하지 않으므로
# (as_retriever(search_type="similarity_score_threshold") 는 NotImplementedError)
# 점수를 받아 직접 거른다. 임계값은 반드시 자기 데이터의 점수 분포를 보고 정할 것.
THRESHOLD = 0.2
kept = [d for d, s in store.similarity_search_with_score("비밀번호 재설정", k=5) if s >= THRESHOLD]
print(f"  score >= {THRESHOLD} 인 문서 수: {len(kept)} → {[d.id for d in kept]}")

# 6) 삭제와 갱신
store.delete(ids=["p3"])  # 중복 문서 제거
store.add_documents([Document(id="a1", page_content="비밀번호 재설정은 설정 > 보안 메뉴로 이동했습니다.", metadata={"category": "account", "year": 2026})])
print("\n6) p3 삭제 + a1 갱신 후:", store.get_by_ids(["a1"])[0].page_content)
print("   p3 존재 여부:", bool(store.get_by_ids(["p3"])))
