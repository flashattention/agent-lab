"""with_retry 와 with_fallbacks 로 장애에 강한 체인 만들기.

- 일시적 오류(ConnectionError)는 재시도로 해결한다
- 영구적 오류(ValueError 등)는 재시도하지 않는다
- 주 경로가 완전히 죽으면 예비 경로(fallback)로 넘어간다
"""

import os

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 재시도
section("1. with_retry: 두 번 실패 후 성공하는 API")
attempts = {"n": 0}


def flaky_api(text: str) -> str:
    """처음 두 번은 네트워크 오류를 내는 가짜 외부 API."""
    attempts["n"] += 1
    print(f"  시도 {attempts['n']}회차...")
    if attempts["n"] < 3:
        raise ConnectionError("일시적 네트워크 오류")
    return f"처리 완료: {text}"


robust = RunnableLambda(flaky_api).with_retry(
    retry_if_exception_type=(ConnectionError, TimeoutError),  # 일시적 오류만 재시도
    stop_after_attempt=3,
    wait_exponential_jitter=False,  # 실습에서는 대기 없이. 현업에서는 True(기본값) 권장
)
print("결과:", robust.invoke("주문 1234"))

# ---------------------------------------------------------------- 2. 재시도하면 안 되는 오류
section("2. 영구적 오류는 재시도하지 않는다")
calls = {"n": 0}


def bad_request(_: str) -> str:
    calls["n"] += 1
    raise ValueError("잘못된 요청(400) — 다시 보내도 실패")


try:
    RunnableLambda(bad_request).with_retry(
        retry_if_exception_type=(ConnectionError,), stop_after_attempt=3, wait_exponential_jitter=False
    ).invoke("x")
except ValueError as e:
    print(f"ValueError 즉시 전파: {e} (호출 횟수 {calls['n']}회)")

# ---------------------------------------------------------------- 3. 폴백
section("3. with_fallbacks: 주 모델 장애 → 예비 모델")


def dead_primary(_):
    """제공자 전체 장애를 흉내 내는 '주 모델'."""
    raise ConnectionError("503 Service Unavailable")


primary = RunnableLambda(dead_primary).with_config(run_name="primary-model")
backup = init_chat_model(MODEL)  # 현업에서는 다른 제공자/리전의 모델을 둔다

prompt = ChatPromptTemplate.from_template("한 문장으로 답해: {q}")
chain = prompt | primary.with_fallbacks([backup]) | StrOutputParser()
print("폴백 결과:", chain.invoke({"q": "LCEL이 뭐야?"})[:80])

# 최후의 보루: 정중한 고정 메시지
last_resort = RunnableLambda(lambda _: "죄송합니다. 잠시 후 다시 시도해 주세요.")
everything_dead = RunnableLambda(dead_primary).with_fallbacks(
    [RunnableLambda(dead_primary), last_resort],  # 순서대로 시도
    exceptions_to_handle=(ConnectionError,),  # 이 예외일 때만 폴백
)
print("모두 실패 시:", everything_dead.invoke("hi"))
