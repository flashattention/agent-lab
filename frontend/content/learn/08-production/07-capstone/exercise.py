"""[캡스톤 실습] 정책 확장 + 그래프 조립 + 승인 루프

support_desk 패키지의 부품으로 고객지원 시스템을 직접 조립하고, 새 비즈니스 요구사항을 반영한다.

과제
1. decide_refund_v2(order_id, amount, user_id, tier, reason)
   기존 정책(support_desk.policies.decide_refund)에 새 규칙을 더하라.
   - 사유(reason)에 "불량" 이 들어 있으면 자동 승인 한도를 2배로 한다. (STANDARD 5만 → 10만, VIP 10만 → 20만)
   - 나머지 규칙(본인 주문, 배송 완료 후 7일 이내)은 그대로.
   반환: ("auto" | "review", 사유 문자열)

2. build_graph(checkpointer, store, specialist_model)
   support_desk.graph 의 노드 함수와 support_desk.agents 의 빌더로 최상위 그래프를 조립하라.
   guard 와 route 는 Command(goto=...) 로 다음 노드를 직접 고르므로, 고정 엣지는 4종류만 필요하다.
     START→guard, load_memory→route, (faq_agent|order_agent|smalltalk)→save_memory, save_memory→END

3. handle_turn(graph, text, config, ctx, approver, max_reviews=3)
   한 턴을 실행하고, interrupt 가 있으면 approver(interrupt.value) 의 결정으로 재개하기를 반복하라.
   (무한 루프 방지를 위해 max_reviews 회까지만) 마지막 GraphOutput 을 반환한다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import support_desk.policies as policies
from langchain.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from support_desk.agents import build_faq_agent, build_order_agent
from support_desk.config import SETTINGS
from support_desk.data import ORDERS
from support_desk.graph import SupportState, guard, load_memory, route, save_memory, smalltalk
from support_desk.testing import ScriptedChatModel, call
from support_desk.tools import SupportContext


# ------------------------------------------------------------------ TODO 1
def decide_refund_v2(order_id: str, amount: int, user_id: str, tier: str, reason: str = "") -> tuple[str, str]:
    # TODO 1: support_desk/policies.py 의 decide_refund 를 참고해 '불량' 사유면 한도를 2배로 하는 규칙을 추가하세요
    raise NotImplementedError("TODO 1: decide_refund_v2")


# ------------------------------------------------------------------ TODO 2
def build_graph(*, checkpointer: Any, store: Any, specialist_model: Any = None):
    # TODO 2: StateGraph(SupportState, context_schema=SupportContext) 에 노드 7개를 등록하고
    #         고정 엣지 4종류를 연결한 뒤 checkpointer/store 와 함께 compile 하세요
    raise NotImplementedError("TODO 2: build_graph")


# ------------------------------------------------------------------ TODO 3
def handle_turn(graph, text: str, config: dict, ctx: SupportContext,
                approver: Callable[[dict], dict], max_reviews: int = 3):
    # TODO 3: graph.invoke(..., context=ctx, version="v2") → out.interrupts 가 있으면
    #         approver(out.interrupts[0].value) 결과로 Command(resume=...) 재개. 최대 max_reviews 회.
    raise NotImplementedError("TODO 3: handle_turn")


# ================================================================== 자가 채점
# (1) 정책 판정표
assert decide_refund_v2("A-1001", 89_000, "u-kim", "STANDARD", "단순 변심")[0] == "review"
assert decide_refund_v2("A-1001", 89_000, "u-kim", "STANDARD", "제품 불량")[0] == "auto"
assert decide_refund_v2("A-1001", 89_000, "u-lee", "VIP", "불량")[0] == "review"  # 타인 주문
assert decide_refund_v2("B-2001", 10_000, "u-lee", "STANDARD", "불량")[0] == "review"  # 기간 초과
assert decide_refund_v2("A-1002", 5_000, "u-kim", "VIP", "불량")[0] == "review"  # 배송 중
print("1) 정책 판정표 통과")

# 새 정책을 운영 미들웨어에 연결한다 (refund_approval 은 실행 시점에 policies.decide_refund 를 조회한다)
policies.decide_refund = decide_refund_v2

# (2) 그래프 조립 확인
g = build_graph(checkpointer=InMemorySaver(), store=InMemoryStore())
assert {"guard", "load_memory", "route", "faq_agent", "order_agent", "smalltalk", "save_memory"} <= set(g.get_graph().nodes)
print("2) 그래프 조립 통과")


# (3) 승인 루프 — 대본 모델로 결정적으로
def scenario(reason: str, approver_log: list) -> list[str]:
    model = ScriptedChatModel(responses=[
        call("request_refund", order_id="A-1001", amount=89_000, reason=reason),
        AIMessage("환불 처리 결과를 안내드립니다."),
    ])
    graph = build_graph(checkpointer=InMemorySaver(), store=InMemoryStore(), specialist_model=model)

    def approver(value: dict) -> dict:
        approver_log.append(value["reason"])
        return {"type": "edit", "args": {"amount": 50_000}}  # 상담원이 부분 환불로 조정

    out = handle_turn(graph, "A-1001 환불해 주세요", {"configurable": {"thread_id": reason}},
                      SupportContext("u-kim", "STANDARD"), approver)
    assert not out.interrupts
    return [str(m.content) for m in out.value["messages"] if m.type == "tool"]


log: list[str] = []
tools = scenario("제품 불량", log)
assert not log and "89,000원" in tools[-1], (log, tools)
print("3-a) 불량 사유 → 한도 2배로 자동 환불:", tools[-1][:30])
tools = scenario("단순 변심", log)
assert len(log) == 1 and "50,000원" in tools[-1], (log, tools)
print("3-b) 변심 사유 → 검토 → 상담원 조정(5만 원) 후 환불:", tools[-1][:30])
print("✅ 모든 테스트 통과!")
