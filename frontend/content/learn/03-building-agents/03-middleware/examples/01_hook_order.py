"""6가지 미들웨어 훅의 실행 순서를 눈으로 확인하기.

before_agent → (before_model → wrap_model_call → after_model → wrap_tool_call)* → after_agent
"""

import os
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    after_agent,
    after_model,
    before_agent,
    before_model,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.tools import tool
from langgraph.runtime import Runtime

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
TRACE: list[str] = []


def log(event: str) -> None:
    TRACE.append(event)
    print(f"  {len(TRACE):>2}. {event}")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    return f"{city}: 맑음, 22도"


# ── 노드형 훅: (state, runtime) → 상태 업데이트 dict 또는 None ──
# 관례: 인자 이름은 state, runtime (클래스형 미들웨어에서는 이 이름이 필수).
@before_agent
def on_start(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    log(f"before_agent   (메시지 {len(state['messages'])}개로 시작)")
    return None


@before_model
def on_before_model(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    log(f"before_model   (모델에 보낼 메시지 {len(state['messages'])}개)")
    return None


@after_model
def on_after_model(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    last = state["messages"][-1]
    log(f"after_model    (tool_calls={[c['name'] for c in last.tool_calls]})")
    return None


@after_agent
def on_end(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    log(f"after_agent    (최종 메시지 {len(state['messages'])}개)")
    return None


# ── 래핑형 훅: (request, handler) → handler(request)를 감싼다 ──
@wrap_model_call
def around_model(request: ModelRequest, handler) -> ModelResponse:
    log("wrap_model_call: 모델 호출 직전")
    response = handler(request)  # ← 실제 모델 호출
    log("wrap_model_call: 모델 호출 직후")
    return response


@wrap_tool_call
def around_tool(request, handler):
    log(f"wrap_tool_call: {request.tool_call['name']}({request.tool_call['args']}) 실행 직전")
    result = handler(request)  # ← 실제 도구 실행
    log("wrap_tool_call: 도구 실행 직후")
    return result


def main() -> None:
    agent = create_agent(
        MODEL,
        tools=[get_weather],
        middleware=[on_start, on_before_model, around_model, on_after_model, around_tool, on_end],
    )

    print("=" * 60)
    print("실행 추적")
    print("=" * 60)
    agent.invoke({"messages": [{"role": "user", "content": "서울 날씨 알려줘"}]})

    print("\n" + "=" * 60)
    print("노드형 훅은 그래프의 실제 노드가 된다")
    print("=" * 60)
    for node in agent.get_graph().nodes:
        print("  -", node)


if __name__ == "__main__":
    main()
