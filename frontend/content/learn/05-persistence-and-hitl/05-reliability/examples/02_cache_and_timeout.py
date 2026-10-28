"""예제 2: CachePolicy로 같은 입력의 비싼 노드 결과 재사용 + timeout으로 멈춘 노드 끊기.

- CachePolicy(ttl=..., key_func=...) + compile(cache=InMemoryCache())
- timeout=초  : 한 번의 노드 시도에 대한 하드 제한 (async 노드에서만 동작)
- TimeoutPolicy(idle_timeout=..., run_timeout=...) + runtime.heartbeat(): '진행 중이면 연장'
"""

import asyncio
import time
from typing import TypedDict

from langgraph.cache.memory import InMemoryCache
from langgraph.errors import NodeError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, TimeoutPolicy

# ---------------------------------------------------------------------------
# 1) 캐시
# ---------------------------------------------------------------------------


class QAState(TypedDict, total=False):
    question: str
    request_id: str  # 요청마다 달라지는 값 → 캐시 키에서 제외해야 한다
    answer: str


EXPENSIVE_CALLS = {"n": 0}


def expensive_answer(state: QAState) -> dict:
    """비싼 LLM/검색 호출이라고 가정한다."""
    EXPENSIVE_CALLS["n"] += 1
    time.sleep(0.2)
    return {"answer": f"'{state['question']}'에 대한 답 (계산 #{EXPENSIVE_CALLS['n']})"}


def cache_key(state: QAState) -> str:
    """request_id는 빼고 질문만으로 캐시 키를 만든다. (정규화도 함께)"""
    return state["question"].strip().lower()


builder = StateGraph(QAState)
builder.add_node("answer", expensive_answer, cache_policy=CachePolicy(ttl=300, key_func=cache_key))
builder.add_edge(START, "answer")
builder.add_edge("answer", END)
qa = builder.compile(cache=InMemoryCache())  # 캐시 백엔드는 compile에서 지정

print("=" * 64)
print("1) CachePolicy")
print("=" * 64)
for i, q in enumerate(["What is LangGraph?", "what is langgraph?  ", "What is a checkpointer?"]):
    t0 = time.perf_counter()
    updates = list(qa.stream({"question": q, "request_id": f"req-{i}"}, stream_mode="updates"))
    ms = (time.perf_counter() - t0) * 1000
    cached = any(u.get("__metadata__", {}).get("cached") for u in updates)
    answer = next(u["answer"]["answer"] for u in updates if "answer" in u)
    print(f"  {q!r:<28} {ms:6.1f}ms  cached={cached!s:<5}  → {answer}")
assert EXPENSIVE_CALLS["n"] == 2, "정규화된 같은 질문은 캐시에서 나와야 한다"

# ---------------------------------------------------------------------------
# 2) 타임아웃
# ---------------------------------------------------------------------------


class JobState(TypedDict, total=False):
    result: str


async def hanging_call(state: JobState) -> dict:
    """응답 없이 멈춘 외부 API를 흉내 낸다."""
    await asyncio.sleep(5)
    return {"result": "never"}


async def long_but_alive(state: JobState, runtime: Runtime) -> dict:
    """오래 걸리지만 진행 중임을 heartbeat로 알리는 작업 (예: 대용량 문서 처리)."""
    for _ in range(6):
        await asyncio.sleep(0.1)
        runtime.heartbeat()  # "아직 살아 있어요" → idle_timeout 연장
    return {"result": "0.6초 작업 완료"}


def on_timeout(state: JobState, error: NodeError) -> dict:
    return {"result": f"타임아웃으로 대체 응답 ({type(error.error).__name__})"}


async def main() -> None:
    print("\n" + "=" * 64)
    print("2) timeout")
    print("=" * 64)

    # (a) 하드 타임아웃 0.3초, 핸들러 없음 → NodeTimeoutError
    g1 = StateGraph(JobState)
    g1.add_node("call", hanging_call, timeout=0.3)
    g1.add_edge(START, "call")
    t0 = time.perf_counter()
    try:
        await g1.compile().ainvoke({})
    except NodeTimeoutError as e:
        print(f"  (a) {time.perf_counter() - t0:.2f}초 만에 중단: {e}")

    # (b) 같은 상황 + error_handler → 대체 응답으로 계속
    g2 = StateGraph(JobState)
    g2.add_node("call", hanging_call, timeout=0.3, error_handler=on_timeout)
    g2.add_edge(START, "call")
    out = await g2.compile().ainvoke({})
    print("  (b)", out["result"])

    # (c) idle_timeout 0.3초지만 heartbeat로 진행을 알리면 0.6초 작업도 성공
    g3 = StateGraph(JobState)
    g3.add_node("job", long_but_alive, timeout=TimeoutPolicy(idle_timeout=0.3, run_timeout=3))
    g3.add_edge(START, "job")
    out = await g3.compile().ainvoke({})
    print("  (c)", out["result"])
    assert out["result"] == "0.6초 작업 완료"


asyncio.run(main())
print("\n✔ 캐시와 타임아웃 예제 완료")
