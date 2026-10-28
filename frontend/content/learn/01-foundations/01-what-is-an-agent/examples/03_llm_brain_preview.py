"""미리 보기: 같은 에이전트 루프에서 '두뇌'만 LLM으로 교체한다.

- 도구 정의(@tool), bind_tools, tool_calls, ToolMessage 는 2.4 / 3.1 에서 자세히 배운다.
- API 키가 없으면 Mock 모델이 응답한다. 내용보다 '흐름'에 집중하자.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_weather(city: str) -> str:
    """도시(city)의 현재 날씨와 강수확률을 조회한다."""
    fake = {"서울": "흐림, 강수확률 80%", "부산": "맑음, 강수확률 10%"}
    return fake.get(city, "정보 없음")


TOOLS = {t.name: t for t in [get_weather]}


def run_llm_agent(question: str, max_steps: int = 4) -> str:
    # 두뇌: 도구 목록을 알고 있는 채팅 모델
    llm = init_chat_model(MODEL).bind_tools(list(TOOLS.values()))
    # 상태: 대화 메시지 리스트 (LangChain/LangGraph 에이전트의 표준 상태 형태)
    messages = [
        SystemMessage("너는 여행 도우미야. 필요하면 도구를 써서 사실을 확인한 뒤 짧게 답해."),
        HumanMessage(question),
    ]
    for step in range(1, max_steps + 1):  # 반복 상한
        ai: AIMessage = llm.invoke(messages)  # Reason
        messages.append(ai)
        if not ai.tool_calls:  # 종료 조건: 더 이상 도구를 부르지 않음
            print(f"[step {step}] 최종 답변 생성")
            return ai.text
        for call in ai.tool_calls:  # Act: LLM이 고른 도구 실행
            result = TOOLS[call["name"]].invoke(call["args"])
            print(f"[step {step}] 🔧 {call['name']}({call['args']}) → {result}")
            # Perceive: 결과를 ToolMessage 로 대화에 추가 → 다음 턴에 LLM이 본다
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    return "최대 반복 횟수에 도달했습니다."


if __name__ == "__main__":
    print("=" * 60)
    answer = run_llm_agent("서울 날씨 보고 우산 챙길지 알려줘")
    print("=" * 60)
    print("💬", answer)
