"""도구 호출 한 바퀴: bind_tools → tool_calls → 실행 → ToolMessage → 최종 답변.

- 모델이 두 도구를 한 번에(병렬로) 요청하는 상황을 처리한다
- tool call 하나당 ToolMessage 하나, tool_call_id 를 정확히 맞춘다
- 도구 오류를 ToolMessage(status="error")로 바꿔 모델에게 돌려준다
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolException, tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회한다."""
    return {"서울": "맑음 21도", "부산": "흐림 19도"}.get(city, "정보 없음")


@tool
def add(a: int, b: int) -> int:
    """두 정수를 더한다."""
    return a + b


ORDERS = {"A-1001": "배송 중", "A-1002": "배송 완료"}


@tool
def lookup_order(order_id: str) -> str:
    """주문번호로 주문 상태를 조회한다."""
    if order_id not in ORDERS:
        # 모델이 읽고 고칠 수 있도록 구체적인 오류 메시지
        raise ToolException(f"주문 {order_id!r}를 찾을 수 없습니다. 주문번호 형식은 A-0000입니다.")
    return ORDERS[order_id]


lookup_order.handle_tool_error = True  # 예외 → ToolMessage(status="error")

tools = [get_weather, add, lookup_order]
tools_by_name = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)  # 도구 스키마가 매 요청에 함께 전송된다


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 모델이 도구를 요청
section("1. 모델의 도구 호출 요청")
question = "서울의 날씨를 조회하고 12와 30을 더한다"
messages: list = [HumanMessage(question)]
ai = llm_with_tools.invoke(messages)
messages.append(ai)
print("텍스트 내용:", repr(ai.text))  # 도구를 부를 때는 보통 비어 있다
for call in ai.tool_calls:
    print(f"  요청: {call['name']}({call['args']})  id={call['id']}")

# ---------------------------------------------------------------- 2. 우리 코드가 실행
section("2. 도구 실행 → ToolMessage")
for call in ai.tool_calls:
    tool_fn = tools_by_name.get(call["name"])
    if tool_fn is None:  # 모델이 없는 도구를 지어낼 수도 있다 → 오류로 응답
        messages.append(ToolMessage(f"알 수 없는 도구: {call['name']}", tool_call_id=call["id"], status="error"))
        continue
    tool_msg = tool_fn.invoke(call)  # ToolCall 을 통째로 넘기면 ToolMessage 가 나온다
    messages.append(tool_msg)
    print(f"  {tool_msg.name} → {tool_msg.content!r} (tool_call_id={tool_msg.tool_call_id})")

# 모든 tool call 에 대응하는 ToolMessage 가 있는지 확인 (없으면 API 400 에러)
requested = {c["id"] for c in ai.tool_calls}
answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
assert requested == answered, "tool call 과 ToolMessage 의 짝이 맞지 않습니다"

# ---------------------------------------------------------------- 3. 결과를 보고 최종 답변
section("3. 최종 답변")
final = llm_with_tools.invoke(messages)
final.pretty_print()

# ---------------------------------------------------------------- 4. 도구 오류 처리
section("4. 도구 오류도 ToolMessage 로")
bad_call = {"name": "lookup_order", "args": {"order_id": "1001"}, "id": "call_bad", "type": "tool_call"}
err_msg = lookup_order.invoke(bad_call)
print(f"status={err_msg.status}, content={err_msg.content}")
print("→ 모델은 이 메시지를 읽고 'A-1001'로 고쳐 다시 호출할 수 있다.")

# ---------------------------------------------------------------- 5. tool_choice 로 강제하기
section("5. tool_choice 로 특정 도구 강제")
forced = llm.bind_tools(tools, tool_choice="lookup_order").invoke("주문 A-1002 어떻게 됐어?")
print("강제 호출:", [(c["name"], c["args"]) for c in forced.tool_calls])
