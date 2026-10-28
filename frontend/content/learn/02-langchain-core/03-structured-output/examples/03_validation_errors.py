"""검증 실패를 감지하고 재시도 → 상한 → 대체값으로 처리하기.

Pydantic field_validator 로 비즈니스 규칙(이메일에 @ 포함, 전화번호 형식)을 걸어 둔다.
Mock 모델은 '(mock) email' 같은 더미 값을 채우므로 실제로 검증 실패가 발생한다.
(실제 모델에서는 대부분 첫 시도에 성공하지만, 실패 처리 코드는 반드시 있어야 한다.)
"""

import os
import re

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
MAX_ATTEMPTS = 2  # 재시도 상한: 무한 루프는 비용 폭탄!


class Contact(BaseModel):
    """명함/서명에서 추출한 연락처."""

    name: str = Field(description="이름")
    email: str = Field(description="이메일 주소")
    phone: str | None = Field(None, description="전화번호, 형식 010-0000-0000. 없으면 null")

    @field_validator("email")
    @classmethod
    def email_must_have_at(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError(f"올바른 이메일이 아닙니다: {v!r}")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"01\d-\d{3,4}-\d{4}", v):
            raise ValueError(f"전화번호 형식이 아닙니다: {v!r}")
        return v


# ---------------------------------------------------------------- 0. 기본 동작: 예외
print("=" * 12, "0. include_raw 없이", "=" * 12)
try:
    Contact.model_validate({"name": "홍길동", "email": "hong.example.com"})
except ValidationError as e:
    print("ValidationError 발생 →", e.errors()[0]["msg"])

# ---------------------------------------------------------------- 1. 재시도 루프
extractor = llm.with_structured_output(Contact, include_raw=True)


def extract_contact(text: str) -> tuple[Contact | None, list[str]]:
    """연락처를 추출한다. 실패하면 오류를 모델에게 알려 주고 재시도한다."""
    messages: list = [
        SystemMessage("텍스트에서 연락처를 추출한다. 없는 정보는 지어내지 않는다."),
        HumanMessage(text),
    ]
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = extractor.invoke(messages)
        if result["parsing_error"] is None:
            print(f"  시도 {attempt}: 성공")
            return result["parsed"], errors

        err = str(result["parsing_error"]).splitlines()[1:3]  # 핵심 줄만
        errors.append(" / ".join(s.strip() for s in err))
        print(f"  시도 {attempt}: 검증 실패 → {errors[-1][:70]}")
        # 오류 피드백: 이전 출력과 오류 내용을 대화에 붙여 고쳐 달라고 요청
        raw: AIMessage = result["raw"]
        messages += [
            AIMessage(content=str(raw.tool_calls[0]["args"] if raw.tool_calls else raw.text)),
            HumanMessage(f"이전 출력이 검증에 실패했습니다: {errors[-1]}\n오류를 고쳐 다시 추출하세요."),
        ]
    return None, errors


print("\n" + "=" * 12, "1. 추출 + 재시도", "=" * 12)
contact, errors = extract_contact("감사합니다. 김민수 드림 / minsu@agentlab.dev / 010-1234-5678")

# ---------------------------------------------------------------- 2. 우아한 실패
print("\n" + "=" * 12, "2. 결과 처리", "=" * 12)
review_queue: list[dict] = []
if contact is None:
    # 끝내 실패: 안전한 대체값 + 사람 검토 큐로 보내기
    review_queue.append({"reason": "extraction_failed", "errors": errors})
    print(f"{MAX_ATTEMPTS}회 모두 실패 → 사람 검토 큐에 등록 (대기 {len(review_queue)}건)")
else:
    print("추출 성공:", contact)
