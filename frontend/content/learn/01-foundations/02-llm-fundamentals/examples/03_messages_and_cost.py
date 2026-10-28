"""메시지 역할(role), 토큰 사용량(usage_metadata), 비용 계산, 컨텍스트 예산.

- 실제 모델 호출 결과의 usage_metadata 를 읽어 비용을 계산한다.
- 단가는 '예시 값'이다. 실제 단가는 반드시 OpenAI 공식 가격 페이지에서 확인하자.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# 예시 단가(USD / 1M 토큰). 실제 가격과 다를 수 있다 — 계산 방법을 익히는 용도.
EXAMPLE_PRICE = {"input": 0.25, "output": 2.00}


def cost_usd(input_tokens: int, output_tokens: int, price: dict[str, float]) -> float:
    """토큰 수 × 단가 / 1,000,000"""
    return input_tokens * price["input"] / 1_000_000 + output_tokens * price["output"] / 1_000_000


if __name__ == "__main__":
    # 1) 네 가지 메시지 역할
    messages = [
        SystemMessage("너는 간결하게 답하는 여행 도우미야."),  # system: 규칙과 페르소나
        HumanMessage("서울 날씨 어때?"),  # user(human): 사용자 입력
        AIMessage(  # assistant(ai): 모델의 이전 출력 (여기서는 도구 호출 요청)
            content="",
            tool_calls=[{"name": "get_weather", "args": {"city": "서울"}, "id": "call_1", "type": "tool_call"}],
        ),
        ToolMessage("흐림, 17도, 강수확률 80%", tool_call_id="call_1"),  # tool: 도구 실행 결과
    ]
    print("=" * 60)
    print("① 대화 메시지 (역할별)")
    print("=" * 60)
    for m in messages:
        m.pretty_print()

    # 2) 모델 호출 → usage_metadata 확인
    llm = init_chat_model(MODEL)
    reply = llm.invoke(messages)
    print("\n" + "=" * 60)
    print("② 모델 응답과 토큰 사용량")
    print("=" * 60)
    reply.pretty_print()
    usage = reply.usage_metadata or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    print("usage_metadata:", usage)
    # 추론 모델이면 output_token_details.reasoning 에 '보이지 않는 생각' 토큰 수가 들어온다
    details = usage.get("output_token_details", {}) if isinstance(usage, dict) else {}
    print("reasoning 토큰:", details.get("reasoning", "(정보 없음)"))

    # 3) 비용 계산
    c = cost_usd(usage["input_tokens"], usage["output_tokens"], EXAMPLE_PRICE)
    print(f"\n💰 이번 호출 비용(예시 단가): ${c:.6f}")
    print(f"💰 하루 10만 건이면: ${c * 100_000:,.2f}")

    # 4) 에이전트 루프에서는 입력 토큰이 '누적'된다
    print("\n" + "=" * 60)
    print("③ 에이전트 루프의 누적 입력 토큰 (매 턴 전체 대화를 다시 보냄)")
    print("=" * 60)
    history = list(messages[:2])
    total_in = 0
    for turn in range(1, 6):
        n = count_tokens_approximately(history)  # 빠른 근사치
        total_in += n
        print(f"  turn {turn}: 이번 입력 ≈ {n:>4} 토큰 | 누적 ≈ {total_in:>5}")
        # 도구 결과가 붙었다고 가정 (긴 검색 결과)
        history.append(ToolMessage("검색 결과 " * 40, tool_call_id=f"call_{turn}"))

    # 5) 컨텍스트 예산: 입력 + 출력 예약분이 컨텍스트 윈도우 안에 들어와야 한다
    window, reserve_output = 8_000, 1_000  # 학습용 작은 값
    used = count_tokens_approximately(history)
    print(f"\n📦 컨텍스트 예산: 사용 {used} + 출력 예약 {reserve_output} / 윈도우 {window}"
          f" → {'OK' if used + reserve_output <= window else '초과! 요약/트리밍 필요'}")
