"""stream_mode 다섯 가지를 한 그래프로 비교한다.

같은 그래프를 values / updates / messages / custom / debug 로 각각 돌려 보고,
마지막에는 여러 모드를 한 번에 구독하는 version="v2" 형식까지 확인한다.

실행: 오른쪽 IDE에서 ▶ 실행 (API 키가 없으면 Mock 모델로 동작)
"""

from __future__ import annotations

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


class State(MessagesState):
    """대화 메시지 + 검색으로 찾은 문서 개수."""

    doc_count: int


def retrieve(state: State) -> dict[str, Any]:
    """가짜 검색 노드. get_stream_writer()로 진행률을 custom 이벤트로 내보낸다."""
    writer = get_stream_writer()  # 그래프 실행 중이 아니면 no-op 함수가 반환된다
    for i in range(1, 4):
        writer({"stage": "retrieve", "progress": f"{i}/3 문서 읽는 중"})
    return {"doc_count": 3}


def generate(state: State) -> dict[str, Any]:
    """LLM 호출 노드. 이 안의 토큰이 messages 모드로 흘러나온다."""
    writer = get_stream_writer()
    writer({"stage": "generate", "progress": "답변 생성 시작"})
    # config의 tags는 messages 모드 메타데이터로 전달되어 프론트에서 필터링 기준이 된다
    reply = llm.invoke(state["messages"], config={"tags": ["final_answer"]})
    return {"messages": [reply]}


builder = StateGraph(State)
builder.add_node("retrieve", retrieve)
builder.add_node("generate", generate)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)
graph = builder.compile()

INPUT = {"messages": [HumanMessage("LangGraph 스트리밍을 한 문장으로 설명해줘")], "doc_count": 0}


def short(obj: Any, n: int = 90) -> str:
    """출력이 너무 길지 않게 잘라 준다."""
    s = repr(obj)
    return s if len(s) <= n else s[:n] + "…"


def section(title: str) -> None:
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


# 1) values: 각 superstep이 끝날 때마다 "전체 상태"를 통째로 보낸다
section("1) stream_mode='values' — 매 단계의 전체 상태 스냅샷")
for state in graph.stream(INPUT, stream_mode="values"):
    print(f"keys={list(state)} | messages={len(state['messages'])} | doc_count={state['doc_count']}")

# 2) updates: 노드가 반환한 "변경분"만 {노드이름: 업데이트} 형태로 보낸다
section("2) stream_mode='updates' — 노드별 변경분(delta)")
for update in graph.stream(INPUT, stream_mode="updates"):
    for node, delta in update.items():
        print(f"[{node}] → {short(delta)}")

# 3) messages: LLM 토큰 단위 (chunk, metadata) 튜플
section("3) stream_mode='messages' — LLM 토큰 스트림")
tokens: list[str] = []
for chunk, meta in graph.stream(INPUT, stream_mode="messages"):
    tokens.append(chunk.content)
    print(f"node={meta['langgraph_node']:<9} tags={meta.get('tags')} token={chunk.content!r}")
print("합친 결과:", "".join(tokens)[:80])

# 4) custom: get_stream_writer()로 내보낸 임의의 데이터
section("4) stream_mode='custom' — 노드가 직접 쏘는 진행 상황")
for data in graph.stream(INPUT, stream_mode="custom"):
    print("📣", data)

# 5) debug: 태스크 시작/종료, 체크포인트 등 실행 엔진 내부 이벤트
section("5) stream_mode='debug' — 실행 엔진 이벤트")
for ev in graph.stream(INPUT, stream_mode="debug"):
    print(f"step={ev['step']} type={ev['type']:<12} name={ev['payload'].get('name')}")

# 6) 여러 모드 동시 구독 + version="v2": 모든 파트가 {type, ns, data} 딕셔너리로 통일된다
section("6) 다중 모드 + version='v2' — 프로덕션 권장 형식")
counts: dict[str, int] = {}
final: AIMessage | None = None
for part in graph.stream(INPUT, stream_mode=["updates", "messages", "custom"], version="v2"):
    counts[part["type"]] = counts.get(part["type"], 0) + 1
    if part["type"] == "updates" and "generate" in part["data"]:
        final = part["data"]["generate"]["messages"][-1]
print("파트 종류별 개수:", counts)
print("최종 답변:", final.content[:80] if final else None)
