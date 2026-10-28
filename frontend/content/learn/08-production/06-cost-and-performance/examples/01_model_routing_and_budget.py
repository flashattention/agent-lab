"""모델 라우팅 + 토큰 예산 미들웨어.

[모델 라우팅]
  쉬운 질문까지 가장 비싼 모델로 처리하는 것이 가장 흔한 비용 낭비다.
  wrap_model_call 에서 요청마다 '충분히 좋은 가장 싼 모델'을 고른다.
    - 짧고 단순한 질문, 도구 결과 정리 → 작은 모델
    - 길거나 추론이 필요한 질문        → 큰 모델

[토큰 예산]
  after_model 에서 usage_metadata 를 상태에 누적하고,
  before_model 에서 예산을 넘었으면 모델을 더 부르지 않고 종료한다.

※ 단가는 '예시 값'이다. 실제 단가는 제공자 가격표를 확인할 것.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    hook_config,
)
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

SMALL = os.getenv("LAB_SMALL_MODEL", "openai:gpt-5-nano")
LARGE = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# 예시 단가 (USD / 1M tokens) — 구조 설명용. 실제 값으로 바꿔 쓰세요.
PRICE = {
    "gpt-5-nano": {"in": 0.05, "out": 0.40},
    "gpt-5-mini": {"in": 0.25, "out": 2.00},
}

HARD_HINTS = ("왜", "비교", "분석", "설계", "전략", "why", "compare", "analyze")


# ============================================================ 1) 라우터
class ModelRouter(AgentMiddleware):
    """요청 난이도에 따라 모델을 고르는 미들웨어."""

    def __init__(self) -> None:
        super().__init__()
        # 모델 객체는 한 번만 만들어 재사용한다 (요청마다 만들면 느리다)
        self.small = init_chat_model(SMALL)
        self.large = init_chat_model(LARGE)
        self.decisions: list[str] = []

    def choose(self, request: ModelRequest) -> str:
        last_human = next(m for m in reversed(request.messages) if isinstance(m, HumanMessage))
        text = str(last_human.content)
        after_tool = isinstance(request.messages[-1], ToolMessage)
        if after_tool:
            return "small"  # 도구 결과를 정리하는 턴은 대개 쉬운 작업
        if len(text) > 200 or any(h in text.lower() for h in HARD_HINTS):
            return "large"
        return "small"

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        tier = self.choose(request)
        self.decisions.append(tier)
        return handler(request.override(model=self.small if tier == "small" else self.large))


# ============================================================ 2) 토큰 예산
class BudgetState(AgentState):
    tokens_used: NotRequired[int]
    cost_usd: NotRequired[float]


class TokenBudget(AgentMiddleware[BudgetState]):
    """스레드(대화)당 토큰 예산. 넘으면 모델 호출 없이 정중히 종료."""

    state_schema = BudgetState

    def __init__(self, max_tokens: int) -> None:
        super().__init__()
        self.max_tokens = max_tokens

    def after_model(self, state: BudgetState, runtime: Runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        usage = getattr(last, "usage_metadata", None) or {}
        model = (last.response_metadata or {}).get("model_name", "gpt-5-mini")
        price = PRICE.get(model, PRICE["gpt-5-mini"])
        cost = (usage.get("input_tokens", 0) * price["in"] + usage.get("output_tokens", 0) * price["out"]) / 1e6
        return {
            "tokens_used": state.get("tokens_used", 0) + usage.get("total_tokens", 0),
            "cost_usd": state.get("cost_usd", 0.0) + cost,
        }

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: BudgetState, runtime: Runtime) -> dict[str, Any] | None:
        if state.get("tokens_used", 0) >= self.max_tokens:
            return {
                "messages": [AIMessage("대화가 길어져 이번 세션의 처리 한도에 도달했습니다. 새 대화를 시작해 주세요.")],
                "jump_to": "end",
            }
        return None


@tool
def search_kb(query: str) -> str:
    """사내 지식베이스 knowledge 검색"""
    return "환불은 7일 이내 가능. 단순 변심은 배송비 고객 부담."


router = ModelRouter()
agent = create_agent(LARGE, tools=[search_kb], middleware=[router, TokenBudget(max_tokens=260)])

agent_with_memory = create_agent(LARGE, tools=[search_kb], middleware=[router, TokenBudget(max_tokens=260)],
                                 checkpointer=InMemorySaver())

print("=" * 70 + "\n1) 라우팅 — 질문마다 어떤 모델이 쓰였나\n" + "=" * 70)
for q in ["배송비 얼마예요?", "환불 정책과 교환 정책을 비교 분석해서 고객 유형별 전략을 설계해줘"]:
    router.decisions.clear()
    out = agent.invoke({"messages": [HumanMessage(q)]})
    used = [m.response_metadata.get("model_name") for m in out["messages"] if isinstance(m, AIMessage)]
    print(f"Q: {q[:30]:<32} 라우팅={router.decisions}  실제 모델={used}")
    print(f"   토큰={out.get('tokens_used')}  예상 비용=${out.get('cost_usd', 0):.6f}")

print("\n" + "=" * 70 + "\n2) 토큰 예산 — 같은 대화에서 예산을 넘으면 차단\n" + "=" * 70)
cfg = {"configurable": {"thread_id": "budget-demo"}}
for turn in range(1, 6):
    out = agent_with_memory.invoke({"messages": [HumanMessage(f"{turn}번째 knowledge 질문입니다")]}, cfg)
    last = out["messages"][-1].content
    print(f"턴 {turn}: 누적 토큰={out.get('tokens_used', 0):>4}  응답={last[:45]}")
    if "한도" in last:
        print("   → 예산을 넘은 시점부터 모델을 더 부르지 않고 종료 (이후 비용 0)")
        break
assert "한도" in out["messages"][-1].content
