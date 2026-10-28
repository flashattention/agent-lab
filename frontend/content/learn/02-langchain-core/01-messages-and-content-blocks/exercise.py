"""실습: 메시지와 콘텐츠 블록 다루기

고객지원 챗봇의 기초 부품 세 가지를 만듭니다.

1. build_history(system_rule, turns)
   - SystemMessage 하나로 시작하고, (사용자, 상담원) 튜플마다 HumanMessage와 AIMessage를 차례로 붙인 리스트를 반환
2. make_image_question(question, image_b64)
   - text 블록 + image 블록(base64, mime_type="image/png") 두 개로 이루어진 HumanMessage를 반환
3. count_blocks(message)
   - message.content_blocks 를 이용해 {블록 type: 개수} 딕셔너리를 반환

마지막으로 대화 기록에 이미지 질문을 붙여 모델을 호출하고, 답변을 기록에 추가합니다.
"""

import base64
import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def build_history(system_rule: str, turns: list[tuple[str, str]]) -> list:
    """시스템 규칙 + 과거 대화 턴으로 메시지 리스트를 만든다."""
    history: list = []
    # TODO: SystemMessage(system_rule)로 시작하세요.
    # TODO: turns 의 (user_text, ai_text)마다 HumanMessage, AIMessage 를 차례로 append 하세요.
    return history


def make_image_question(question: str, image_b64: str) -> HumanMessage:
    """텍스트 질문과 PNG 이미지(base64)를 담은 멀티모달 메시지를 만든다."""
    # TODO: content 에 블록 두 개를 담은 HumanMessage 를 반환하세요.
    #   1) {"type": "text", ...}  2) {"type": "image", "base64": ..., "mime_type": "image/png"}
    return HumanMessage(content=[])


def count_blocks(message) -> dict[str, int]:
    """표준 content_blocks 를 type 별로 센다."""
    counts: dict[str, int] = {}
    # TODO: message.content_blocks 를 순회하며 block["type"] 별 개수를 세세요.
    return counts


# ------------------------------------------------------------------ 실행
history = build_history(
    "너는 전자제품 쇼핑몰의 상담원이다. 한국어로 짧게 답한다.",
    [("배송은 얼마나 걸리나요?", "보통 2~3일 걸립니다."), ("반품도 되나요?", "수령 후 7일 이내 가능합니다.")],
)
image_b64 = base64.b64encode(b"\x89PNG fake broken-screen photo").decode()
question = make_image_question("화면이 이렇게 깨졌는데 교환되나요?", image_b64)
history.append(question)

# TODO: history 전체로 모델을 호출하고, 답변(AIMessage)을 history 에 추가하세요.
answer = None

for m in history:
    print(f"{m.type:>6}: {count_blocks(m)}")

# ------------------------------------------------------------------ 자가 채점
assert isinstance(history[0], SystemMessage), "첫 메시지는 SystemMessage여야 합니다"
assert [m.type for m in history[1:5]] == ["human", "ai", "human", "ai"], "과거 턴이 순서대로 들어가야 합니다"
assert count_blocks(question) == {"text": 1, "image": 1}, "질문은 text 1개 + image 1개 블록이어야 합니다"
assert question.content_blocks[1]["mime_type"] == "image/png", "base64 이미지는 mime_type이 필요합니다"
assert isinstance(answer, AIMessage) and history[-1] is answer, "모델 답변을 기록에 추가해야 합니다"
assert count_blocks(answer).get("text", 0) >= 1, "답변에는 text 블록이 있어야 합니다"
assert answer.usage_metadata["input_tokens"] > 0, "usage_metadata로 토큰 사용량을 확인할 수 있어야 합니다"
print("✅ 모든 테스트 통과!")
