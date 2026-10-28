"""도구 호출 1회 왕복을 손으로 처리하기.

흐름: 질문 → 모델이 tool_calls 요청 → 우리가 도구 실행 → ToolMessage 전달 → 최종 답변
API 키가 없으면 Mock 모델이 응답합니다(흐름은 동일).
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    # 실제 서비스라면 날씨 API를 호출하겠지만, 여기서는 고정된 가짜 데이터를 씁니다.
    fake_db = {"서울": "맑음, 22도", "부산": "흐림, 19도"}
    return f"{city}: {fake_db.get(city, '정보 없음')}"


def main() -> None:
    llm = init_chat_model(MODEL)
    # bind_tools: 모델에게 '이런 도구를 쓸 수 있다'는 메뉴판(JSON 스키마)을 붙인다.
    llm_with_tools = llm.bind_tools([get_weather])

    messages = [
        SystemMessage("너는 날씨 비서다. 필요하면 도구를 사용해라."),
        HumanMessage("서울 날씨 어때?"),
    ]

    print("=" * 60)
    print("① 모델 호출: 무엇을 할지 결정")
    ai: AIMessage = llm_with_tools.invoke(messages)
    messages.append(ai)
    print("   tool_calls =", ai.tool_calls)

    print("=" * 60)
    print("② 도구 실행: 실제 실행은 '우리 코드'가 한다")
    for call in ai.tool_calls:
        result = get_weather.invoke(call["args"])
        print(f"   {call['name']}({call['args']}) -> {result}")
        # tool_call_id로 '어떤 요청에 대한 응답인지'를 연결한다(필수).
        messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

    print("=" * 60)
    print("③ 관찰 결과를 보고 최종 답변")
    final = llm_with_tools.invoke(messages)
    messages.append(final)

    print("=" * 60)
    print("전체 메시지 기록 (이것이 에이전트의 작업 기억입니다)")
    for m in messages:
        m.pretty_print()


if __name__ == "__main__":
    main()
