"""4.3 예제 3 — LLM 구조화 출력을 라우터로 쓰기.

- LLM 호출은 노드(classify)에서, 길 찾기는 라우터(route_by_department)에서.
- 선택지는 Literal 로 강제하고, 분류 이유(reason)도 상태에 남긴다.
Mock 모드에서는 질문에 선택지 문자열(refund/tech/general)이 들어 있으면 그 값을 고른다.
"""

import os
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
Department = Literal["refund", "tech", "general"]


class Route(BaseModel):
    """고객 문의를 담당 부서로 분류한다."""

    department: Department = Field(description="refund: 환불/취소, tech: 기술 문제, general: 그 외")
    reason: str = Field(description="분류 이유 한 문장")


router_llm = init_chat_model(MODEL).with_structured_output(Route)

ROUTER_PROMPT = (
    "너는 고객센터 분류기다. 문의를 refund, tech, general 중 하나로 분류하고 이유를 한 문장으로 쓴다. "
    "애매하면 general 을 고른다."
)


class TicketState(TypedDict, total=False):
    text: str
    department: Department
    route_reason: str
    reply: str


def classify(state: TicketState) -> dict:
    decision: Route = router_llm.invoke([SystemMessage(ROUTER_PROMPT), HumanMessage(state["text"])])
    # 분류 결과와 이유를 상태에 '기록' → 트레이스·디버깅·지표에 활용
    return {"department": decision.department, "route_reason": decision.reason}


def route_by_department(state: TicketState) -> Department:
    dept = state.get("department")
    return dept if dept in ("refund", "tech", "general") else "general"  # 폴백 경로


def refund(state: TicketState) -> dict:
    return {"reply": "[환불팀] 주문번호를 알려주세요."}


def tech(state: TicketState) -> dict:
    return {"reply": "[기술팀] 오류 화면을 캡처해 보내주세요."}


def general(state: TicketState) -> dict:
    return {"reply": "[상담팀] 확인 후 연락드리겠습니다."}


builder = StateGraph(TicketState)
for fn in (classify, refund, tech, general):
    builder.add_node(fn)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_by_department, ["refund", "tech", "general"])
for n in ("refund", "tech", "general"):
    builder.add_edge(n, END)
graph = builder.compile()

if __name__ == "__main__":
    questions = [
        "결제를 취소하고 refund 받고 싶어요",
        "앱이 계속 꺼져요. tech 지원 부탁해요",
        "다음 달 이벤트가 있나요?",
    ]
    for q in questions:
        out = graph.invoke({"text": q})
        print("-" * 60)
        print(f"문의   : {q}")
        print(f"부서   : {out['department']}  (이유: {out['route_reason']})")
        print(f"답변   : {out['reply']}")
    print("\n※ Mock 모드에서는 선택지 단어가 없는 질문의 분류가 임의로 정해집니다. 실제 키로 비교해 보세요.")
