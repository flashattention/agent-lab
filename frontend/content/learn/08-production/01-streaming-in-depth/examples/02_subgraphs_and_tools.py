"""서브그래프 스트리밍(subgraphs=True)과 도구 안에서의 custom 스트림.

- 부모 그래프 안에 '리서치 서브그래프'를 노드로 넣는다.
- subgraphs=True 를 주면 서브그래프 내부 이벤트도 네임스페이스(ns)와 함께 올라온다.
- create_agent 의 도구는 ToolRuntime.stream_writer 로 진행 상황을 보낼 수 있다.
"""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import ToolRuntime, tool
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


# ---------------------------------------------------------------- 도구 + 에이전트
@tool
def search_papers(query: str, runtime: ToolRuntime) -> str:
    """논문 데이터베이스에서 query와 관련된 논문(papers)을 검색한다."""
    # 도구 실행 중간 상태를 UI로 보낸다: "검색 중… 12건 발견"
    runtime.stream_writer({"tool": "search_papers", "status": "started"})
    hits = ["ReAct (2022)", "Reflexion (2023)", "LATS (2023)"]
    runtime.stream_writer({"tool": "search_papers", "status": "done", "hits": len(hits)})
    return "\n".join(hits)


# create_agent가 만든 그래프도 결국 CompiledStateGraph → 다른 그래프의 노드(서브그래프)가 될 수 있다
research_agent = create_agent(
    MODEL,
    tools=[search_papers],
    system_prompt="너는 논문 리서치 담당이다. 반드시 search_papers 도구를 써라.",
    name="research_agent",
)


# ---------------------------------------------------------------- 부모 그래프
def plan(state: MessagesState) -> dict[str, Any]:
    get_stream_writer()({"stage": "plan", "msg": "질문을 분석해 리서치 계획 수립"})
    return {}


def write_report(state: MessagesState) -> dict[str, Any]:
    get_stream_writer()({"stage": "report", "msg": "보고서 작성 완료"})
    return {}


builder = StateGraph(MessagesState)
builder.add_node("plan", plan)
builder.add_node("research", research_agent)  # 상태 키(messages)를 공유하므로 그대로 붙일 수 있다
builder.add_node("report", write_report)
builder.add_edge(START, "plan")
builder.add_edge("plan", "research")
builder.add_edge("research", "report")
builder.add_edge("report", END)
graph = builder.compile()

INPUT = {"messages": [HumanMessage("에이전트 추론 기법 papers 를 search 해서 정리해줘")]}


def ns_label(ns: tuple[str, ...]) -> str:
    """('research:3f2a…', ) 같은 네임스페이스를 사람이 읽기 좋게 바꾼다."""
    return "root" if not ns else " > ".join(part.split(":")[0] for part in ns)


print("=" * 70)
print("A) subgraphs=False (기본값) — 서브그래프는 '하나의 노드'로만 보인다")
print("=" * 70)
for part in graph.stream(INPUT, stream_mode="updates", version="v2"):
    print(f"[{ns_label(part['ns'])}] {list(part['data'])}")

print("\n" + "=" * 70)
print("B) subgraphs=True — 내부 노드(model/tools)까지 네임스페이스와 함께 보인다")
print("=" * 70)
seen_ns: set[str] = set()
for part in graph.stream(INPUT, stream_mode=["updates", "custom"], subgraphs=True, version="v2"):
    label = ns_label(part["ns"])
    seen_ns.add(label)
    if part["type"] == "updates":
        print(f"[{label:<9}] update  {list(part['data'])}")
    else:
        print(f"[{label:<9}] custom  {part['data']}")

print("\n" + "=" * 70)
print("C) messages 모드에서 '최종 답변 토큰'만 골라내기")
print("=" * 70)
# 실무 포인트: 도구 결과(ToolMessage)도 messages 모드로 흘러나온다.
# 화면에 보여줄 토큰은 'model 노드에서 나온 AIMessageChunk' 로 한정한다.
answer = []
for part in graph.stream(INPUT, stream_mode="messages", subgraphs=True, version="v2"):
    chunk, meta = part["data"]
    if meta["langgraph_node"] == "model" and chunk.type == "AIMessageChunk" and chunk.content:
        answer.append(chunk.content)
print("".join(answer)[:120])

assert "research" in seen_ns, "서브그래프 네임스페이스가 보여야 한다"
print("\n관찰된 네임스페이스:", sorted(seen_ns))
