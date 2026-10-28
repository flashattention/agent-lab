"""에러 처리: 타임아웃, 재시도(with_retry), 폴백(with_fallbacks), 안전한 호출 래퍼.

실제 API 장애를 일부러 일으킬 수는 없으므로, 일정 횟수 실패하는 '불안정한 가짜 모델'을
RunnableLambda 로 만들어 재시도·폴백 동작을 관찰한다.
"""

from __future__ import annotations

import os

import openai
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableLambda

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def section(title: str) -> None:
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


class TransientError(Exception):
    """일시적 장애(429, 5xx, 네트워크 끊김 등)를 흉내 내는 예외."""


def make_flaky(fail_times: int) -> RunnableLambda:
    """처음 fail_times 번은 실패하고 그다음부터 성공하는 가짜 모델."""
    state = {"calls": 0}

    def _call(prompt: str) -> str:
        state["calls"] += 1
        if state["calls"] <= fail_times:
            print(f"    ✗ 호출 {state['calls']}: 일시 장애 발생")
            raise TransientError("503 Service Unavailable (simulated)")
        print(f"    ✓ 호출 {state['calls']}: 성공")
        return f"응답: {prompt}"

    return RunnableLambda(_call)


# 재시도할 가치가 있는 OpenAI 예외들 (인증 오류·잘못된 요청은 재시도해도 소용없다)
RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)


def safe_invoke(llm, prompt: str) -> str:
    """예외 종류별로 다르게 대응하는 호출 래퍼 (현업 패턴)."""
    try:
        return llm.invoke(prompt).text
    except openai.AuthenticationError:
        return "[오류] API 키가 잘못되었습니다. 설정을 확인하세요."  # 재시도 무의미
    except openai.BadRequestError as e:
        return f"[오류] 요청 형식 문제(컨텍스트 초과, 지원하지 않는 파라미터 등): {e}"  # 코드 수정 필요
    except RETRYABLE as e:
        return f"[오류] 일시 장애로 실패했습니다(재시도 소진): {type(e).__name__}"  # 사용자에게 재시도 안내
    except Exception as e:  # 예상 못 한 오류는 로그를 남기고 다시 올리는 게 원칙
        print("unexpected:", type(e).__name__)
        raise


if __name__ == "__main__":
    section("1) 모델 초기화 시 timeout / max_retries 설정")
    llm = init_chat_model(MODEL, timeout=30, max_retries=2)
    print("✅ OpenAI 클라이언트 레벨에서 429/5xx/타임아웃을 자동 재시도합니다 (max_retries=2).")

    section("2) with_retry: Runnable 레벨 재시도 (지수 백오프)")
    flaky = make_flaky(fail_times=2).with_retry(
        retry_if_exception_type=(TransientError,),  # 재시도할 예외만 지정
        stop_after_attempt=3,  # 최대 3번 시도
        wait_exponential_jitter=False,  # 데모를 빠르게 (현업에서는 True 권장)
    )
    print("  결과:", flaky.invoke("안녕"))

    section("3) with_retry 로도 실패하면? → 예외가 그대로 올라온다")
    try:
        make_flaky(fail_times=5).with_retry(
            retry_if_exception_type=(TransientError,), stop_after_attempt=2, wait_exponential_jitter=False
        ).invoke("안녕")
    except TransientError as e:
        print("  최종 실패:", e)

    section("4) with_fallbacks: 기본 모델 실패 시 대체 모델로")
    primary = make_flaky(fail_times=99)  # 항상 실패하는 기본 모델이라고 가정
    chain = primary.with_fallbacks([llm | RunnableLambda(lambda m: f"(폴백 모델) {m.text[:40]}")])
    print("  결과:", chain.invoke("폴백 테스트"))

    section("5) batch(return_exceptions=True): 일부 실패해도 전체를 잃지 않기")
    sometimes = RunnableLambda(lambda x: 1 / x)  # 0 이 들어오면 ZeroDivisionError
    results = sometimes.batch([1, 0, 2], return_exceptions=True)
    for x, r in zip([1, 0, 2], results):
        print(f"  입력 {x} → {'❌ ' + type(r).__name__ if isinstance(r, Exception) else r}")

    section("6) 예외 종류별로 대응하는 safe_invoke")
    print("  ", safe_invoke(llm, "안전하게 호출!")[:60])

    section("7) 잘못된 모델 ID는 초기화 시점에 바로 실패한다")
    try:
        init_chat_model("unknown-provider:some-model")
    except ValueError as e:
        print("  ValueError:", str(e).splitlines()[0][:70])
