"""임베딩 차원(dimension)이 저장 비용과 검색 품질에 미치는 영향 체감하기.

1. 문서 수 × 차원 × 4바이트(float32)로 필요한 메모리를 계산한다.
2. 벡터 앞부분만 잘라(truncate) 다시 정규화했을 때 순위가 얼마나 유지되는지 본다.
   (OpenAI text-embedding-3 계열은 Matryoshka 방식으로 학습돼 `dimensions=` 인자로
    차원을 줄여도 품질 손실이 비교적 작습니다. Mock 임베딩은 그런 학습이 없으므로
    여기서는 '순위가 어떻게 흔들리는지 측정하는 방법'에 집중하세요.)
"""

import numpy as np
from langchain_openai import OpenAIEmbeddings

# ---------------------------------------------------------------------------
# 1) 저장 비용 계산기
# ---------------------------------------------------------------------------
print("=" * 60)
print("1) 벡터 저장에 필요한 메모리 (float32 기준, 인덱스 오버헤드 제외)")
print("=" * 60)
for n_docs in (10_000, 1_000_000, 10_000_000):
    for dim in (256, 1536, 3072):
        gb = n_docs * dim * 4 / 1024**3
        print(f"  문서 {n_docs:>10,}개 × {dim:>4}차원 → {gb:8.2f} GB")
print("→ 차원을 1536→256으로 줄이면 저장/메모리가 1/6로 줄어듭니다. HNSW 그래프 등 인덱스 오버헤드는 별도입니다.")

# ---------------------------------------------------------------------------
# 2) 차원 축소(truncation) 후 순위 비교
# ---------------------------------------------------------------------------
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
docs = [
    "LangGraph는 상태 기반 그래프로 에이전트 워크플로를 만든다.",
    "벡터 데이터베이스는 임베딩을 저장하고 근사 최근접 이웃 검색을 한다.",
    "코사인 유사도는 두 벡터 사이 각도로 의미의 가까움을 잰다.",
    "김치찌개는 돼지고기와 묵은지로 끓이면 맛있다.",
    "임베딩 모델은 텍스트를 고정 길이 벡터로 바꾼다.",
]
query = "임베딩 벡터의 유사도 검색"

full_docs = np.array(embeddings.embed_documents(docs))
full_q = np.array(embeddings.embed_query(query))
full_dim = full_docs.shape[1]


def rank(doc_m: np.ndarray, q: np.ndarray) -> list[int]:
    """정규화 후 코사인 유사도 내림차순 인덱스."""
    doc_m = doc_m / np.linalg.norm(doc_m, axis=1, keepdims=True).clip(min=1e-12)
    q = q / max(np.linalg.norm(q), 1e-12)
    return [int(i) for i in np.argsort(-(doc_m @ q))]


baseline = rank(full_docs, full_q)
print("\n" + "=" * 60)
print(f"2) 원래 차원 {full_dim} 의 순위: {baseline}")
print("=" * 60)
for dim in (full_dim // 2, full_dim // 4, full_dim // 8):
    r = rank(full_docs[:, :dim], full_q[:dim])  # 앞 dim개만 사용 → 반드시 재정규화
    same_top1 = r[0] == baseline[0]
    overlap = len(set(r[:3]) & set(baseline[:3]))
    print(f"  {dim:>4}차원 순위: {r} | top-1 유지: {same_top1} | top-3 겹침: {overlap}/3")

print("\n핵심: 차원을 줄일 때는 '감'이 아니라 이렇게 평가셋으로 순위 변화를 측정해서 결정합니다.")
