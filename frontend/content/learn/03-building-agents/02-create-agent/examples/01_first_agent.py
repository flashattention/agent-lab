"""create_agent로 만드는 첫 에이전트.

3.1에서 직접 만든 ReAct 루프가 create_agent 한 줄로 바뀌는 것을 확인합니다.
- tools          : 에이전트가 쓸 수 있는 도구
- system_prompt  : 매 모델 호출마다 맨 앞에 붙는 지시문 (상태에는 저장되지 않음)
- name           : 이 에이전트가 만든 AIMessage.name 에 찍히는 이름
"""

import os

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, ToolMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    fake_db = {"서울": "맑음, 22도", "부산": "흐림, 19도", "도쿄": "비, 17도"}
    return f"{city}: {fake_db.get(city, '정보 없음')}"


@tool
def recommend_outfit(temperature: int) -> str:
    """기온(temperature, 섭씨)에 맞는 옷차림을 추천합니다."""
    if temperature >= 23:
        return "반팔과 얇은 바지"
    if temperature >= 17:
        return "가벼운 겉옷"
    return "두꺼운 외투"


def main() -> None:
    # 문자열 대신 인스턴스를 넘기면 timeout/max_retries 같은 세부 설정을 할 수 있다.
    llm = init_chat_model(MODEL, timeout=30, max_retries=2)

    agent = create_agent(
        llm,
        tools=[get_weather, recommend_outfit],
        system_prompt="너는 친절한 날씨 비서다. 반드시 도구로 확인한 사실만 말해라.",
        name="weather_agent",
    )

    result = agent.invoke({"messages": [{"role": "user", "content": "부산 날씨 어때?"}]})

    print("=" * 60)
    print("전체 메시지 흐름")
    print("=" * 60)
    for m in result["messages"]:
        m.pretty_print()

    # 출력 상태 분석
    msgs = result["messages"]
    ai_msgs = [m for m in msgs if isinstance(m, AIMessage)]
    tool_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
    print("\n" + "=" * 60)
    print("요약")
    print("  메시지 수       :", len(msgs))
    print("  모델 호출 수    :", len(ai_msgs))
    print("  도구 실행 수    :", len(tool_msgs))
    print("  AIMessage.name  :", ai_msgs[-1].name)  # name 인자가 여기에 찍힌다
    print("  최종 답변       :", msgs[-1].content)
    print("  시스템 프롬프트가 상태에 있나? ->", any(m.type == "system" for m in msgs))


if __name__ == "__main__":
    main()
