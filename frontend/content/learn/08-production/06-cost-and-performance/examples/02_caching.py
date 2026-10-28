"""세 층의 캐시: 노드 캐시 · LLM 응답 캐시 · (제공자) 프롬프트 캐시.

1) LangGraph 노드 캐시 — CachePolicy + compile(cache=InMemoryCache())
   같은 입력으로 같은 노드가 실행되면 결과를 재사용한다. (임베딩, 외부 API, 비싼 계산)
2) LLM 응답 캐시 — 모델 객체에 cache 를 주면 '완전히 같은 입력'의 응답을 재사용한다.
3) 프롬프트 캐시 — OpenAI 등 제공자가 '같은 접두사(prefix)'의 입력 토큰을 할인한다.
   코드가 아니라 '프롬프트 구조'로 얻는 캐시다. (Mock 모드에서는 관찰 불가 → 설명만)
"""

from __future__ import annotations

import os
import time
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.caches import InMemoryCache as LLMCache
from langchain_core.globals import set_llm_cache
from langgraph.cache.memory import InMemoryCache
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


# ====================================================================== 1) 노드 캐시
class State(TypedDict):
    query: str
    docs: list[str]


CALLS = {"retrieve": 0}


def retrieve(state: State) -> dict:
    """비싼 검색 노드 (임베딩 + 벡터 검색 + 리랭킹을 흉내 내는 0.3초 지연)."""
    CALLS["retrieve"] += 1
    time.sleep(0.3)
    return {"docs": [f"'{state['query']}' 관련 문서 {i}" for i in range(3)]}


def cache_key(state: State) -> str:
    """캐시 키 함수: 대소문자·공백 차이는 같은 질의로 취급한다."""
    return " ".join(state["query"].lower().split())


builder = StateGraph(State)
builder.add_node("retrieve", retrieve, cache_policy=CachePolicy(ttl=300, key_func=cache_key))
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", END)
graph = builder.compile(cache=InMemoryCache())  # 운영: Redis/SQLite 기반 캐시

print("=" * 70 + "\n1) 노드 캐시 (CachePolicy)\n" + "=" * 70)
for q in ["환불 정책", "환불   정책", "교환 정책", "환불 정책"]:
    t0 = time.perf_counter()
    graph.invoke({"query": q, "docs": []})
    print(f"query={q!r:<14} {1000 * (time.perf_counter() - t0):6.1f}ms  누적 실행 횟수={CALLS['retrieve']}")
assert CALLS["retrieve"] == 2, "'환불 정책' 계열은 한 번만 실행되어야 한다"

# ====================================================================== 2) LLM 응답 캐시
print("\n" + "=" * 70 + "\n2) LLM 응답 캐시\n" + "=" * 70)
llm_cache = LLMCache()
set_llm_cache(llm_cache)  # 전역 캐시: cache 를 따로 지정하지 않은 모든 채팅 모델에 적용
cached_llm = init_chat_model(MODEL)  # 특정 모델에만 쓰려면 init_chat_model(MODEL, cache=llm_cache)
prompt = "FAQ: 배송은 며칠 걸리나요? 한 문장으로."
for i in range(3):
    t0 = time.perf_counter()
    msg = cached_llm.invoke(prompt)
    print(f"호출 {i + 1}: {1000 * (time.perf_counter() - t0):6.2f}ms  usage={msg.usage_metadata}")
print("캐시 항목 수:", len(llm_cache._cache))  # 데모용으로 내부 dict 를 들여다본다
assert len(llm_cache._cache) == 1
cached_llm.invoke(prompt + " ")  # 공백 하나만 달라도 새 항목
print("공백 하나 다른 프롬프트 후 캐시 항목 수:", len(llm_cache._cache))
print("→ 2번째부터는 모델을 호출하지 않는다. 단, '완전히 같은' 입력(+모델 설정)에만 적중한다.")
set_llm_cache(None)  # 아래 예제에 영향을 주지 않도록 해제

# ====================================================================== 3) 프롬프트 캐시
print("\n" + "=" * 70 + "\n3) 제공자 프롬프트 캐시 — 프롬프트를 '고정 → 가변' 순서로\n" + "=" * 70)
STATIC_SYSTEM = "너는 ACME 상담원이다.\n" + "[정책 문서 …수천 토큰…]\n" * 3  # 모든 요청에서 동일
good = [("system", STATIC_SYSTEM), ("human", "주문 A-1 상태?")]  # 접두사 동일 → 캐시 적중
bad = [("system", f"현재 시각 {time.time():.0f}\n" + STATIC_SYSTEM), ("human", "주문 A-1 상태?")]  # 매번 달라짐
print("좋은 구조: system(고정) → 대화 기록 → 새 질문      ⇒ 긴 접두사가 매 요청 동일")
print("나쁜 구조: system 맨 앞에 시각/사용자명 같은 가변값 ⇒ 접두사가 매번 달라 캐시 불가")
resp = init_chat_model(MODEL).invoke(good)
details = (resp.usage_metadata or {}).get("input_token_details", {})
print("usage.input_token_details =", details or "(Mock 모드에서는 비어 있음 — 실제 키로 실행하면 cache_read 가 보인다)")
