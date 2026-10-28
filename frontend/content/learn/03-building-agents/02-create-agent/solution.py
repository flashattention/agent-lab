"""정답: create_agent로 쇼핑몰 상담 에이전트 만들기

두 개의 에이전트를 만듭니다.

  [A] 상담 에이전트 (도구 사용)
      TODO ① create_agent로 에이전트를 만드세요.
             - tools: get_order_status, get_return_policy
             - system_prompt: 자유롭게 작성
             - name: "support_agent"
      TODO ② stream_mode="updates"로 실행하며, 실행된 노드 이름을 visited 리스트에 순서대로 담으세요.

  [B] 리뷰 분석 에이전트 (구조화 응답)
      TODO ③ ReviewAnalysis 스키마를 ToolStrategy로 감싸 response_format에 넘기세요. (tools=[])
      TODO ④ 실행 결과에서 구조화 응답 객체를 꺼내 analysis 변수에 담으세요.

채점 기준(Mock 모드에서도 통과)
- visited에 "model"과 "tools"가 모두 있고, 마지막 노드는 "model"이다
- 최종 AIMessage.name == "support_agent"
- analysis는 ReviewAnalysis 인스턴스이고 stars는 1~5 사이 정수다
"""

import os
from typing import Literal

from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import AIMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_order_status(order_id: str) -> str:
    """주문 번호(order_id)로 주문의 배송 상태를 조회합니다."""
    return f"{order_id}: 배송 중 (내일 도착 예정)"


@tool
def get_return_policy(category: str) -> str:
    """상품 카테고리(category)별 반품 규정을 조회합니다."""
    return f"{category}: 수령 후 7일 이내 무료 반품"


class ReviewAnalysis(BaseModel):
    """상품 리뷰 분석 결과."""

    sentiment: Literal["긍정", "부정", "중립"] = Field(description="리뷰의 감정")
    stars: int = Field(ge=1, le=5, description="리뷰로 추정한 별점 1~5")
    keywords: list[str] = Field(description="리뷰의 핵심 키워드")


# ───────────── [A] 상담 에이전트 ─────────────
# ① 도구 + 시스템 프롬프트 + 이름
support_agent = create_agent(
    MODEL,
    tools=[get_order_status, get_return_policy],
    system_prompt="너는 쇼핑몰 상담원이다. 도구로 확인한 사실만 정중하게 안내해라.",
    name="support_agent",
)

visited: list[str] = []
final_messages: list = []
if support_agent is None:
    raise NotImplementedError("TODO ①: create_agent로 support_agent를 만드세요")

question = {"messages": [{"role": "user", "content": "주문 A-777 배송 상태 알려줘"}]}
for chunk in support_agent.stream(question, stream_mode="updates"):
    for node_name, update in chunk.items():
        visited.append(node_name)  # ② 실행된 노드 기록
        final_messages.extend(update.get("messages", []))

# ───────────── [B] 리뷰 분석 에이전트 ─────────────
# ③ 구조화 응답 스키마 지정
review_agent = create_agent(
    MODEL,
    tools=[],
    system_prompt="상품 리뷰를 분석해라.",
    response_format=ToolStrategy(ReviewAnalysis),
)

review = "배송은 빨랐는데 화면에 잔상이 있어서 아쉬워요. 그래도 가격 대비 괜찮습니다."
result = review_agent.invoke({"messages": [{"role": "user", "content": review}]})

# ④ 구조화 응답은 structured_response 키에 있다
analysis = result["structured_response"]

# ───────────── 자가 채점 ─────────────
print("visited:", visited)
print("analysis:", analysis)

assert "model" in visited and "tools" in visited, "model과 tools 노드를 모두 거쳐야 합니다 (TODO ②)"
assert visited[-1] == "model", "마지막 노드는 최종 답을 내는 model이어야 합니다"
last_ai = [m for m in final_messages if isinstance(m, AIMessage)][-1]
assert last_ai.name == "support_agent", "name 인자를 확인하세요 (TODO ①)"
assert isinstance(analysis, ReviewAnalysis), "structured_response를 꺼내세요 (TODO ③, ④)"
assert 1 <= analysis.stars <= 5

print("✅ 모든 테스트 통과!")
