"""[실습] 비용 계산기 + 모델 라우터 + 노드 캐시 — 정답

과제
1. estimate_cost(usage, model) : usage_metadata 와 PRICE(USD/1M tokens)로 비용(USD)을 계산하라.
   - 캐시 적중 입력 토큰(usage["input_token_details"]["cache_read"])은 cached_in 단가를 적용한다.
2. pick_model(text, after_tool) : "small" 또는 "large" 를 반환하라.
   - 도구 결과 직후(after_tool=True)면 "small"
   - 글자 수 > 150 이거나 HARD_HINTS 단어가 있으면 "large", 아니면 "small"
3. build_graph() : embed 노드에 CachePolicy(ttl=600)를 걸고 InMemoryCache 로 컴파일하라.
"""

from __future__ import annotations

import os
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.cache.memory import InMemoryCache
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# 예시 단가 (USD / 1M tokens) — 실습용 가상 값
PRICE = {
    "small": {"in": 0.10, "cached_in": 0.01, "out": 0.40},
    "large": {"in": 1.00, "cached_in": 0.10, "out": 8.00},
}
HARD_HINTS = ("비교", "분석", "설계", "왜")


# ------------------------------------------------------------------ TODO 1
def estimate_cost(usage: dict, model: str) -> float:
    p = PRICE[model]
    cached = (usage.get("input_token_details") or {}).get("cache_read", 0)
    fresh_in = usage.get("input_tokens", 0) - cached
    return (fresh_in * p["in"] + cached * p["cached_in"] + usage.get("output_tokens", 0) * p["out"]) / 1_000_000


# ------------------------------------------------------------------ TODO 2
def pick_model(text: str, after_tool: bool = False) -> str:
    if after_tool:
        return "small"
    if len(text) > 150 or any(h in text for h in HARD_HINTS):
        return "large"
    return "small"


# ------------------------------------------------------------------ TODO 3
class State(TypedDict):
    text: str
    vector: list[float]


EMBED_CALLS = {"n": 0}


def embed(state: State) -> dict:
    EMBED_CALLS["n"] += 1
    return {"vector": [float(len(state["text"])), 1.0]}


def build_graph():
    g = StateGraph(State)
    g.add_node("embed", embed, cache_policy=CachePolicy(ttl=600))
    g.add_edge(START, "embed")
    g.add_edge("embed", END)
    return g.compile(cache=InMemoryCache())


# ================================================================== 자가 채점
u = {"input_tokens": 1_000_000, "output_tokens": 100_000, "input_token_details": {"cache_read": 800_000}}
assert abs(estimate_cost(u, "large") - (200_000 * 1.0 + 800_000 * 0.10 + 100_000 * 8.0) / 1e6) < 1e-9
assert abs(estimate_cost({"input_tokens": 2000, "output_tokens": 500}, "small") - 0.0004) < 1e-12
print("1) 비용 계산 통과: large =", round(estimate_cost(u, "large"), 4), "USD")

assert pick_model("배송비 얼마예요?") == "small"
assert pick_model("두 요금제를 비교해줘") == "large"
assert pick_model("가" * 151) == "large"
assert pick_model("두 요금제를 비교해줘", after_tool=True) == "small"
print("2) 라우터 통과")

graph = build_graph()
for _ in range(3):
    graph.invoke({"text": "환불 정책", "vector": []})
graph.invoke({"text": "교환 정책", "vector": []})
assert EMBED_CALLS["n"] == 2, f"embed 는 서로 다른 입력 2번만 실행돼야 합니다 (실제 {EMBED_CALLS['n']})"
print("3) 노드 캐시 통과: embed 실행 횟수 =", EMBED_CALLS["n"])

# 보너스: 실제(또는 Mock) 모델 응답의 usage 로 비용 추정
msg = init_chat_model(MODEL).invoke("안녕하세요")
print("보너스) 이번 호출 예상 비용:", f"${estimate_cost(msg.usage_metadata, pick_model('안녕하세요')):.8f}")
print("✅ 모든 테스트 통과!")
