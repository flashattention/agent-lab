"""실습: Agents-as-tools 로 '계산 전문가' 서브 에이전트를 메인 에이전트에 붙이기

목표
1. `ask_math_expert` 도구 안에서 `math_agent`를 **새 대화**로 호출하고,
   최종 답변 텍스트만 반환하세요. (recursion_limit 로 상한을 꼭 두세요)
2. 호출될 때마다 `CALL_LOG`에 질문을 기록하세요. (관측성 연습)
3. `ask_math_expert` 도구를 가진 메인 에이전트 `main_agent`를 만드세요.

자가 채점(assert)은 Mock 모드에서도 통과하도록 '구조'만 검사합니다.
- 서브 에이전트가 정확히 1번 호출되었는가
- 메인 대화에 ask_math_expert 의 ToolMessage가 있는가
- 서브 에이전트 내부 도구(add_numbers)의 흔적이 메인 대화에 새어 나오지 않았는가
"""

import os

from langchain.agents import create_agent
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def add_numbers(a: float, b: float) -> float:
    """두 숫자를 더한다."""
    return a + b


math_agent = create_agent(
    MODEL,
    tools=[add_numbers],
    system_prompt="당신은 계산 전문가입니다. 반드시 도구로 계산하고 결과만 짧게 답하세요.",
    name="math_agent",
)

CALL_LOG: list[str] = []


@tool
def ask_math_expert(question: str) -> str:
    """덧셈 같은 계산 문제를 계산 전문가 에이전트에게 위임한다."""
    CALL_LOG.append(question)
    # 새 대화로 시작 → 메인의 대화 기록이 서브 에이전트로 새지 않는다
    result = math_agent.invoke({"messages": [HumanMessage(question)]}, {"recursion_limit": 10})
    # 최종 답변 텍스트만 반환 → 서브 에이전트의 중간 과정이 메인으로 새지 않는다
    return result["messages"][-1].text


main_agent = create_agent(
    MODEL,
    tools=[ask_math_expert],
    system_prompt="당신은 비서입니다. 계산 문제는 반드시 계산 전문가에게 위임하세요.",
    name="main_agent",
)


if __name__ == "__main__":
    result = main_agent.invoke(
        {"messages": [HumanMessage("계산 전문가에게 물어봐 줘: 12 더하기 30은?")]},
        {"recursion_limit": 10},
    )
    for m in result["messages"]:
        m.pretty_print()

    msgs = result["messages"]
    tool_names = [m.name for m in msgs if isinstance(m, ToolMessage)]

    assert len(CALL_LOG) == 1, f"서브 에이전트는 1번 호출되어야 합니다. 현재: {len(CALL_LOG)}"
    assert "ask_math_expert" in tool_names, "메인 대화에 ask_math_expert 결과가 없습니다."
    assert "add_numbers" not in tool_names, "서브 에이전트 내부 도구 결과가 메인으로 새어 나왔습니다."
    assert isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls, "마지막은 최종 AI 답변이어야 합니다."
    print("✅ 모든 테스트 통과!")
