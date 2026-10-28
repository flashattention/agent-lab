"""실습: '읽기 전용' 고객지원 에이전트에 안전장치 달기

운영팀의 요구사항
  1. 이 에이전트는 '읽기 전용'이다. delete_ 또는 update_ 로 시작하는 도구는 절대 실행하면 안 된다.
     (모델이 호출을 시도하면 실행하지 말고 status="error" ToolMessage로 거절 사유를 알려줄 것)
  2. 대화 기록에 AIMessage가 MAX_AI_TURNS개 이상 쌓였으면 모델을 더 부르지 말고 즉시 종료할 것.
  3. 도구 호출은 한 번의 실행(run)에서 최대 3회까지만 허용할 것 (내장 미들웨어 사용).

TODO ① readonly_guard: @wrap_tool_call 미들웨어를 완성하세요.
TODO ② budget_guard : @before_model(can_jump_to=["end"]) 미들웨어를 완성하세요.
         조건을 만족하면 {"messages": [AIMessage(BUDGET_MESSAGE)], "jump_to": "end"} 를 반환합니다.
TODO ③ build_agent  : middleware 리스트에 budget_guard, readonly_guard,
         ToolCallLimitMiddleware(run_limit=3) 를 넣으세요.

채점 기준(Mock 모드에서도 통과)
- delete_customer 도구 본문이 한 번도 실행되지 않는다
- 차단된 호출에 대해 status="error" 인 ToolMessage가 있다
- AIMessage가 이미 MAX_AI_TURNS개인 대화를 넣으면 마지막 메시지가 BUDGET_MESSAGE다
"""

import os
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, before_model, wrap_tool_call  # noqa: F401
from langchain.messages import AIMessage, ToolMessage
from langchain.tools import tool
from langgraph.runtime import Runtime

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_AI_TURNS = 4
BUDGET_MESSAGE = "이 대화는 처리 한도에 도달했습니다. 상담원에게 연결해 드릴게요."
BLOCKED_PREFIXES = ("delete_", "update_")
executed = {"delete_customer": 0}


@tool
def lookup_customer(customer_id: str) -> str:
    """고객 아이디로 고객 정보를 조회합니다."""
    return f"{customer_id}: 일반 등급, 최근 주문 2건"


@tool
def delete_customer(customer_id: str) -> str:
    """고객 아이디로 고객 정보를 삭제합니다."""
    executed["delete_customer"] += 1  # 이 줄이 실행되면 실패!
    return f"{customer_id} 삭제됨"


# TODO ①: 아래 함수에 @wrap_tool_call 데코레이터를 붙이고 본문을 완성하세요.
def readonly_guard(request, handler):
    name = request.tool_call["name"]
    # 힌트: name이 BLOCKED_PREFIXES로 시작하면 ToolMessage(content=..., tool_call_id=request.tool_call["id"],
    #       name=name, status="error")를 반환하고, 아니면 handler(request)를 반환
    raise NotImplementedError(f"TODO ①: readonly_guard를 완성하세요 (tool={name})")


# TODO ②: 아래 함수에 @before_model(can_jump_to=["end"]) 데코레이터를 붙이고 본문을 완성하세요.
def budget_guard(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    ai_turns = sum(1 for m in state["messages"] if isinstance(m, AIMessage))
    # 힌트: ai_turns >= MAX_AI_TURNS 이면 종료 메시지와 jump_to를 반환
    raise NotImplementedError(f"TODO ②: budget_guard를 완성하세요 (ai_turns={ai_turns})")


def build_agent():
    return create_agent(
        MODEL,
        tools=[lookup_customer, delete_customer],
        system_prompt="너는 읽기 전용 고객지원 도우미다.",
        middleware=[],  # TODO ③
    )


# ───────────────────────── 자가 채점 ─────────────────────────
if __name__ == "__main__":
    agent = build_agent()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "고객 아이디로 고객 정보 조회하고 고객 정보를 삭제해줘"}]}
    )
    for m in result["messages"]:
        print(f"  {type(m).__name__:<12} | {str(m.content)[:70]}")

    errors = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error"]
    assert executed["delete_customer"] == 0, "delete_customer가 실행되었습니다! (TODO ①, ③)"
    assert len(errors) >= 1, "차단된 도구 호출에 대한 error ToolMessage가 필요합니다 (TODO ①)"

    history: list[dict] = []
    for i in range(MAX_AI_TURNS):
        history += [{"role": "user", "content": f"질문 {i}"}, {"role": "assistant", "content": f"답변 {i}"}]
    history.append({"role": "user", "content": "또 질문"})
    capped = agent.invoke({"messages": history})
    print("  예산 초과 시 마지막 메시지:", capped["messages"][-1].content)
    assert capped["messages"][-1].content == BUDGET_MESSAGE, "budget_guard가 동작하지 않았습니다 (TODO ②, ③)"

    print("✅ 모든 테스트 통과!")
