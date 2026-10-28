"""실제 임베딩 모델로 '의미 검색'의 최소 버전을 만들어 보기.

- OpenAIEmbeddings 로 문서와 질의를 벡터로 바꾼다.
- numpy 행렬 곱으로 유사도를 계산해 top-k 문서를 고른다.
- 이것이 벡터 DB가 내부에서 하는 일의 '가장 단순한 버전'이다.

API 키가 없으면 Mock 임베딩(단어 해시 기반 bag-of-words)이 쓰입니다.
Mock 모드에서는 '같은 단어를 공유할수록' 유사도가 높게 나오고,
실제 모델에서는 단어가 달라도 '의미가 비슷하면' 높게 나옵니다.
"""

import time

import numpy as np
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

docs = [
    "환불은 구매 후 7일 이내에 마이페이지에서 신청할 수 있습니다.",
    "배송은 결제 완료 후 평균 2일이 걸리며, 제주도는 하루 더 걸립니다.",
    "비밀번호를 잊어버렸다면 로그인 화면의 비밀번호 찾기를 누르세요.",
    "회원 등급은 최근 6개월 구매 금액으로 매달 1일에 갱신됩니다.",
    "환불 금액은 카드사 사정에 따라 3~5 영업일 후 카드로 돌아옵니다.",
]

# 1) 문서 임베딩: 보통 '색인(indexing)' 단계에서 한 번만 계산해 저장해 둔다.
t0 = time.perf_counter()
doc_vectors = np.array(embeddings.embed_documents(docs))  # (문서 수, 차원)
print(f"문서 {len(docs)}개 임베딩 완료 → 행렬 모양 {doc_vectors.shape}, {time.perf_counter() - t0:.3f}s")
print(f"벡터 길이(노름) 예시: {np.linalg.norm(doc_vectors[0]):.4f}  (OpenAI 임베딩은 이미 길이 1로 정규화돼 있음)")


def search(question: str, k: int = 2) -> list[tuple[float, str]]:
    """질의를 임베딩하고 코사인 유사도 상위 k개 문서를 돌려준다."""
    q = np.array(embeddings.embed_query(question))
    # 정규화가 보장되지 않는 모델도 있으므로 방어적으로 한 번 더 정규화
    q = q / (np.linalg.norm(q) or 1.0)
    d = doc_vectors / np.linalg.norm(doc_vectors, axis=1, keepdims=True)
    scores = d @ q
    top = np.argsort(-scores)[:k]  # 점수 내림차순 인덱스
    return [(float(scores[i]), docs[i]) for i in top]


questions = [
    "환불 신청은 어디서 하나요?",
    "배송 기간이 얼마나 걸려요?",
    "비밀번호 찾기 방법",
]

for qtext in questions:
    print("\n" + "-" * 60)
    print(f"Q: {qtext}")
    for rank, (score, text) in enumerate(search(qtext), start=1):
        print(f"  {rank}. ({score:.3f}) {text}")

# 2) 전체 유사도 행렬: 문서끼리 얼마나 비슷한지(중복 탐지 등에 활용)
print("\n" + "=" * 60)
print("문서 간 코사인 유사도 행렬 (소수 둘째 자리)")
sim = doc_vectors @ doc_vectors.T
print(np.round(sim, 2))
print("→ 대각선은 자기 자신이라 1.0입니다. 0.9 이상인 쌍이 있다면 중복 문서일 가능성이 큽니다.")
print("  (Mock 임베딩은 '공유 단어' 기반이라 실제 모델과 수치가 다릅니다. API 키를 넣고 비교해 보세요.)")
