"""순수 Python while 루프로 만든 ReAct 에이전트.

- 종료 조건 ①: 모델이 더 이상 도구를 부르지 않음 (정상 종료)
- 종료 조건 ②: max_iterations 도달 (안전장치)
- 알 수 없는 도구 / 도구 예외를 '관찰'로 돌려줘 모델이 복구할 기회를 준다.
"""

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import BaseTool, tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

SYSTEM_PROMPT = (
    "너는 여행 도우미다. 날씨가 필요하면 get_weather, 환율이 필요하면 convert_currency를 사용해라. "
    "필요한 정보를 모두 모았으면 한국어로 간결하게 답해라."
)


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    fake_db = {"서울": "맑음, 22도", "부산": "흐림, 19도", "도쿄": "비, 17도"}
    return f"{city}: {fake_db.get(city, '정보 없음')}"


@tool
def convert_currency(amount: float, rate: float) -> str:
    """금액(amount)에 환율(rate)을 곱해 환전 금액을 계산합니다."""
    if rate <= 0:
        # 예외를 던지면 루프가 잡아서 ToolMessage로 모델에게 돌려준다.
        raise ValueError("환율은 0보다 커야 합니다.")
    return f"{amount * rate:,.0f}"


TOOLS: list[BaseTool] = [get_weather, convert_currency]
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in TOOLS}


def execute_tool_call(call: dict[str, Any]) -> ToolMessage:
    """tool_call 하나를 실행하고, 성공이든 실패든 ToolMessage로 돌려준다."""
    tool_fn = TOOLS_BY_NAME.get(call["name"])
    if tool_fn is None:
        content = f"Error: '{call['name']}' 도구는 없습니다. 사용 가능: {list(TOOLS_BY_NAME)}"
        status = "error"
    else:
        try:
            content = str(tool_fn.invoke(call["args"]))
            status = "success"
        except Exception as e:  # 도구 실패도 하나의 '관찰'이다
            content = f"Error: {type(e).__name__}: {e}"
            status = "error"
    return ToolMessage(content=content, tool_call_id=call["id"], name=call["name"], status=status)


def run_agent(question: str, max_iterations: int = 5) -> dict[str, Any]:
    """ReAct 루프를 실행하고 답변·단계 수·종료 이유를 반환한다."""
    llm_with_tools = init_chat_model(MODEL).bind_tools(TOOLS)
    messages: list[Any] = [SystemMessage(SYSTEM_PROMPT), HumanMessage(question)]
    total_tokens = 0

    for step in range(1, max_iterations + 1):  # 상한을 구조적으로 강제
        print(f"\n── step {step} ─────────────────────────────")
        ai: AIMessage = llm_with_tools.invoke(messages)
        messages.append(ai)
        if ai.usage_metadata:
            total_tokens += ai.usage_metadata["total_tokens"]

        if not ai.tool_calls:  # 종료 조건 ①
            print("   [Final] 모델이 도구 없이 답했습니다 → 종료")
            return {"answer": ai.content, "steps": step, "stopped": "final_answer",
                    "messages": messages, "tokens": total_tokens}

        for call in ai.tool_calls:  # 병렬 요청이 올 수 있으니 전부 처리
            print(f"   [Action] {call['name']}({call['args']})")
            observation = execute_tool_call(call)
            print(f"   [Observation:{observation.status}] {observation.content}")
            messages.append(observation)

    print("\n   [Stop] max_iterations 도달 → 강제 종료")  # 종료 조건 ②
    return {"answer": None, "steps": max_iterations, "stopped": "max_iterations",
            "messages": messages, "tokens": total_tokens}


if __name__ == "__main__":
    for limit in (5, 1):
        print("\n" + "=" * 60)
        print(f"max_iterations={limit}")
        print("=" * 60)
        result = run_agent("도쿄 날씨 알려주고, 100달러를 환율 1400으로 환전하면 얼마야?", max_iterations=limit)
        print("\n결과 요약")
        print("  종료 이유 :", result["stopped"])
        print("  단계 수   :", result["steps"])
        print("  누적 토큰 :", result["tokens"])
        print("  답변      :", result["answer"])

    # 알 수 없는 도구를 모델이 지어냈을 때의 처리 확인
    print("\n" + "=" * 60)
    print("환각된 도구 이름 처리")
    fake_call = {"name": "book_flight", "args": {"to": "도쿄"}, "id": "call_fake"}
    print(" ", execute_tool_call(fake_call).content)
