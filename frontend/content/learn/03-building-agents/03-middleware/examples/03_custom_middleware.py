"""커스텀 미들웨어 4종을 조합한 에이전트.

- UsageTracker (클래스형)  : state_schema로 상태 필드 추가 + wrap_model_call로 토큰 집계
- route_model  (wrap_model_call) : 대화 길이에 따라 저렴한 모델/기본 모델 라우팅
- guard_tools  (wrap_tool_call)  : 허용 목록에 없는 도구 차단
- stop_long    (before_model + jump_to) : 너무 긴 대화는 모델 호출 없이 종료
"""

import os
from typing import Any, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    before_model,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, ToolMessage
from langchain.tools import tool
from langgraph.runtime import Runtime

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
CHEAP_MODEL = "openai:gpt-5-nano"
ALLOWED_TOOLS = {"lookup_customer"}


@tool
def lookup_customer(customer_id: str) -> str:
    """고객 아이디로 고객 정보를 조회합니다."""
    return f"{customer_id}: VIP 등급, 가입 3년차"


@tool
def delete_customer(customer_id: str) -> str:
    """고객 아이디로 고객 정보를 삭제합니다."""
    return f"{customer_id} 삭제됨"  # 차단되어 실제로는 실행되지 않는다


# ── 1) 클래스형: 상태 필드 추가 + 토큰 집계 ──────────────
class UsageState(AgentState):
    model_calls: NotRequired[int]
    total_tokens: NotRequired[int]


class UsageTracker(AgentMiddleware):
    """모델 호출 수와 토큰 사용량을 에이전트 상태에 누적한다."""

    state_schema = UsageState

    def before_model(self, state: UsageState, runtime: Runtime) -> dict[str, Any] | None:
        return {"model_calls": state.get("model_calls", 0) + 1}

    def after_model(self, state: UsageState, runtime: Runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        used = (last.usage_metadata or {}).get("total_tokens", 0) if isinstance(last, AIMessage) else 0
        return {"total_tokens": state.get("total_tokens", 0) + used}


# ── 2) 모델 라우팅: 첫 호출은 기본 모델, 이후 정리 단계는 저렴한 모델 ──
cheap_llm = init_chat_model(CHEAP_MODEL)


@wrap_model_call
def route_model(request: ModelRequest, handler) -> ModelResponse:
    has_tool_results = any(isinstance(m, ToolMessage) for m in request.messages)
    if has_tool_results:
        # 원본 request는 그대로 두고, 모델만 바꾼 복사본을 만든다
        request = request.override(model=cheap_llm)
    return handler(request)


# ── 3) 도구 가드: 허용 목록 밖의 도구는 실행하지 않는다 ──
@wrap_tool_call
def guard_tools(request, handler):
    name = request.tool_call["name"]
    if name not in ALLOWED_TOOLS:
        print(f"  🚫 차단: {name}")
        return ToolMessage(
            content=f"'{name}' 도구는 이 에이전트에서 사용할 수 없습니다.",
            tool_call_id=request.tool_call["id"],
            name=name,
            status="error",
        )
    return handler(request)


# ── 4) 조기 종료: jump_to는 can_jump_to로 미리 선언해야 한다 ──
@before_model(can_jump_to=["end"])
def stop_long(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    if len(state["messages"]) > 6:
        return {
            "messages": [AIMessage("대화가 너무 길어졌습니다. 새 대화로 다시 시작해 주세요.")],
            "jump_to": "end",
        }
    return None


def build_agent():
    return create_agent(
        MODEL,
        tools=[lookup_customer, delete_customer],
        system_prompt="너는 CRM 상담 도우미다.",
        # 순서: 상한/종료 판단 → 집계 → 라우팅 → 도구 가드
        middleware=[stop_long, UsageTracker(), route_model, guard_tools],
    )


def main() -> None:
    agent = build_agent()

    print("=" * 60)
    print("A) 고객 조회 + 삭제를 한 번에 요청")
    print("=" * 60)
    result = agent.invoke({"messages": [{"role": "user", "content": "고객 아이디로 고객 정보 조회하고 고객 정보를 삭제해줘"}]})
    for m in result["messages"]:
        model_name = m.response_metadata.get("model_name", "") if isinstance(m, AIMessage) else ""
        body = str(m.content)[:60] or f"tool_calls={[c['name'] for c in m.tool_calls]}"
        print(f"  {type(m).__name__:<12} {model_name:<11} | {body}")
    print("  model_calls :", result.get("model_calls"))
    print("  total_tokens:", result.get("total_tokens"))

    print("\n" + "=" * 60)
    print("B) 이미 긴 대화 → before_model에서 jump_to='end'")
    print("=" * 60)
    long_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"메시지 {i}"} for i in range(7)]
    result = agent.invoke({"messages": long_history})
    print("  마지막 메시지:", result["messages"][-1].content)
    print("  model_calls :", result.get("model_calls", 0), "(모델이 호출되지 않음)")


if __name__ == "__main__":
    main()
