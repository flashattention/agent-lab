"""4.6 예제 2 — 변환 상태 서브그래프: create_agent 에이전트를 파이프라인의 한 단계로.

부모(보고서 파이프라인)와 자식(리서치 에이전트)은 스키마가 완전히 다르다.
래퍼 노드가 '필요한 것만 넣고, 필요한 것만 꺼내는' 어댑터 역할을 한다 → 컨텍스트 격리.
"""

import os
from typing import TypedDict

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

KB = {
    "langgraph": "LangGraph v1은 상태 기반 그래프로 에이전트 흐름을 제어한다.",
    "subgraph": "서브그래프는 다른 그래프의 노드로 쓰이는 컴파일된 그래프다.",
}


@tool
def search_docs(query: str) -> str:
    """사내 문서 검색 도구: 기술 키워드로 문서를 찾습니다."""
    hits = [text for key, text in KB.items() if key in query.lower()]
    return "\n".join(hits) or "관련 문서 없음"


# 자식: create_agent 가 만든 그래프도 '컴파일된 그래프' = 서브그래프로 쓸 수 있다
research_agent = create_agent(
    MODEL,
    tools=[search_docs],
    system_prompt="너는 리서처다. search_docs 로 찾은 내용만 근거로 2문장 이내로 답한다.",
    name="research_agent",
)


# 부모: 메시지가 없는, 전혀 다른 스키마
class ReportState(TypedDict, total=False):
    topic: str
    findings: str
    agent_steps: int
    report: str


def research(state: ReportState) -> dict:
    """래퍼 노드: 부모 상태 → 자식 입력, 자식 출력 → 부모 업데이트"""
    result = research_agent.invoke(
        {"messages": [HumanMessage(f"{state['topic']}에 대해 search_docs 로 조사해 줘")]},
        {"recursion_limit": 10},
    )
    messages = result["messages"]
    # 자식이 쌓은 메시지(도구 호출 등)는 자식 안에 머물고, 부모에는 최종 답변만 전달
    return {"findings": messages[-1].content, "agent_steps": len(messages)}


def write_report(state: ReportState) -> dict:
    return {"report": f"## {state['topic']}\n{state['findings']}"}


builder = StateGraph(ReportState)
builder.add_node(research)
builder.add_node(write_report)
builder.add_edge(START, "research")
builder.add_edge("research", "write_report")
builder.add_edge("write_report", END)
graph = builder.compile()

if __name__ == "__main__":
    print("── xray=True: 래퍼 노드가 참조하는 모듈 수준의 에이전트 그래프까지 펼쳐서 그려 준다")
    print(graph.get_graph(xray=True).draw_mermaid())

    print("── subgraphs=True 로 스트리밍하면 래퍼 안에서 실행된 에이전트 이벤트도 보인다")
    for namespace, chunk in graph.stream({"topic": "subgraph"}, stream_mode="updates", subgraphs=True):
        level = "부모" if not namespace else " > ".join(ns.split(":")[0] for ns in namespace)
        print(f"  [{level}] {list(chunk)}")

    result = graph.invoke({"topic": "subgraph"})
    print("\n자식 에이전트 내부 메시지 수:", result["agent_steps"], "(부모 상태에는 저장되지 않음)")
    print(result["report"])
