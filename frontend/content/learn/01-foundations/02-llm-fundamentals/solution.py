"""실습: 메시지 구성 · 비용 계산 · 컨텍스트 예산 (정답)

세 함수를 완성하세요.
1. build_messages(system, history, question)
   - [SystemMessage, *history, HumanMessage(question)] 순서의 리스트를 돌려준다.
   - history 는 (role, text) 튜플 리스트. role 은 "user" 또는 "assistant".
2. estimate_cost(usage, price)
   - usage: {"input_tokens": int, "output_tokens": int, ...}
   - price: {"input": USD/1M, "output": USD/1M}
   - USD 비용(float)을 돌려준다.
3. fits_in_context(messages, window, reserve_output)
   - count_tokens_approximately(messages) + reserve_output <= window 이면 True.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
EXAMPLE_PRICE = {"input": 0.25, "output": 2.00}  # 예시 단가 (USD / 1M 토큰)


def build_messages(system: str, history: list[tuple[str, str]], question: str) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(system)]
    for role, text in history:
        messages.append(HumanMessage(text) if role == "user" else AIMessage(text))
    messages.append(HumanMessage(question))
    return messages


def estimate_cost(usage: dict, price: dict[str, float]) -> float:
    return (usage["input_tokens"] * price["input"] + usage["output_tokens"] * price["output"]) / 1_000_000


def fits_in_context(messages: list[BaseMessage], window: int, reserve_output: int) -> bool:
    return count_tokens_approximately(messages) + reserve_output <= window


if __name__ == "__main__":
    history = [("user", "안녕, 나는 민수야."), ("assistant", "안녕하세요 민수님!")]
    msgs = build_messages("너는 친절한 도우미야.", history, "내 이름이 뭐였지?")
    for m in msgs:
        print(f"{m.type:>6}: {m.content}")

    llm = init_chat_model(MODEL)
    reply = llm.invoke(msgs)
    usage = reply.usage_metadata
    cost = estimate_cost(usage, EXAMPLE_PRICE)
    print(f"\nusage={usage}\ncost=${cost:.8f}")

    # --- 자가 채점 ---
    assert [m.type for m in msgs] == ["system", "human", "ai", "human"], "역할 순서가 올바르지 않습니다"
    assert msgs[-1].content == "내 이름이 뭐였지?"
    assert abs(estimate_cost({"input_tokens": 1_000_000, "output_tokens": 0}, EXAMPLE_PRICE) - 0.25) < 1e-9
    assert abs(estimate_cost({"input_tokens": 2000, "output_tokens": 500}, EXAMPLE_PRICE) - 0.0015) < 1e-9
    assert cost > 0, "실제 호출의 usage_metadata 로 비용을 계산해야 합니다"
    assert fits_in_context(msgs, window=8000, reserve_output=1000) is True
    assert fits_in_context(msgs, window=50, reserve_output=1000) is False
    print("✅ 모든 테스트 통과!")
