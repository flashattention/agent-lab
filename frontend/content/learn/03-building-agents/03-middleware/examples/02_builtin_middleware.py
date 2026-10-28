"""내장 미들웨어 5종 시연.

1) ModelCallLimitMiddleware  : 모델 호출 횟수 상한
2) ToolRetryMiddleware       : 일시적 도구 오류 재시도
3) ModelFallbackMiddleware   : 주 모델 장애 시 대체 모델
4) PIIMiddleware             : 이메일 가리기
5) HumanInTheLoopMiddleware  : 위험한 도구 실행 전 사람 승인 (→ 5.3에서 자세히)
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    PIIMiddleware,
    ToolRetryMiddleware,
)
from langchain.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
FALLBACK_MODEL = "openai:gpt-5-nano"


def section(title: str) -> None:
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


def show(messages: list) -> None:
    for m in messages:
        body = str(m.content)[:80] or f"tool_calls={[c['name'] for c in m.tool_calls]}"
        print(f"  {type(m).__name__:<12} | {body}")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    return f"{city}: 맑음, 22도"


# ── 1) 모델 호출 상한 ─────────────────────────────
section("1) ModelCallLimitMiddleware(run_limit=1)")
agent = create_agent(
    MODEL,
    tools=[get_weather],
    middleware=[ModelCallLimitMiddleware(run_limit=1, exit_behavior="end")],
)
show(agent.invoke({"messages": [{"role": "user", "content": "서울 날씨"}]})["messages"])
print("  → 도구 결과를 받은 뒤 두 번째 모델 호출 전에 종료 메시지로 끝났습니다.")

# ── 2) 도구 재시도 ────────────────────────────────
section("2) ToolRetryMiddleware(max_retries=3)")
attempts = {"count": 0}


@tool
def search_news(query: str) -> str:
    """뉴스를 검색합니다. (처음 두 번은 일부러 타임아웃이 납니다)"""
    attempts["count"] += 1
    if attempts["count"] < 3:
        raise TimeoutError(f"검색 서버 응답 없음 (시도 {attempts['count']})")
    return "뉴스 3건 검색됨"


agent = create_agent(
    MODEL,
    tools=[search_news],
    # 데모용으로 대기 시간을 아주 짧게. 현업에서는 기본값(1초, 지수 백오프, jitter)을 권장
    middleware=[ToolRetryMiddleware(max_retries=3, initial_delay=0.01, jitter=False, tools=["search_news"])],
)
show(agent.invoke({"messages": [{"role": "user", "content": "오늘 뉴스 검색"}]})["messages"])
print(f"  → 도구가 총 {attempts['count']}번 실행되었고, 모델은 성공 결과만 보았습니다.")


# ── 3) 모델 폴백 ──────────────────────────────────
class AlwaysDownModel(BaseChatModel):
    """항상 503 오류를 내는 가짜 모델 (장애 상황 재현용)."""

    @property
    def _llm_type(self) -> str:
        return "always-down"

    def _generate(self, *args: Any, **kwargs: Any):
        raise RuntimeError("503 Service Unavailable")

    def bind_tools(self, tools: Any, **kwargs: Any) -> "AlwaysDownModel":
        return self


section(f"3) ModelFallbackMiddleware('{FALLBACK_MODEL}')")
agent = create_agent(
    AlwaysDownModel(),
    tools=[get_weather],
    middleware=[ModelFallbackMiddleware(FALLBACK_MODEL)],
)
result = agent.invoke({"messages": [{"role": "user", "content": "부산 날씨"}]})
print("  응답한 모델:", result["messages"][-1].response_metadata.get("model_name"))
show(result["messages"])

# ── 4) PII 가리기 ─────────────────────────────────
section("4) PIIMiddleware('email', strategy='redact')")
agent = create_agent(MODEL, tools=[], middleware=[PIIMiddleware("email", strategy="redact")])
show(agent.invoke({"messages": [{"role": "user", "content": "제 메일은 minji@example.com 입니다"}]})["messages"])
print("  → 모델은 원래 이메일 주소를 보지 못했습니다.")

# ── 5) 사람 승인 (HITL) ───────────────────────────
section("5) HumanInTheLoopMiddleware(interrupt_on={'delete_file': True})")


@tool
def delete_file(path: str) -> str:
    """파일을 영구 삭제합니다."""
    return f"{path} 삭제 완료"


agent = create_agent(
    MODEL,
    tools=[delete_file],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"delete_file": True})],
    checkpointer=InMemorySaver(),  # 멈췄다가 재개하려면 상태 저장소가 필요
)
config = {"configurable": {"thread_id": "hitl-demo"}}
paused = agent.invoke({"messages": [{"role": "user", "content": "report.txt 파일 삭제해줘"}]}, config)
request = paused["__interrupt__"][0].value["action_requests"][0]
print(f"  ⏸  승인 대기: {request['name']}({request['args']})")

# 사람이 거절했다고 가정하고 재개
resumed = agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "중요 파일이라 삭제 불가"}]}), config)
show(resumed["messages"])
