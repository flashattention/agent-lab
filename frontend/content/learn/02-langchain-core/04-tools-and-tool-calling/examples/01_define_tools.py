"""@tool 로 도구 정의하기 — 모델에게 보이는 '사용 설명서' 살펴보기.

모델은 함수 본문을 보지 못한다. 보는 것은 이름 / 설명 / 인자 스키마뿐이다.
세 가지 방식으로 도구를 만들고, 모델에게 전달되는 스키마를 출력해 비교한다.
"""

import json
from typing import Annotated, Literal

from langchain.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field


def show(t) -> None:
    """모델 API에 실제로 전송되는 형태(OpenAI tool 형식)로 출력한다."""
    spec = convert_to_openai_tool(t)["function"]
    print(f"\n🔧 {spec['name']}")
    print(f"   설명: {spec['description'].splitlines()[0]}")
    print("   인자:", json.dumps(spec["parameters"].get("properties", {}), ensure_ascii=False))
    print("   필수:", spec["parameters"].get("required", []))


# ---------------------------------------------------------------- 1. 가장 단순한 형태
@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회한다. 여행·옷차림 질문에 사용한다."""
    return f"{city}: 맑음, 21도"


# ---------------------------------------------------------------- 2. docstring 파싱 + Literal + 기본값
@tool(parse_docstring=True)
def search_orders(
    customer_id: str,
    status: Literal["paid", "shipped", "refunded"] = "paid",
    limit: int = 5,
) -> str:
    """고객의 주문을 검색한다.

    Args:
        customer_id: 고객 ID (예: C-1001)
        status: 주문 상태 필터
        limit: 최대 결과 수 (1~20)
    """
    return f"{customer_id}의 {status} 주문 {limit}건"


# ---------------------------------------------------------------- 3. Annotated 로 인자 설명
@tool
def convert_currency(
    amount: Annotated[float, "변환할 금액"],
    to: Annotated[Literal["USD", "JPY", "EUR"], "목표 통화"],
) -> str:
    """원화(KRW) 금액을 다른 통화로 환산한다."""
    rates = {"USD": 0.00072, "JPY": 0.11, "EUR": 0.00066}
    return f"{amount * rates[to]:.2f} {to}"


# ---------------------------------------------------------------- 4. Pydantic args_schema (검증 규칙 포함)
class RefundInput(BaseModel):
    order_id: str = Field(description="환불할 주문번호, 형식 A-0000", pattern=r"^[A-Z]-\d{4}$")
    amount: int = Field(description="환불 금액(원)", gt=0)


@tool("refund_order", args_schema=RefundInput)
def refund_order(order_id: str, amount: int) -> str:
    """주문을 환불한다. 고객이 환불을 명시적으로 요청하고 주문번호를 확인한 뒤에만 사용한다."""
    return f"{order_id} {amount}원 환불 접수"


for t in [get_weather, search_orders, convert_currency, refund_order]:
    show(t)

# ---------------------------------------------------------------- 도구는 그냥 Runnable: 직접 실행/테스트
print("\n" + "=" * 12, "직접 실행 (단위 테스트처럼)", "=" * 12)
print(get_weather.invoke({"city": "부산"}))
print(search_orders.invoke({"customer_id": "C-1001"}))  # 기본값 적용
print(convert_currency.invoke({"amount": 10000, "to": "USD"}))

# args_schema 의 검증 규칙이 동작한다 → 모델이 잘못된 인자를 넣어도 실행 전에 막힌다
try:
    refund_order.invoke({"order_id": "1234", "amount": -500})
except Exception as e:
    print("검증 실패로 실행 차단:", type(e).__name__, "-", str(e).splitlines()[0])
