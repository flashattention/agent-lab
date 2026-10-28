"""표준 콘텐츠 블록(content_blocks) 다루기.

- 제공자마다 다른 '원본 content' 형식이 content_blocks에서 같은 모양으로 통일되는 것을 확인한다
- 블록 type 별로 분기하는 제공자 독립적인 렌더링 함수를 만든다
- 이미지/PDF 멀티모달 입력 메시지를 표준 블록으로 만들어 모델에 보낸다
"""

import base64
import os
from collections import Counter

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage
from langchain_core.messages.content import create_file_block, create_image_block, create_text_block

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 제공자별 원본 형식
section("1. 제공자마다 다른 원본 content")

# Anthropic 스타일: 'thinking' 블록
anthropic_style = AIMessage(
    content=[
        {"type": "thinking", "thinking": "사용자는 환불 규정을 묻고 있다.", "signature": "sig"},
        {"type": "text", "text": "구매 후 7일 이내라면 환불됩니다."},
    ],
    response_metadata={"model_provider": "anthropic"},
)

# OpenAI Responses API 스타일: 'reasoning' + summary 리스트
openai_style = AIMessage(
    content=[
        {"type": "reasoning", "id": "rs_1", "summary": [{"type": "summary_text", "text": "환불 규정 확인 필요."}]},
        {"type": "text", "text": "구매 후 7일 이내라면 환불됩니다.", "annotations": []},
    ],
    response_metadata={"model_provider": "openai"},
)

# 표준 블록으로 직접 만든 메시지 + tool_calls → content_blocks 에 tool_call 블록이 함께 나온다
standard_style = AIMessage(
    content=[
        {"type": "reasoning", "reasoning": "주문 상태를 먼저 조회해야 한다."},
        {"type": "text", "text": "주문을 확인해 볼게요."},
    ],
    tool_calls=[{"name": "lookup_order", "args": {"order_id": "1234"}, "id": "call_9", "type": "tool_call"}],
)

for name, msg in [("anthropic", anthropic_style), ("openai", openai_style), ("standard", standard_style)]:
    print(f"[{name}] 원본 content 첫 블록 type :", msg.content[0]["type"])
    print(f"[{name}] content_blocks types   :", [b["type"] for b in msg.content_blocks])

# ---------------------------------------------------------------- 2. 제공자 독립 렌더러
section("2. 표준 블록으로 분기하는 렌더러")


def render(message: AIMessage) -> str:
    """어떤 제공자의 AIMessage든 같은 방식으로 화면용 문자열을 만든다."""
    lines: list[str] = []
    for block in message.content_blocks:
        kind = block["type"]
        if kind == "reasoning":
            lines.append(f"  💭 (추론 요약) {block.get('reasoning', '')}")
        elif kind == "text":
            lines.append(f"  💬 {block['text']}")
        elif kind == "tool_call":
            lines.append(f"  🔧 도구 호출: {block['name']}({block['args']})")
        else:
            lines.append(f"  ❔ 처리하지 않는 블록: {kind}")
    return "\n".join(lines)


print("anthropic 메시지:\n" + render(anthropic_style))
print("openai 메시지:\n" + render(openai_style))
print("standard 메시지:\n" + render(standard_style))
print("블록 통계:", Counter(b["type"] for b in standard_style.content_blocks))

# .text 는 텍스트 블록만 모아 준다 (추론 블록은 제외)
print("anthropic_style.text =", repr(anthropic_style.text))

# ---------------------------------------------------------------- 3. 멀티모달 입력
section("3. 이미지/PDF 입력 메시지 만들기")

# 실습용 가짜 데이터 (실제로는 파일을 읽어 base64로 인코딩한다)
fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\n...fake image bytes...").decode()
fake_pdf = base64.b64encode(b"%PDF-1.4 fake pdf").decode()

# 방법 A: 딕셔너리로 직접 작성
question_a = HumanMessage(
    content=[
        {"type": "text", "text": "이 이미지에 무엇이 보이나요?"},
        {"type": "image", "url": "https://example.com/cat.png"},
    ]
)

# 방법 B: 팩토리 함수 사용 (필수 키 누락 실수를 줄여 준다)
question_b = HumanMessage(
    content=[
        create_text_block("영수증 이미지와 계약서 PDF를 비교해 줘."),
        create_image_block(base64=fake_png, mime_type="image/png"),
        create_file_block(base64=fake_pdf, mime_type="application/pdf"),
    ]
)

for label, q in [("A", question_a), ("B", question_b)]:
    kinds = [b["type"] for b in q.content_blocks]
    print(f"질문 {label} 블록 구성: {kinds}")

# Mock 모드에서는 이미지를 '보지' 못하지만, 메시지 구조가 그대로 전달되는지 확인할 수 있다.
# (실제 모델로 실행할 때는 이미지를 지원하는 모델과 실제 이미지 데이터를 사용하세요.)
answer = llm.invoke([question_a])
print("\n모델 답변:", answer.text[:80])
