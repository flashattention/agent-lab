"""메시지 타입과 AIMessage 해부.

- System/Human/AI/Tool 네 가지 메시지를 만들어 본다
- 모델을 호출하고 AIMessage의 주요 필드를 확인한다
- 답변을 대화 기록에 붙여 두 번째 턴을 이어간다 (LLM은 기억이 없다!)
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)  # temperature는 설정하지 않는다 (GPT-5 추론 모델은 거부함)


def section(title: str) -> None:
    """출력을 읽기 쉽게 구분선을 찍는다."""
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 메시지 만들기
section("1. 네 가지 메시지 타입")
system = SystemMessage("너는 친절한 여행 플래너다. 한국어로 두 문장 이내로 답한다.")
human = HumanMessage("부산 1박 2일 여행 코스를 추천해 줘.")

# AIMessage와 ToolMessage는 보통 모델/프로그램이 만들지만, 테스트를 위해 손으로 만들 수도 있다.
fake_ai = AIMessage(
    content="",
    tool_calls=[{"name": "get_weather", "args": {"city": "부산"}, "id": "call_001", "type": "tool_call"}],
)
fake_tool = ToolMessage(content="부산: 맑음, 21도", tool_call_id="call_001")  # 반드시 id가 짝을 이룬다

for m in [system, human, fake_ai, fake_tool]:
    # .type 은 LangChain 내부 타입 이름 (system/human/ai/tool)
    print(f"{type(m).__name__:<14} type={m.type:<6} content={m.content!r}")

# 딕셔너리 형식도 같은 의미다 (OpenAI 스타일 role 이름 사용)
dict_messages = [
    {"role": "system", "content": system.content},
    {"role": "user", "content": human.content},
]

# ---------------------------------------------------------------- 2. 모델 호출
section("2. 모델 호출과 AIMessage 해부")
history: list = [system, human]
ai = llm.invoke(history)
ai.pretty_print()

print("text              :", ai.text[:60], "...")
print("tool_calls        :", ai.tool_calls)
print("usage_metadata    :", ai.usage_metadata)  # 비용 계산의 기본 재료
print("response_metadata :", ai.response_metadata)
print("id                :", ai.id)

# 딕셔너리 형식으로 보내도 똑같이 AIMessage가 돌아온다
same_type = llm.invoke(dict_messages)
print("dict 입력 결과 타입:", type(same_type).__name__)

# ---------------------------------------------------------------- 3. 두 번째 턴
section("3. 대화 기록을 들고 다니기")
history.append(ai)  # 모델 답변을 기록에 남겨야 다음 턴에서 '기억'한다
history.append(HumanMessage("그중 첫째 날 저녁 맛집만 다시 알려줘."))
ai2 = llm.invoke(history)
history.append(ai2)

for m in history:
    m.pretty_print()

print(f"\n총 메시지 수: {len(history)}  (턴이 늘수록 입력 토큰도 늘어난다)")
print("2턴 입력 토큰:", ai2.usage_metadata["input_tokens"], "> 1턴 입력 토큰:", ai.usage_metadata["input_tokens"])
