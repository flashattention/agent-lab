"""코사인 유사도를 numpy로 직접 구현해 보기.

임베딩 모델 없이, 손으로 만든 작은 벡터로 다음을 확인합니다.
1. 내적(dot product), 노름(norm), 코사인 유사도, 유클리드 거리의 정의
2. 벡터를 L2 정규화하면 "내적 == 코사인 유사도"가 된다는 사실
3. 행렬 곱 한 번으로 질의 1개 vs 문서 N개의 유사도를 한꺼번에 계산하는 법
"""

import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """두 벡터 사이 각도의 코사인. 1에 가까울수록 같은 방향(=비슷한 의미)."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:  # 0 벡터는 방향이 없으므로 유사도 0으로 처리
        return 0.0
    return float(np.dot(a, b) / denom)


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """두 점 사이의 직선 거리. 0에 가까울수록 가깝다(작을수록 유사)."""
    return float(np.linalg.norm(a - b))


def l2_normalize(m: np.ndarray) -> np.ndarray:
    """각 행(row)을 길이 1로 만든다. 1차원 벡터도 처리한다."""
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


# ---------------------------------------------------------------------------
# 1) 장난감 3차원 "의미 공간": [동물성, 음식성, 기술성] 이라고 상상해 봅시다.
# ---------------------------------------------------------------------------
words = {
    "강아지": np.array([0.9, 0.1, 0.0]),
    "고양이": np.array([0.8, 0.2, 0.1]),
    "피자": np.array([0.1, 0.9, 0.0]),
    "파이썬": np.array([0.3, 0.0, 0.9]),  # 뱀(동물)이기도 하고 언어(기술)이기도!
}

print("=" * 60)
print("1) 코사인 유사도 vs 유클리드 거리 ('강아지' 기준)")
print("=" * 60)
base = words["강아지"]
for name, vec in words.items():
    print(f"  {name:4s} | cosine={cosine_similarity(base, vec):+.3f} | euclid={euclidean_distance(base, vec):.3f}")

# ---------------------------------------------------------------------------
# 2) 길이(크기)만 다른 벡터: 코사인은 같고, 유클리드는 달라진다.
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("2) 방향은 같고 길이만 다른 벡터")
print("=" * 60)
short = np.array([1.0, 1.0, 0.0])
long = short * 10  # 같은 방향, 10배 길이 (예: 같은 단어가 10번 반복된 문서)
print(f"  cosine(short, long) = {cosine_similarity(short, long):.3f}  ← 방향이 같으니 1.0")
print(f"  euclid(short, long) = {euclidean_distance(short, long):.3f} ← 길이 차이 때문에 멀다고 판단")

# ---------------------------------------------------------------------------
# 3) 정규화하면 내적 == 코사인, 그리고 행렬 곱으로 한 번에 계산
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("3) L2 정규화 후 행렬 곱으로 일괄 계산")
print("=" * 60)
names = list(words)
matrix = l2_normalize(np.stack([words[n] for n in names]))  # (문서 수, 차원)
query = l2_normalize(np.array([0.85, 0.15, 0.05]))  # "털 달린 반려동물" 같은 질의라고 가정

scores = matrix @ query  # (문서 수,) — 정규화했으므로 이것이 곧 코사인 유사도
for n, s in sorted(zip(names, scores), key=lambda x: -x[1]):
    print(f"  {n:4s} → {s:.3f}")

# 정규화된 벡터에서 내적과 코사인이 같은지 검증
a, b = matrix[0], matrix[3]
assert abs(float(a @ b) - cosine_similarity(a, b)) < 1e-9
print("\n✔ 정규화된 벡터에서는 내적 == 코사인 유사도 (벡터 DB가 dot product를 쓰는 이유)")

# 정규화된 벡터에서는 유클리드 거리와 코사인도 1:1 대응: ||a-b||^2 = 2 - 2cos
lhs = euclidean_distance(a, b) ** 2
rhs = 2 - 2 * cosine_similarity(a, b)
print(f"✔ ||a-b||² = {lhs:.4f}, 2-2cos = {rhs:.4f} → 순위가 똑같이 나온다")
