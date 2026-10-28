"""4.4 예제 3 — 슈퍼스텝과 defer.

길이가 다른 병렬 가지가 한 집계 노드로 모일 때, defer 없이는 집계가 두 번 실행된다.
debug 스트림의 step 번호로 슈퍼스텝을 눈으로 확인한다.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class S(TypedDict):
    log: Annotated[list[str], operator.add]


def make(name: str):
    def node(state: S) -> dict:
        # 같은 스텝의 노드들은 스텝 시작 시점의 스냅샷을 읽는다
        return {"log": [f"{name}(봤던 log 길이={len(state['log'])})"]}

    return node


def build(defer: bool):
    """a → b1 → c → agg (긴 가지),  a → b2 → agg (짧은 가지)"""
    b = StateGraph(S)
    for name in ("a", "b1", "b2", "c"):
        b.add_node(name, make(name))
    b.add_node("agg", make("agg"), defer=defer)
    b.add_edge(START, "a")
    b.add_edge("a", "b1")
    b.add_edge("a", "b2")
    b.add_edge("b1", "c")
    b.add_edge("c", "agg")
    b.add_edge("b2", "agg")
    b.add_edge("agg", END)
    return b.compile()


for defer in (False, True):
    print("=" * 64)
    print(f"defer={defer}")
    print("=" * 64)
    graph = build(defer)
    for ev in graph.stream({"log": []}, stream_mode="debug"):
        if ev["type"] == "task":  # 노드 실행 시작 이벤트
            print(f"  superstep {ev['step']}: {ev['payload']['name']}")
    final = graph.invoke({"log": []})["log"]
    print("  agg 실행 횟수:", sum(x.startswith("agg") for x in final))
    print("  최종 log:", final)
