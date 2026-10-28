"""지연 최적화(병렬화)와 안정성(재시도·폴백).

1) 순차 vs 병렬 그래프 — 서로 독립적인 조회 3개를 같은 superstep 에서 동시에 실행
2) LLM 배치 — 여러 입력을 abatch 로 동시에 (max_concurrency 로 제공자 한도 보호)
3) ModelRetryMiddleware + ModelFallbackMiddleware
   - 일시적 오류(429/5xx)는 지수 백오프로 재시도
   - 그래도 실패하면 다른 모델(다른 제공자/리전)로 폴백
"""

from __future__ import annotations

import asyncio
import operator
import os
import time
from typing import Annotated, Any, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langgraph.graph import END, START, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


# ====================================================================== 1) 병렬 그래프
class State(TypedDict):
    customer_id: str
    facts: Annotated[list[str], operator.add]  # 병렬 노드의 결과를 합치는 리듀서


def make_lookup(name: str, delay: float):
    async def lookup(state: State) -> dict[str, Any]:
        await asyncio.sleep(delay)  # 외부 API I/O
        return {"facts": [f"{name} ok"]}
    return lookup


LOOKUPS = {"profile": 0.3, "orders": 0.3, "tickets": 0.3}


def build(parallel: bool):
    g = StateGraph(State)
    for name, d in LOOKUPS.items():
        g.add_node(name, make_lookup(name, d))
    names = list(LOOKUPS)
    if parallel:  # START → 세 노드로 fan-out → END 로 fan-in (같은 superstep 에서 동시 실행)
        for n in names:
            g.add_edge(START, n)
            g.add_edge(n, END)
    else:  # START → profile → orders → tickets → END
        g.add_edge(START, names[0])
        for a, b in zip(names, names[1:]):
            g.add_edge(a, b)
        g.add_edge(names[-1], END)
    return g.compile()


async def demo_parallel() -> None:
    print("=" * 70 + "\n1) 독립 조회 3개: 순차 vs 병렬\n" + "=" * 70)
    for label, parallel in [("순차", False), ("병렬", True)]:
        t0 = time.perf_counter()
        out = await build(parallel).ainvoke({"customer_id": "C-1", "facts": []})
        print(f"{label}: {time.perf_counter() - t0:.2f}s  facts={out['facts']}")


async def demo_batch() -> None:
    print("\n" + "=" * 70 + "\n2) LLM 배치 호출 (abatch + max_concurrency)\n" + "=" * 70)
    llm = init_chat_model(MODEL)
    tickets = [f"문의 {i}: 배송이 늦어요" for i in range(6)]
    t0 = time.perf_counter()
    results = await llm.abatch(tickets, config={"max_concurrency": 3})  # 동시 3개까지만
    print(f"{len(results)}건 처리 {time.perf_counter() - t0:.3f}s — 첫 결과: {results[0].content[:40]}")


# ====================================================================== 3) 재시도 + 폴백
class FlakyModel(BaseChatModel):
    """항상 '429 Too Many Requests' 를 내는 장애 모델 (주 모델 장애 시뮬레이션)."""

    attempts: int = 0

    @property
    def _llm_type(self) -> str:
        return "flaky"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.attempts += 1
        raise RuntimeError("429 Too Many Requests (simulated)")


def demo_fallback() -> None:
    print("\n" + "=" * 70 + "\n3) 재시도 → 폴백\n" + "=" * 70)
    primary = FlakyModel()
    agent = create_agent(
        primary,
        middleware=[
            # 순서 주의: 바깥(먼저 등록)이 폴백, 안쪽이 재시도 → '주 모델 재시도 후 폴백'
            ModelFallbackMiddleware(MODEL),
            ModelRetryMiddleware(max_retries=2, initial_delay=0.05, backoff_factor=2.0, jitter=False,
                                 on_failure="error"),
        ],
    )
    t0 = time.perf_counter()
    out = agent.invoke({"messages": [HumanMessage("안녕하세요")]})
    print(f"주 모델 시도 횟수: {primary.attempts} (1회 + 재시도 2회)")
    print(f"최종 응답 모델: {out['messages'][-1].response_metadata.get('model_name')}")
    print(f"소요: {time.perf_counter() - t0:.2f}s  응답: {out['messages'][-1].content[:50]}")


async def main() -> None:
    await demo_parallel()
    await demo_batch()
    demo_fallback()


asyncio.run(main())
