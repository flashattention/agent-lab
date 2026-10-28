"""실습: 영수증 문자 메시지에서 지출 내역 추출하기

카드 결제 알림 문자에서 지출 내역을 구조화된 데이터로 뽑아 가계부에 넣으려 합니다.

1. Expense 스키마(Pydantic)를 완성하세요.
   - merchant: str              (가맹점 이름)
   - amount: int                (결제 금액, 원 단위 정수)
   - category: Literal["food", "transport", "shopping", "other"]
   - memo: str | None = None    (메모, 없으면 null)
   - amount 는 0 이상이어야 합니다 → field_validator 로 검증
2. # TODO: include_raw=True 로 구조화 출력 Runnable 을 만드세요.
extractor = None
3. safe_extract(text): 최대 MAX_ATTEMPTS 번 시도하고,
   parsing_error 가 없으면 parsed 를, 모두 실패하면 None 을 반환하세요.
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field, field_validator  # noqa: F401

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
MAX_ATTEMPTS = 2


# 1. 스키마
class Expense(BaseModel):
    """카드 결제 알림에서 추출한 지출 내역."""

    merchant: str = Field(description="가맹점 이름")
    # TODO: amount(int, description 포함), category(Literal), memo(str | None, 기본값 None) 필드를 추가하세요.

    # TODO: @field_validator("amount") 로 음수 금액이면 ValueError 를 내는 검증기를 작성하세요.


# 2. 구조화 출력 Runnable
# TODO: include_raw=True 로 구조화 출력 Runnable 을 만드세요.
extractor = None


# 3. 안전한 추출 함수
def safe_extract(text: str) -> Expense | None:
    # TODO: MAX_ATTEMPTS 번까지 extractor.invoke(text) 를 시도하고,
    #       result["parsing_error"] 가 None 이면 result["parsed"] 를 반환하세요.
    return None


# ------------------------------------------------------------------ 실행
messages = [
    "[신한카드] 스타벅스 강남점 5800원 승인",
    "[KB카드] 카카오T 택시 12400원 승인",
]
expenses = [safe_extract(m) for m in messages]
for m, e in zip(messages, expenses):
    print(f"{m}\n  → {e}")

# ------------------------------------------------------------------ 자가 채점
props = Expense.model_json_schema()["properties"]
assert set(props) == {"merchant", "amount", "category", "memo"}, "스키마 필드가 올바르지 않습니다"
assert props["category"].get("enum") == ["food", "transport", "shopping", "other"], "category 는 Literal 이어야 합니다"
assert "description" in props["amount"], "amount 에 Field(description=...) 을 달아 주세요"
try:
    Expense(merchant="x", amount=-1, category="food")
    raise AssertionError("음수 금액이 검증을 통과했습니다. field_validator 를 확인하세요")
except ValueError:
    pass
assert all(isinstance(e, Expense) for e in expenses), "safe_extract 는 Expense 객체를 반환해야 합니다"
assert expenses[0].amount == 5800, "금액이 정수로 추출되어야 합니다"
print("✅ 모든 테스트 통과!")
