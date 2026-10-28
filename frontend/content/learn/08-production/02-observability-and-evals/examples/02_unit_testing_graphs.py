"""에이전트 단위 테스트: 모델 출력을 '대본'으로 고정하고 그래프의 동작을 검증한다.

테스트 피라미드의 맨 아래층이다. 빠르고(밀리초), 공짜이고, 결정적이다.
"모델이 X라고 답하면 시스템은 Y를 해야 한다"를 검증한다. 모델이 똑똑한지는 여기서 보지 않는다.
(그건 evals 의 일 → examples/03_eval_harness.py)

검증하는 것
1. 노드 함수 단위 테스트 (그래프 없이 함수만 호출)
2. 라우팅 함수 테스트 (조건부 엣지)
3. 도구 호출 궤적(trajectory) 테스트 — 어떤 도구를 어떤 인자로 몇 번 불렀나
4. 모델에게 전달된 입력 검증 — 시스템 프롬프트, 도구 결과가 제대로 들어갔나
5. HITL — 위험한 도구가 실제로 멈추는가
"""

from __future__ import annotations

from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from testing_utils import ScriptedChatModel, run_tests, tool_call

# ======================================================================
# 테스트 대상 (실무에서는 app/ 패키지에 있고, tests/ 에서 import 한다)
# ======================================================================
ORDERS = {"A-1": "배송 중", "A-2": "배송 완료"}


@tool
def lookup_order(order_id: str) -> str:
    """주문 상태를 조회한다."""
    return ORDERS.get(order_id, "주문 없음")


@tool
def refund_order(order_id: str, reason: str) -> str:
    """주문을 환불한다. (위험한 쓰기 작업)"""
    return f"{order_id} 환불 완료"


def build_agent(model: Any, *, checkpointer: Any = None, hitl: bool = False):
    """의존성(모델, 체크포인터)을 주입받는 팩토리 — 테스트 가능한 설계의 핵심."""
    middleware = [HumanInTheLoopMiddleware(interrupt_on={"refund_order": True})] if hitl else []
    return create_agent(
        model,
        tools=[lookup_order, refund_order],
        system_prompt="너는 쇼핑몰 상담원이다.",
        middleware=middleware,
        checkpointer=checkpointer,
    )


class TriageState(MessagesState):
    category: str


def classify(state: TriageState) -> dict[str, str]:
    """키워드 기반 1차 분류 노드 (순수 함수)."""
    text = state["messages"][-1].content
    if "환불" in text:
        return {"category": "refund"}
    if "배송" in text or "주문" in text:
        return {"category": "order"}
    return {"category": "general"}


def route(state: TriageState) -> Literal["refund_desk", "order_desk", "__end__"]:
    """조건부 엣지 라우팅 함수."""
    return {"refund": "refund_desk", "order": "order_desk"}.get(state["category"], END)


def build_triage_graph():
    g = StateGraph(TriageState)
    g.add_node("classify", classify)
    g.add_node("refund_desk", lambda s: {"messages": [AIMessage("환불 데스크 연결")]})
    g.add_node("order_desk", lambda s: {"messages": [AIMessage("주문 데스크 연결")]})
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route)
    g.add_edge("refund_desk", END)
    g.add_edge("order_desk", END)
    return g.compile()


# ======================================================================
# 테스트 (pytest 라면 이 함수들을 tests/test_agent.py 에 두면 된다)
# ======================================================================
def test_classify_node_is_pure_function():
    out = classify({"messages": [HumanMessage("환불하고 싶어요")], "category": ""})
    assert out == {"category": "refund"}


def test_route_function_maps_categories():
    assert route({"messages": [], "category": "order"}) == "order_desk"
    assert route({"messages": [], "category": "general"}) == END


def test_triage_graph_visits_expected_nodes():
    graph = build_triage_graph()
    visited = [node for update in graph.stream({"messages": [HumanMessage("배송 언제 와요?")]},
                                               stream_mode="updates") for node in update]
    assert visited == ["classify", "order_desk"], visited


def test_agent_calls_lookup_with_correct_args():
    model = ScriptedChatModel(responses=[
        tool_call("lookup_order", {"order_id": "A-1"}),
        AIMessage("주문 A-1은 배송 중입니다."),
    ])
    result = build_agent(model).invoke({"messages": [HumanMessage("A-1 어디쯤이에요?")]})

    # 궤적: 어떤 도구를 어떤 인자로 불렀나
    calls = [tc for m in result["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    assert [(c["name"], c["args"]) for c in calls] == [("lookup_order", {"order_id": "A-1"})]
    # 도구 결과가 실제로 실행되었나
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs[0].content == "배송 중"
    # 모델은 정확히 2번 호출되어야 한다 (도구 호출 → 최종 답변)
    assert len(model.calls) == 2


def test_model_receives_system_prompt_and_tool_result():
    model = ScriptedChatModel(responses=[tool_call("lookup_order", {"order_id": "A-2"}), AIMessage("완료")])
    build_agent(model).invoke({"messages": [HumanMessage("A-2 상태?")]})
    second_call = model.calls[1]
    assert second_call[0].type == "system" and "상담원" in second_call[0].content
    assert any(isinstance(m, ToolMessage) and m.content == "배송 완료" for m in second_call)


def test_refund_requires_human_approval():
    model = ScriptedChatModel(responses=[tool_call("refund_order", {"order_id": "A-1", "reason": "변심"})])
    agent = build_agent(model, checkpointer=InMemorySaver(), hitl=True)
    out = agent.invoke({"messages": [HumanMessage("A-1 환불")]}, {"configurable": {"thread_id": "t"}})
    assert "__interrupt__" in out, "환불은 반드시 사람 승인에서 멈춰야 한다"
    # 승인 전에는 도구가 실행되지 않았어야 한다
    assert not any(isinstance(m, ToolMessage) for m in out["messages"])


if __name__ == "__main__":
    print("=" * 70 + "\n에이전트 단위 테스트 실행\n" + "=" * 70)
    passed, failed = run_tests([
        test_classify_node_is_pure_function,
        test_route_function_maps_categories,
        test_triage_graph_visits_expected_nodes,
        test_agent_calls_lookup_with_correct_args,
        test_model_receives_system_prompt_and_tool_result,
        test_refund_requires_human_approval,
    ])
    assert failed == 0
