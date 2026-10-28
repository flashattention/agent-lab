"""가짜 운영 데이터 (실서비스에서는 주문 DB / CRM / CMS 에서 온다)."""

from __future__ import annotations

CUSTOMERS: dict[str, dict] = {
    "u-kim": {"name": "김하나", "tier": "VIP"},
    "u-lee": {"name": "이두리", "tier": "STANDARD"},
}

ORDERS: dict[str, dict] = {
    "A-1001": {"customer": "u-kim", "item": "노이즈캔슬링 헤드폰", "amount": 89_000, "status": "배송 완료", "days_since_delivery": 3},
    "A-1002": {"customer": "u-kim", "item": "USB-C 케이블", "amount": 12_000, "status": "배송 중", "days_since_delivery": None},
    "B-2001": {"customer": "u-lee", "item": "모니터 암", "amount": 45_000, "status": "배송 완료", "days_since_delivery": 10},
}

POLICY_DOCS: list[dict] = [
    {"id": "refund", "title": "환불 정책",
     "text": "환불 refund 정책: 상품 수령 후 7일 이내 환불 가능합니다. 단순 변심은 왕복 배송비 6,000원을 고객이 부담합니다. "
             "불량 상품은 배송비 없이 환불됩니다."},
    {"id": "shipping", "title": "배송 안내",
     "text": "배송 shipping 안내: 평일 오후 2시 이전 주문은 당일 출고, 평균 1~2일 내 도착합니다. 도서산간은 2일 추가됩니다."},
    {"id": "exchange", "title": "교환 정책",
     "text": "교환 exchange 정책: 수령 후 14일 이내 동일 상품의 다른 옵션으로 교환 가능합니다. 재고가 없으면 환불로 처리됩니다."},
    {"id": "membership", "title": "멤버십",
     "text": "멤버십 membership 안내: VIP 등급은 연간 구매 100만 원 이상 고객에게 부여되며 무료 반품과 전용 상담 혜택이 있습니다."},
]
