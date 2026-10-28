"""[실습] 스트림 한 번으로 UI에 필요한 모든 정보 모으기 — 정답

글쓰기 파이프라인 그래프가 있다.

    outline(부모) → drafting(서브그래프: draft 노드) → polish(부모)

draft 노드와 polish 노드 모두 LLM을 호출하지만, 사용자 화면에는 polish 의 '최종 답변' 토큰만
보여 줘야 한다. 진행 상황(progress)은 별도 영역에, 실행된 노드 순서는 디버그 패널에 보여 준다.

과제
1. outline 노드에서 get_stream_writer()로 {"stage": "outline", ...} 진행 이벤트를 1개 이상 보내라.
2. summarize_stream() 을 완성하라. graph.stream(...)을 **한 번만** 호출해서
   - final_text : tags 에 "final" 이 붙은 LLM 토큰만 이어 붙인 문자열
   - draft_tokens : tags 에 "draft" 가 붙은 토큰 개수 (화면에는 안 보여도 개수는 센다)
   - progress  : custom 이벤트 데이터 리스트
   - node_order: updates 이벤트에서 (네임스페이스 라벨, 노드 이름) 튜플 리스트
   를 담은 dict 를 반환한다.
   힌트: stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2"
"""

from __future__ import annotations

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


# ------------------------------------------------------------ 그래프 (수정하지 않아도 됨)
def outline(state: MessagesState) -> dict[str, Any]:
    # TODO(1) 정답: 진행 이벤트 보내기
    writer = get_stream_writer()
    writer({"stage": "outline", "msg": "목차 3개 생성"})
    return {}


def draft(state: MessagesState) -> dict[str, Any]:
    msg = llm.invoke(state["messages"], config={"tags": ["draft"]})
    return {"messages": [msg]}


def polish(state: MessagesState) -> dict[str, Any]:
    msg = llm.invoke(state["messages"][:1] + [HumanMessage("초안을 다듬어줘")], config={"tags": ["final"]})
    return {"messages": [msg]}


sub = StateGraph(MessagesState)
sub.add_node("draft", draft)
sub.add_edge(START, "draft")
sub.add_edge("draft", END)

builder = StateGraph(MessagesState)
builder.add_node("outline", outline)
builder.add_node("drafting", sub.compile())
builder.add_node("polish", polish)
builder.add_edge(START, "outline")
builder.add_edge("outline", "drafting")
builder.add_edge("drafting", "polish")
builder.add_edge("polish", END)
graph = builder.compile()


def ns_label(ns: tuple[str, ...]) -> str:
    return "root" if not ns else ns[-1].split(":")[0]


# ------------------------------------------------------------ 과제
def summarize_stream(inputs: dict[str, Any]) -> dict[str, Any]:
    """그래프를 한 번 스트리밍하면서 UI 에 필요한 정보를 모은다."""
    final_tokens: list[str] = []
    draft_tokens = 0
    progress: list[dict] = []
    node_order: list[tuple[str, str]] = []

    # TODO(2) 정답
    for part in graph.stream(
        inputs, stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2"
    ):
        if part["type"] == "messages":
            chunk, meta = part["data"]
            tags = meta.get("tags") or []
            if "final" in tags and chunk.content:
                final_tokens.append(chunk.content)
            elif "draft" in tags and chunk.content:
                draft_tokens += 1
        elif part["type"] == "updates":
            for node in part["data"]:
                node_order.append((ns_label(part["ns"]), node))
        elif part["type"] == "custom":
            progress.append(part["data"])

    return {
        "final_text": "".join(final_tokens),
        "draft_tokens": draft_tokens,
        "progress": progress,
        "node_order": node_order,
    }


# ------------------------------------------------------------ 자가 채점
result = summarize_stream({"messages": [HumanMessage("스트리밍에 대한 블로그 글을 써줘")]})
print("final_text  :", result["final_text"][:70])
print("draft_tokens:", result["draft_tokens"])
print("progress    :", result["progress"])
print("node_order  :", result["node_order"])

assert result["final_text"], "final 태그 토큰을 모아야 합니다"
assert result["draft_tokens"] > 0, "draft 태그 토큰 수를 세어야 합니다"
assert any(p.get("stage") == "outline" for p in result["progress"]), "outline 노드에서 진행 이벤트를 보내세요"
root_nodes = [n for ns, n in result["node_order"] if ns == "root"]
assert root_nodes == ["outline", "drafting", "polish"], f"부모 그래프 노드 순서가 이상합니다: {root_nodes}"
assert ("drafting", "draft") in result["node_order"], "subgraphs=True 로 서브그래프 내부 노드도 수집하세요"
print("✅ 모든 테스트 통과!")
