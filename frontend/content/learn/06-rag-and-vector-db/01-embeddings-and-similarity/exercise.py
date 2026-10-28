"""실습: numpy로 나만의 '미니 벡터 검색기' 만들기

과제
1. `cosine_similarity(a, b)`를 완성하세요. 0 벡터가 들어오면 0.0을 돌려줘야 합니다.
2. `normalize_rows(m)`을 완성하세요. 2차원 행렬의 각 행을 길이 1로 만듭니다(0 행은 그대로 둡니다).
3. `top_k(query_vec, doc_matrix, k)`를 완성하세요.
   정규화 + 행렬 곱으로 유사도를 구하고, (문서 인덱스, 점수) 튜플을 점수 내림차순으로 k개 돌려줍니다.

힌트: np.linalg.norm(..., axis=1, keepdims=True), 행렬 곱 연산자 @, np.argsort(-scores)
"""

import numpy as np
from langchain_openai import OpenAIEmbeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    # TODO: 내적 / (노름 × 노름). 분모가 0이면 0.0을 반환하세요.
    return 0.0


def normalize_rows(m: np.ndarray) -> np.ndarray:
    # TODO: 각 행을 자신의 L2 노름으로 나누세요. 노름이 0인 행은 1로 나눠 그대로 둡니다.
    return m


def top_k(query_vec: np.ndarray, doc_matrix: np.ndarray, k: int = 3) -> list[tuple[int, float]]:
    # TODO: 1) 문서 행렬과 질의 벡터를 정규화  2) 행렬 곱으로 점수 계산
    #       3) 점수 내림차순 상위 k개 인덱스를 골라 (index, score) 리스트로 반환
    return []


# ---------------------------------------------------------------------------
# 실제 임베딩으로 사용해 보기 (Mock 모드에서도 동작)
# ---------------------------------------------------------------------------
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
docs = [
    "환불은 구매 후 7일 이내에 신청할 수 있습니다.",
    "배송은 평균 2일이 걸립니다.",
    "비밀번호는 로그인 화면에서 재설정합니다.",
    "환불 금액은 카드로 3~5일 후 돌아옵니다.",
]
doc_matrix = np.array(embeddings.embed_documents(docs))
q = np.array(embeddings.embed_query("환불 신청 기간"))
results = top_k(q, doc_matrix, k=2)
for idx, score in results:
    print(f"({score:.3f}) {docs[idx]}")

# ---------------------------------------------------------------------------
# 자가 채점
# ---------------------------------------------------------------------------
assert abs(cosine_similarity(np.array([1.0, 0.0]), np.array([0.0, 1.0]))) < 1e-9, "직교 벡터의 코사인은 0"
assert abs(cosine_similarity(np.array([1.0, 2.0]), np.array([2.0, 4.0])) - 1.0) < 1e-9, "같은 방향은 1"
assert abs(cosine_similarity(np.array([1.0, 0.0]), np.array([-1.0, 0.0])) + 1.0) < 1e-9, "반대 방향은 -1"
assert cosine_similarity(np.zeros(3), np.ones(3)) == 0.0, "0 벡터는 0.0"

n = normalize_rows(np.array([[3.0, 4.0], [0.0, 0.0]]))
assert np.allclose(n[0], [0.6, 0.8]), "각 행이 길이 1이 되어야 합니다"
assert np.allclose(n[1], [0.0, 0.0]), "0 행은 그대로 0이어야 합니다"

toy = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]])
r = top_k(np.array([1.0, 0.1]), toy, k=2)
assert len(r) == 2, "k개를 반환해야 합니다"
assert r[0][0] == 0 and r[1][0] == 2, "점수 내림차순이어야 합니다"
assert r[0][1] >= r[1][1]
assert len(results) == 2 and all(0 <= i < len(docs) for i, _ in results)

print("✅ 모든 테스트 통과!")
