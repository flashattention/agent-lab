"""예제 1: RetryPolicy로 일시적 장애 재시도 + error_handler로 우아한 실패(fallback).

- fetch_rates : 처음 두 번은 ConnectionError(일시 장애) → RetryPolicy가 재시도해 성공
- fetch_news  : 계속 실패 → 재시도를 다 써도 실패하면 error_handler가 대체 경로로 안내
- parse_input : ValueError(코드 버그/잘못된 입력)는 재시도해도 소용없으므로 retry_on에서 제외
"""

import operator
from typing import Annotated, TypedDict

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, RetryPolicy


class ReportState(TypedDict, total=False):
    rates: str
    news: str
    log: Annotated[list[str], operator.add]


class TransientAPIError(Exception):
    """429/503 같은 일시적 오류를 흉내 내는 예외."""


CALLS = {"rates": 0, "news": 0}


def fetch_rates(state: ReportState, runtime: Runtime) -> dict:
    CALLS["rates"] += 1
    attempt = runtime.execution_info.node_attempt  # 몇 번째 시도인지 LangGraph가 알려 준다
    print(f"  fetch_rates 시도 #{attempt}")
    if CALLS["rates"] < 3:
        raise ConnectionError("환율 API 연결 실패")
    return {"rates": "USD/KRW 1,380", "log": [f"rates 성공 (시도 {attempt}회)"]}


def fetch_news(state: ReportState, runtime: Runtime) -> dict:
    CALLS["news"] += 1
    print(f"  fetch_news 시도 #{runtime.execution_info.node_attempt}")
    raise TransientAPIError("뉴스 API 503")


def news_fallback(state: ReportState, error: NodeError) -> Command:
    """재시도를 모두 소진하면 호출된다. 에러 정보는 NodeError로 주입된다."""
    print(f"  ⚠️ fallback 실행: node={error.node}, error={error.error!r}")
    return Command(
        update={"news": "(뉴스를 가져오지 못했습니다 — 캐시된 요약 사용)", "log": ["news fallback"]},
        goto="write",  # 대체 경로로 계속 진행
    )


def write(state: ReportState) -> dict:
    return {"log": [f"보고서 작성: {state['rates']} / {state['news']}"]}


# 일시적 오류만 재시도하도록 retry_on을 명시한다
transient_retry = RetryPolicy(
    max_attempts=3,  # 첫 시도 포함 최대 3번
    initial_interval=0.05,  # 첫 재시도 전 대기(초). 실서비스는 0.5~1초 이상
    backoff_factor=2.0,  # 대기 시간이 0.05 → 0.1 → 0.2 ... 로 증가 (지수 백오프)
    jitter=True,  # 여러 클라이언트가 동시에 재시도하지 않도록 무작위성 추가
    retry_on=(ConnectionError, TransientAPIError),
)

builder = StateGraph(ReportState)
builder.add_node("fetch_rates", fetch_rates, retry_policy=transient_retry)
builder.add_node("fetch_news", fetch_news, retry_policy=transient_retry, error_handler=news_fallback)
builder.add_node("write", write)
builder.add_edge(START, "fetch_rates")
builder.add_edge("fetch_rates", "fetch_news")
builder.add_edge("fetch_news", "write")
builder.add_edge("write", END)
graph = builder.compile()

print("=" * 64)
print("1) 재시도 + fallback")
print("=" * 64)
result = graph.invoke({"log": []})
for line in result["log"]:
    print("  log:", line)
assert CALLS == {"rates": 3, "news": 3}
assert "fallback" in result["news"] or "가져오지 못했습니다" in result["news"]

print("\n" + "=" * 64)
print("2) 재시도 대상이 아닌 에러는 즉시 실패한다")
print("=" * 64)
PARSE_CALLS = {"n": 0}


def parse_input(state: ReportState) -> dict:
    PARSE_CALLS["n"] += 1
    raise ValueError("날짜 형식이 잘못됨: '2026-13-45'")  # 버그/잘못된 입력: 재시도해도 같다


b2 = StateGraph(ReportState)
b2.add_node("parse_input", parse_input, retry_policy=transient_retry)
b2.add_edge(START, "parse_input")
try:
    b2.compile().invoke({"log": []})
except ValueError as e:
    print(f"  ValueError 발생 (시도 {PARSE_CALLS['n']}회만): {e}")
assert PARSE_CALLS["n"] == 1, "retry_on에 없는 에러는 재시도하지 않는다"
print("\n✔ 재시도는 '일시적' 오류에만, 나머지는 빠르게 실패하거나 fallback으로.")
