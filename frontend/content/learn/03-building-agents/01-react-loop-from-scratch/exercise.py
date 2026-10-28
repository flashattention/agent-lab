"""실습: 나만의 ReAct 루프 완성하기

여러분은 사내 '주문 도우미' 에이전트의 핵심 루프를 직접 구현합니다.
아래 TODO 4곳을 채우세요.

  TODO ① 모델에 도구 목록을 바인딩하기 (bind_tools)
  TODO ② 종료 조건: 모델 응답에 tool_calls가 없으면 결과를 반환하기
  TODO ③ 도구 실행 결과를 ToolMessage로 만들기 (tool_call_id 필수!)
  TODO ④ 존재하지 않는 도구 이름이면 status="error"인 ToolMessage 돌려주기

채점 기준(Mock 모드에서도 통과해야 함)
- 정상 실행 시 stopped == "final_answer" 이고 ToolMessage가 1개 이상 있다
- 모든 ToolMessage의 tool_call_id가 직전 AIMessage의 tool_call id와 짝이 맞는다
- max_iterations=1 이면 stopped == "max_iterations" 로 끝난다
- 모르는 도구 호출은 예외 대신 status="error" ToolMessage가 된다
"""

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import BaseTool, tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_order_status(order_id: str) -> str:
    """주문 번호로 주문의 배송 상태를 조회합니다."""
    fake_orders = {"A-100": "배송 중", "A-200": "배송 완료"}
    return f"{order_id}: {fake_orders.get(order_id, '주문 없음')}"


@tool
def calculate_refund(price: float, days_used: int) -> str:
    """상품 가격(price)과 사용 일수(days_used)로 환불 금액을 계산합니다."""
    rate = 1.0 if days_used <= 7 else 0.5
    return f"환불 금액: {price * rate:,.0f}원"


TOOLS: list[BaseTool] = [get_order_status, calculate_refund]
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in TOOLS}


def execute_tool_call(call: dict[str, Any]) -> ToolMessage:
    """tool_call 하나를 실행해 ToolMessage로 돌려준다. 실패해도 예외를 던지지 않는다."""
    tool_fn = TOOLS_BY_NAME.get(call["name"])
    if tool_fn is None:
        # TODO ④: 알 수 없는 도구 → status="error" 인 ToolMessage를 반환하세요.
        raise NotImplementedError("TODO ④: 알 수 없는 도구 처리를 구현하세요")
    try:
        content = str(tool_fn.invoke(call["args"]))
        status = "success"
    except Exception as e:
        content = f"Error: {type(e).__name__}: {e}"
        status = "error"
    # TODO ③: content, status, call["id"]를 사용해 ToolMessage를 만들어 반환하세요.
    raise NotImplementedError(f"TODO ③: ToolMessage를 만드세요 (content={content!r}, status={status})")


def run_agent(question: str, max_iterations: int = 5) -> dict[str, Any]:
    """ReAct 루프. {'answer', 'steps', 'stopped', 'messages'}를 반환한다."""
    # TODO ①: init_chat_model(MODEL)에 TOOLS를 바인딩하세요.
    llm_with_tools = None
    if llm_with_tools is None:
        raise NotImplementedError("TODO ①: bind_tools로 도구를 바인딩하세요")

    messages: list[Any] = [
        SystemMessage("너는 쇼핑몰 주문 도우미다. 도구로 사실을 확인한 뒤 답해라."),
        HumanMessage(question),
    ]
    for step in range(1, max_iterations + 1):
        ai: AIMessage = llm_with_tools.invoke(messages)
        messages.append(ai)

        # TODO ②: ai.tool_calls가 비어 있으면
        #         {"answer": ai.content, "steps": step, "stopped": "final_answer", "messages": messages}
        #         를 반환하세요.

        for call in ai.tool_calls:
            messages.append(execute_tool_call(call))

    return {"answer": None, "steps": max_iterations, "stopped": "max_iterations", "messages": messages}


# ───────────────────────── 자가 채점 ─────────────────────────
if __name__ == "__main__":
    result = run_agent("주문 A-100 배송 상태 알려줘", max_iterations=5)
    msgs = result["messages"]
    tool_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
    print("종료 이유:", result["stopped"], "| 단계:", result["steps"])
    print("답변:", result["answer"])

    assert result["stopped"] == "final_answer", "도구 결과를 받은 뒤에는 정상 종료해야 합니다 (TODO ②)"
    assert len(tool_msgs) >= 1, "도구가 한 번 이상 실행되어야 합니다"

    requested_ids = {c["id"] for m in msgs if isinstance(m, AIMessage) for c in m.tool_calls}
    assert all(t.tool_call_id in requested_ids for t in tool_msgs), "tool_call_id 짝이 맞지 않습니다 (TODO ③)"

    capped = run_agent("주문 A-200 배송 상태 알려줘", max_iterations=1)
    assert capped["stopped"] == "max_iterations" and capped["steps"] == 1, "반복 상한이 지켜지지 않았습니다"

    bad = execute_tool_call({"name": "cancel_everything", "args": {}, "id": "call_x"})
    assert isinstance(bad, ToolMessage) and bad.status == "error", "모르는 도구는 error ToolMessage여야 합니다 (TODO ④)"
    assert bad.tool_call_id == "call_x"

    print("✅ 모든 테스트 통과!")
