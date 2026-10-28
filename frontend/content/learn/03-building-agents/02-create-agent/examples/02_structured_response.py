"""response_format으로 구조화된 최종 응답 받기.

ToolStrategy: 스키마를 '가짜 도구'로 등록하고 도구 호출을 강제해 구조화 응답을 얻는다.
결과는 result["structured_response"]에 Pydantic 객체로 들어온다.
"""

import os
from typing import Literal

from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


class SupportTicket(BaseModel):
    """고객 문의에서 추출한 지원 티켓."""

    customer_name: str = Field(description="고객 이름")
    category: Literal["배송", "환불", "계정", "기타"] = Field(description="문의 분류")
    urgent: bool = Field(description="즉시 처리가 필요한지 여부")
    summary: str = Field(description="문의 내용 한 줄 요약")


def main() -> None:
    agent = create_agent(
        MODEL,
        tools=[],  # 도구 없이 '추출' 전용 에이전트
        system_prompt="고객 문의를 읽고 지원 티켓 정보를 추출해라.",
        # handle_errors=True(기본값): 스키마 검증 실패 시 오류를 알려주고 재시도
        response_format=ToolStrategy(SupportTicket, handle_errors=True),
        name="ticket_extractor",
    )

    inquiry = "안녕하세요 김민지입니다. 어제 주문한 노트북이 아직 배송이 안 됐어요. 내일 출장이라 급해요!"
    result = agent.invoke({"messages": [{"role": "user", "content": inquiry}]})

    print("=" * 60)
    print("메시지 흐름 (마지막이 ToolMessage인 점에 주목)")
    print("=" * 60)
    for m in result["messages"]:
        print(f"  {type(m).__name__:<12} | {str(m.content)[:70] or m.tool_calls[0]['name']}")

    ticket: SupportTicket = result["structured_response"]
    print("\n" + "=" * 60)
    print("structured_response")
    print("=" * 60)
    print("  타입     :", type(ticket).__name__)
    print("  JSON     :", ticket.model_dump_json(indent=None))
    print("  분류     :", ticket.category)
    print("  긴급     :", ticket.urgent)

    # 프론트엔드/다른 서비스로 그대로 넘길 수 있는 dict
    payload = ticket.model_dump()
    assert set(payload) == {"customer_name", "category", "urgent", "summary"}


if __name__ == "__main__":
    main()
