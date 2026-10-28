"""실습: 배송비 계산 도구와 도구 실행기 만들기

1. calculate_shipping 도구를 완성하세요.
   - 인자: weight_kg: float, region: Literal["domestic", "jeju", "overseas"]
   - docstring 에 '무엇을 하는지'를 쓰세요 (모델이 읽는 설명입니다)
   - 요금: 기본 3000원 + kg당 1000원, jeju 는 +3000원, overseas 는 ×5
2. execute_tool_calls(ai_message, tools) 를 완성하세요.
   - ai_message.tool_calls 하나당 ToolMessage 하나를 만들어 리스트로 반환
   - 모르는 도구 이름이면 ToolMessage(status="error") 를 반환 (예외로 죽지 않기!)
   - tool_call_id 는 반드시 요청의 id 와 같아야 합니다
3. 모델에 도구를 바인딩하고, 한 바퀴(요청 → 실행 → 최종 답변)를 돌리세요.
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


# 1. 도구 정의
@tool
def calculate_shipping(weight_kg: float, region: str) -> int:
    """TODO: 이 도구가 무엇을 하는지 한 문장으로 쓰세요."""
    # TODO: region 타입을 Literal["domestic", "jeju", "overseas"] 로 바꾸고, docstring 을 추가하세요.
    # TODO: 기본 3000원 + kg당 1000원, jeju +3000원, overseas ×5 규칙으로 계산하세요.
    return 0


# 2. 도구 실행기
def execute_tool_calls(ai_message: AIMessage, tools: list) -> list[ToolMessage]:
    tools_by_name = {t.name: t for t in tools}
    results: list[ToolMessage] = []
    for call in ai_message.tool_calls:
        # TODO: tools_by_name 에서 도구를 찾고,
        #   - 없으면 ToolMessage(..., tool_call_id=call["id"], status="error") 를 추가
        #   - 있으면 t.invoke(call) 결과(ToolMessage)를 추가
        pass
    return results


# 3. 한 바퀴 돌리기
tools = [calculate_shipping]
# TODO: llm 에 tools 를 바인딩하세요.
llm_with_tools = llm
messages: list = [HumanMessage("3 kg 상자를 보내려고 해. 배송비를 계산한다면 얼마야?")]
ai = llm_with_tools.invoke(messages)
messages.append(ai)
messages.extend(execute_tool_calls(ai, tools))
final = llm_with_tools.invoke(messages)
for m in messages + [final]:
    m.pretty_print()

# ------------------------------------------------------------------ 자가 채점
spec = convert_to_openai_tool(calculate_shipping)["function"]
assert spec["description"].strip() and "TODO" not in spec["description"], "docstring(설명)을 작성하세요"
assert spec["parameters"]["properties"]["region"]["enum"] == ["domestic", "jeju", "overseas"], "region 은 Literal 이어야 합니다"
assert calculate_shipping.invoke({"weight_kg": 2, "region": "domestic"}) == 5000
assert calculate_shipping.invoke({"weight_kg": 2, "region": "jeju"}) == 8000
assert calculate_shipping.invoke({"weight_kg": 2, "region": "overseas"}) == 25000

fake = AIMessage(
    content="",
    tool_calls=[
        {"name": "calculate_shipping", "args": {"weight_kg": 1, "region": "domestic"}, "id": "c1", "type": "tool_call"},
        {"name": "no_such_tool", "args": {}, "id": "c2", "type": "tool_call"},
    ],
)
outs = execute_tool_calls(fake, tools)
assert [o.tool_call_id for o in outs] == ["c1", "c2"], "tool_call_id 가 요청 id 와 같아야 합니다"
assert outs[0].content == "4000" and outs[1].status == "error", "정상 실행 / 모르는 도구 오류 처리를 확인하세요"

assert ai.tool_calls, "모델이 도구를 호출해야 합니다 (bind_tools 를 확인하세요)"
assert sum(isinstance(m, ToolMessage) for m in messages) == len(ai.tool_calls), "tool call 마다 ToolMessage 가 필요합니다"
assert isinstance(final, AIMessage) and final.text, "최종 답변이 있어야 합니다"
print("✅ 모든 테스트 통과!")
