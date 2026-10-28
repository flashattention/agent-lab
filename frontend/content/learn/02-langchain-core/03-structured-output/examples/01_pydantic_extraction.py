"""Pydantic 스키마로 고객 문의에서 지원 티켓 추출하기.

- Field(description=...) 으로 모델에게 필드의 의미를 알려 준다
- Optional 로 '없을 수 있는 정보'를 표현해 환각을 줄인다
- Literal 로 범주형 값을 고정한다
- 중첩 모델(list[LineItem])로 여러 항목을 추출한다
- 프롬프트와 LCEL 로 조합해 batch 로 대량 처리한다
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


# ---------------------------------------------------------------- 스키마
class LineItem(BaseModel):
    """주문에 포함된 상품 한 줄."""

    product: str = Field(description="상품명")
    quantity: int = Field(description="수량(개). 언급이 없으면 1")


class Ticket(BaseModel):
    """고객 문의에서 추출한 지원 티켓."""

    reasoning: str = Field(description="분류 근거를 한 문장으로 (결론 필드보다 먼저 생성)")
    customer: str | None = Field(None, description="고객 이름. 텍스트에 없으면 null")
    order_id: str | None = Field(None, description="주문번호, 예: A-1234. 없으면 null")
    category: Literal["delivery", "refund", "product", "other"] = Field(description="문의 유형")
    sentiment: Literal["positive", "neutral", "negative"] = Field(description="고객 감정")
    urgent: bool = Field(description="즉시 처리가 필요하면 true")
    items: list[LineItem] = Field(default_factory=list, description="언급된 상품 목록")


# 모델에게 실제로 전달되는 JSON Schema 를 살펴보자 (설명이 모두 들어간다)
schema = Ticket.model_json_schema()
print("필드:", list(schema["properties"].keys()))
print("category 허용값:", schema["properties"]["category"]["enum"])
print("order_id 설명:", schema["properties"]["order_id"]["description"])

# ---------------------------------------------------------------- 단건 추출
print("\n" + "=" * 12, "단건 추출", "=" * 12)
extractor = llm.with_structured_output(Ticket)
email = (
    "지난주 화요일에 주문한 무선 이어폰 2개(주문번호 A-3391)가 아직 안 왔어요. "
    "너무 화나네요. 빨리 확인 부탁드립니다. — 김민지 드림"
)
ticket = extractor.invoke(email)
# Mock 모드에서는 값이 더미로 채워진다(예: 'A-3391'의 숫자를 수량으로 착각). 구조만 확인하자.
# 이런 '그럴듯하지만 틀린 값'이 바로 현업에서 사후 검증(grounding check)이 필요한 이유다.
print(type(ticket).__name__)
for key, value in ticket.model_dump().items():
    print(f"  {key:<10}: {value}")

# Pydantic 객체이므로 타입 안전하게 후속 로직을 짤 수 있다
if ticket.urgent:
    print("→ 긴급 큐로 배정합니다.")

# ---------------------------------------------------------------- 프롬프트와 조합 + batch
print("\n" + "=" * 12, "프롬프트 + batch", "=" * 12)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "너는 정확한 정보 추출기다. 텍스트에 없는 정보는 지어내지 말고 null 로 둔다."),
        ("human", "{text}"),
    ]
)
pipeline = prompt | extractor  # 결과도 Runnable 이므로 LCEL 로 이어진다

emails = [
    "환불 요청합니다. 주문 B-1020 키보드가 불량이에요.",
    "제품 너무 좋아요! 친구에게도 추천했어요.",
    "배송지 변경 가능할까요?",
]
tickets = pipeline.batch([{"text": t} for t in emails], config={"max_concurrency": 3})
for text, t in zip(emails, tickets):
    print(f"  [{t.category:<8}|{t.sentiment:<8}] {text[:30]}")

# JSON 으로 직렬화해 다른 시스템(DB, 큐)으로 보내기
print("\nJSON:", tickets[0].model_dump_json()[:120], "...")
