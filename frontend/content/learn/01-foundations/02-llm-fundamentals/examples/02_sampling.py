"""샘플링(Sampling) 시뮬레이션: temperature 와 top-p 가 다음 토큰 선택에 주는 영향.

실제 LLM 은 수십만 개 어휘에 대해 점수(logit)를 내지만, 여기서는 6개 후보로 축소해
softmax → temperature → top-p → 샘플링 과정을 numpy 로 직접 구현한다.
"""

from __future__ import annotations

import numpy as np

# "오늘 날씨가 정말 ___" 다음에 올 토큰 후보와 모델이 낸 점수(logit, 가상의 값)
CANDIDATES = ["좋다", "덥다", "춥다", "맑다", "이상하다", "바나나"]
LOGITS = np.array([3.0, 2.2, 1.8, 1.5, 0.5, -2.0])


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """temperature 로 나눈 뒤 softmax. T가 작을수록 분포가 뾰족해진다."""
    z = logits / max(temperature, 1e-6)
    z = z - z.max()  # 수치 안정성
    e = np.exp(z)
    return e / e.sum()


def top_p_filter(probs: np.ndarray, top_p: float) -> np.ndarray:
    """누적 확률이 top_p 에 도달할 때까지의 후보만 남기고 다시 정규화(nucleus sampling)."""
    order = np.argsort(probs)[::-1]
    cum = np.cumsum(probs[order])
    keep = order[: int(np.searchsorted(cum, top_p) + 1)]
    out = np.zeros_like(probs)
    out[keep] = probs[keep]
    return out / out.sum()


def bar(p: float, width: int = 30) -> str:
    return "█" * int(round(p * width))


if __name__ == "__main__":
    rng = np.random.default_rng(seed=42)  # 재현 가능한 결과를 위해 시드 고정

    for t in [0.2, 1.0, 2.0]:
        probs = softmax(LOGITS, t)
        print(f"\n🌡️ temperature={t}")
        for tok, p in zip(CANDIDATES, probs):
            print(f"  {tok:<6} {p:6.1%} {bar(p)}")
        draws = rng.choice(CANDIDATES, size=10, p=probs)
        print("  10번 샘플링:", " ".join(draws))

    print("\n✂️ top_p=0.8 적용 (temperature=1.0)")
    filtered = top_p_filter(softmax(LOGITS, 1.0), 0.8)
    for tok, p in zip(CANDIDATES, filtered):
        print(f"  {tok:<6} {p:6.1%} {bar(p)}")

    print("\n💡 temperature 가 낮으면 같은 답을 반복(결정적), 높으면 다양하지만 엉뚱한 답('바나나')도 나옵니다.")
    print("💡 GPT-5 계열 추론 모델은 temperature 설정을 거부하므로, 이 과정에서는 설정하지 않습니다.")
