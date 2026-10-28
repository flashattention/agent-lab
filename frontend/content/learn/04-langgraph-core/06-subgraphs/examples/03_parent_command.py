"""4.6 예제 3 — Command.PARENT: 서브그래프에서 부모 그래프 노드로 핸드오프.

FAQ 서브그래프의 triage 노드가 환불 문의를 발견하면 부모의 refund_team 으로 넘긴다.
주의: 부모에 반영되는 것은 Command 의 update 뿐이다.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class SupportState(TypedDict, total=False):
    question: str
    log: Annotated[list[str], operator.add]
    handoff_reason: str
    reply: str


# ---------------------------------------------------------------- 서브그래프: FAQ 에이전트
def lookup(state: SupportState) -> dict:
    return {"log": ["faq.lookup: FAQ 검색함"]}  # ← 핸드오프 시 이 업데이트는 부모로 가지 않는다!


def triage(state: SupportState):
    if "환불" in state["question"]:
        return Command(
            graph=Command.PARENT,  # 부모 그래프 기준으로 이동
            goto="refund_team",  # 부모의 노드 이름
            update={"handoff_reason": "환불 문의", "log": ["faq.triage: 환불팀으로 핸드오프"]},
        )
    return {"log": ["faq.triage: FAQ 로 처리"], "reply": "FAQ: 배송은 2~3일 걸립니다."}


faq_builder = StateGraph(SupportState)
faq_builder.add_node(lookup)
faq_builder.add_node(triage)
faq_builder.add_edge(START, "lookup")
faq_builder.add_edge("lookup", "triage")
faq_builder.add_edge("triage", END)
faq_agent = faq_builder.compile()


# ---------------------------------------------------------------- 부모 그래프
def refund_team(state: SupportState) -> dict:
    return {"log": ["refund_team: 환불 접수"], "reply": f"환불팀: 접수했습니다 (사유: {state['handoff_reason']})"}


parent = StateGraph(SupportState)
parent.add_node("faq_agent", faq_agent, destinations=("refund_team",))  # 그림에 핸드오프 경로 표시
parent.add_node(refund_team)
parent.add_edge(START, "faq_agent")
parent.add_edge("faq_agent", END)
parent.add_edge("refund_team", END)
graph = parent.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())

    for q in ("배송은 얼마나 걸려요?", "환불하고 싶어요"):
        print("=" * 64)
        print("질문:", q)
        for namespace, chunk in graph.stream({"question": q, "log": []}, stream_mode="updates", subgraphs=True):
            where = "부모" if not namespace else "faq_agent 내부"
            print(f"  [{where:<13}] {chunk}")
        out = graph.invoke({"question": q, "log": []})
        print("  최종 log :", out["log"])
        print("  최종 답변:", out["reply"])
    print("\n※ 환불 경로의 최종 log 에 'faq.lookup' 이 없다 → Command.PARENT 로 나가면 update 만 전달된다.")
