"""예제 3: 내구성 모드(durability) 비교.

같은 3단계 그래프를 durability="exit" / "async" / "sync" 로 실행하고
각 스레드에 남은 체크포인트 수와 걸린 시간을 비교합니다.
(LLM 없이 순수 파이썬 노드만 사용합니다.)
"""

import operator
import time
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class PipelineState(TypedDict):
    doc: str
    log: Annotated[list[str], operator.add]  # 각 단계가 로그를 이어 붙인다


def fetch(state: PipelineState) -> dict:
    return {"log": ["fetch"]}


def clean(state: PipelineState) -> dict:
    return {"doc": state["doc"].strip().lower(), "log": ["clean"]}


def summarize(state: PipelineState) -> dict:
    return {"log": [f"summarize({len(state['doc'])}자)"]}


builder = StateGraph(PipelineState)
builder.add_node("fetch", fetch)
builder.add_node("clean", clean)
builder.add_node("summarize", summarize)
builder.add_edge(START, "fetch")
builder.add_edge("fetch", "clean")
builder.add_edge("clean", "summarize")
builder.add_edge("summarize", END)
graph = builder.compile(checkpointer=InMemorySaver())

# 첫 실행에는 import/초기화 비용이 섞이므로 워밍업을 한 번 해 둔다
graph.invoke({"doc": "warmup", "log": []}, {"configurable": {"thread_id": "warmup"}})

print(f"{'mode':<6} | {'체크포인트 수':>10} | {'steps 기록':<22} | 시간")
print("-" * 60)
for mode in ("exit", "async", "sync"):
    config = {"configurable": {"thread_id": f"run-{mode}"}}
    t0 = time.perf_counter()
    graph.invoke({"doc": "  Hello LangGraph  ", "log": []}, config, durability=mode)
    elapsed = (time.perf_counter() - t0) * 1000
    history = list(graph.get_state_history(config))
    steps = [h.metadata["step"] for h in history]
    print(f"{mode:<6} | {len(history):>10} | {str(steps):<22} | {elapsed:.1f}ms")

print(
    "\n해석: 'exit'는 그래프가 끝날 때 한 번만 저장하므로 중간 체크포인트가 없습니다.\n"
    "      → 빠르지만, 도중에 프로세스가 죽으면 처음부터 다시 실행해야 하고\n"
    "        타임 트래블(5.2)로 돌아갈 중간 지점도 없습니다.\n"
    "      'async'(기본)와 'sync'는 모든 단계를 남깁니다. 차이는 '저장 완료를 기다리느냐'입니다.\n"
    "      InMemorySaver에서는 시간 차이가 거의 없지만, 원격 Postgres에서는 sync가 단계마다 왕복 지연을 더합니다."
)
