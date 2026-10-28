"""4.4 예제 2 — Send 로 동적 팬아웃(map) + 리듀서로 수집(reduce).

plan 이 주제 목록을 정하면, 주제 수만큼 research 노드가 '병렬로' 실행되고,
결과는 notes 리듀서로 모인 뒤 write 가 보고서를 쓴다. research 단계는 LLM 노드다.
"""

import operator
import os
import time
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
MAX_TOPICS = 5  # 팬아웃 수 = 동시 LLM 호출 수 = 비용. 반드시 상한을 둔다.


class ReportState(TypedDict, total=False):
    subject: str
    style: str
    topics: list[str]
    notes: Annotated[list[dict], operator.add]  # reduce: 병렬 결과를 이어 붙인다
    report: str


class ResearchInput(TypedDict):
    """research 노드가 받는 작은 입력. 전체 상태가 아니다!"""

    topic: str
    style: str


def plan(state: ReportState) -> dict:
    # 실제로는 LLM 이 주제를 정할 수도 있다. 여기서는 결정적으로 만든다.
    topics = [f"{state['subject']}의 {aspect}" for aspect in ("개념", "장점", "한계", "사례", "미래", "역사")]
    return {"topics": topics[:MAX_TOPICS]}


def fan_out(state: ReportState) -> list[Send]:
    """map: 주제마다 research 를 다른 입력으로 실행하라는 Send 를 만든다."""
    return [Send("research", {"topic": t, "style": state["style"]}) for t in state["topics"]]


def research(state: ResearchInput) -> dict:
    started = time.perf_counter()
    try:
        ai = llm.invoke([HumanMessage(f"'{state['topic']}'을(를) {state['style']} 한 문장으로 설명해 줘.")])
        note = {"topic": state["topic"], "text": ai.content}
    except Exception as e:  # 실패를 데이터로 기록 → 한 작업 실패가 전체를 망치지 않게
        note = {"topic": state["topic"], "error": str(e)}
    note["ms"] = round((time.perf_counter() - started) * 1000)
    return {"notes": [note]}


def write(state: ReportState) -> dict:
    ok = [n for n in state["notes"] if "text" in n]
    failed = [n for n in state["notes"] if "error" in n]
    lines = [f"# {state['subject']} 보고서 ({len(ok)}개 섹션, 실패 {len(failed)})"]
    lines += [f"- {n['topic']}: {n['text'][:70]}" for n in ok]
    return {"report": "\n".join(lines)}


builder = StateGraph(ReportState)
builder.add_node(plan)
builder.add_node(research)
builder.add_node(write)
builder.add_edge(START, "plan")
builder.add_conditional_edges("plan", fan_out, ["research"])  # 목적지 목록을 알려 그림을 정확히
builder.add_edge("research", "write")  # 모든 research 가 같은 스텝에 끝나므로 write 는 1번만 실행
builder.add_edge("write", END)
graph = builder.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
    inputs = {"subject": "LangGraph", "style": "초보자도 이해하게"}

    print("── 실행 흐름 (updates)")
    for chunk in graph.stream(inputs, stream_mode="updates", config={"max_concurrency": 3}):
        node, update = next(iter(chunk.items()))
        if node == "research":
            print(f"  research 완료: {update['notes'][0]['topic']}")
        else:
            print(f"  {node} 완료: {list(update)}")

    result = graph.invoke(inputs, config={"max_concurrency": 3})  # 동시 실행 수 제한
    print("\n" + result["report"])
    assert len(result["notes"]) == MAX_TOPICS
