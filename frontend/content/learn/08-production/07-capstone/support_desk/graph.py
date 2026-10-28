"""최상위 고객지원 그래프.

  START → guard ─(차단)→ END
            └→ load_memory → route ─┬→ faq_agent   ─┐
                                    ├→ order_agent ─┼→ save_memory → END
                                    └→ smalltalk   ─┘

- guard       : 프롬프트 인젝션 차단 (모델 호출 0회로 종료)
- load_memory : Store 에서 프로필 로드 → 상태에 기록 (라우터·응답 개인화에 사용)
- route       : 규칙 → (애매하면) 작은 LLM 구조화 출력
- 전문가       : create_agent 서브그래프 (RAG / 도구 / HITL)
- save_memory : 이번 턴 이력 + 선호 추출 → Store
"""

from __future__ import annotations

from typing import Any, Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from .agents import build_faq_agent, build_order_agent
from .config import SETTINGS
from .memory import load_profile, record_interaction
from .policies import detect_injection
from .router import llm_route, rule_route
from .tools import SupportContext


class SupportState(MessagesState):
    route: str
    route_source: str  # "rule" | "llm" — 트레이스/평가에서 라우터 품질 분석용
    profile: dict


def _last_human_text(state: SupportState) -> str:
    return next((str(m.content) for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")


# ------------------------------------------------------------------ 노드
def guard(state: SupportState) -> Command[Literal["load_memory", "__end__"]]:
    if detect_injection(_last_human_text(state)):
        refusal = AIMessage("죄송하지만 해당 요청은 도와드릴 수 없습니다. 주문·배송·환불 관련 문의를 남겨 주세요.")
        return Command(update={"messages": [refusal], "route": "blocked", "route_source": "guard"}, goto=END)
    return Command(goto="load_memory")


def load_memory(state: SupportState, runtime: Runtime[SupportContext]) -> dict[str, Any]:
    profile = load_profile(runtime.store, runtime.context.user_id) if runtime.store else {}
    return {"profile": profile}


def route(state: SupportState) -> Command[Literal["faq_agent", "order_agent", "smalltalk"]]:
    text = _last_human_text(state)
    by_rule = rule_route(text)
    if by_rule:
        decision, source = by_rule, "rule"
    else:
        decision, source = llm_route(text).route, "llm"
    target = {"faq": "faq_agent", "order": "order_agent", "smalltalk": "smalltalk"}[decision]
    return Command(update={"route": decision, "route_source": source}, goto=target)


_small_llm = None


def smalltalk(state: SupportState) -> dict[str, Any]:
    """도구 없이 작은 모델로 짧게 응대 (비용 최적화)."""
    global _small_llm
    if _small_llm is None:
        _small_llm = init_chat_model(SETTINGS.small_model)
    name = (state.get("profile") or {}).get("name", "고객")
    msgs = [SystemMessage(f"너는 친절한 쇼핑몰 상담원이다. {name}님에게 한두 문장으로 답하라."), *state["messages"][-6:]]
    return {"messages": [_small_llm.invoke(msgs, config={"tags": ["final_answer"]})]}


def save_memory(state: SupportState, runtime: Runtime[SupportContext]) -> dict[str, Any]:
    if runtime.store:
        profile = record_interaction(runtime.store, runtime.context.user_id, state["route"], _last_human_text(state))
        return {"profile": profile}
    return {}


# ------------------------------------------------------------------ 조립
def build_support_graph(*, checkpointer: Any = None, store: Any = None, specialist_model: Any = None):
    """의존성 주입 팩토리.

    - checkpointer/store : 테스트에서는 InMemorySaver/InMemoryStore, 운영에서는 Postgres
    - specialist_model   : 전문가 에이전트 모델 교체 (단위 테스트의 대본 모델, A/B 실험 등)
    """
    g = StateGraph(SupportState, context_schema=SupportContext)
    g.add_node("guard", guard)
    g.add_node("load_memory", load_memory)
    g.add_node("route", route)
    g.add_node("faq_agent", build_faq_agent(specialist_model))
    g.add_node("order_agent", build_order_agent(specialist_model))
    g.add_node("smalltalk", smalltalk)
    g.add_node("save_memory", save_memory)

    g.add_edge(START, "guard")
    g.add_edge("load_memory", "route")
    for specialist in ("faq_agent", "order_agent", "smalltalk"):
        g.add_edge(specialist, "save_memory")
    g.add_edge("save_memory", END)
    return g.compile(checkpointer=checkpointer, store=store, name="support_desk")
