"""Agents-as-tools: 서브 에이전트를 '도구'로 감싸 메인 에이전트가 호출하게 만든다.

핵심 관찰 포인트
- 서브 에이전트 내부에서는 여러 메시지(도구 호출, 도구 결과, 답변)가 오간다.
- 하지만 메인 에이전트는 그중 '최종 답변 한 줄'만 ToolMessage로 받는다.
  → 이것이 컨텍스트 격리(Context Isolation)다.
"""

import os

from langchain.agents import create_agent
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# ---------------------------------------------------------------------------
# 1) 서브 에이전트: 사내 문서 검색 전문가
# ---------------------------------------------------------------------------
FAKE_DOCS = {
    "환불": "환불은 결제 후 7일 이내, 미사용 상품에 한해 가능합니다.",
    "배송": "기본 배송은 2~3 영업일이 걸립니다.",
}


@tool
def search_policy_docs(query: str) -> str:
    """사내 정책 문서(환불, 배송)를 검색한다."""
    hits = [text for key, text in FAKE_DOCS.items() if key in query]
    return "\n".join(hits) or "관련 문서를 찾지 못했습니다."


policy_agent = create_agent(
    MODEL,
    tools=[search_policy_docs],
    system_prompt="당신은 사내 정책 문서 전문가입니다. 반드시 문서를 검색한 뒤 짧게 답하세요.",
    name="policy_agent",
)

# 서브 에이전트 내부에서 몇 개의 메시지가 생겼는지 기록 (관찰용)
inner_message_counts: list[int] = []


# ---------------------------------------------------------------------------
# 2) 서브 에이전트를 도구로 감싸기
# ---------------------------------------------------------------------------
@tool
def ask_policy_expert(question: str) -> str:
    """환불, 배송 등 회사 정책 질문을 정책 전문가 에이전트에게 위임한다."""
    # 서브 에이전트는 '새 대화'로 시작한다 → 메인 대화 기록이 섞이지 않는다
    result = policy_agent.invoke(
        {"messages": [HumanMessage(question)]},
        {"recursion_limit": 10},  # 서브 에이전트도 반드시 상한을 둔다
    )
    inner_message_counts.append(len(result["messages"]))
    # 메인 에이전트에게는 최종 답변 텍스트만 돌려준다
    return result["messages"][-1].text


# ---------------------------------------------------------------------------
# 3) 메인(오케스트레이터) 에이전트
# ---------------------------------------------------------------------------
main_agent = create_agent(
    MODEL,
    tools=[ask_policy_expert],
    system_prompt="당신은 고객 상담 총괄입니다. 정책 질문은 전문가 도구에 위임하세요.",
    name="main_agent",
)

if __name__ == "__main__":
    question = "환불 정책이 궁금해요. 정책 전문가에게 확인해 주세요."
    print("=" * 60)
    print("질문:", question)
    print("=" * 60)

    result = main_agent.invoke({"messages": [HumanMessage(question)]}, {"recursion_limit": 10})

    print("\n[메인 에이전트가 본 대화]")
    for msg in result["messages"]:
        msg.pretty_print()

    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    print("\n" + "-" * 60)
    print(f"메인 에이전트 메시지 수      : {len(result['messages'])}")
    print(f"서브 에이전트 내부 메시지 수 : {inner_message_counts}")
    print(f"메인이 받은 ToolMessage 수   : {len(tool_msgs)}  (서브 에이전트의 '결과'만 전달됨)")
    names = {getattr(m, 'name', None) for m in result["messages"]}
    print("메인 대화에 search_policy_docs 흔적이 있나?", "search_policy_docs" in names)
