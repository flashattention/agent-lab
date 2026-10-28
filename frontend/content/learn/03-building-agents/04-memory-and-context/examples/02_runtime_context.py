"""런타임 컨텍스트: context_schema + dynamic_prompt + ToolRuntime.

신원·권한 같은 '신뢰해야 하는 정보'는 메시지가 아니라 컨텍스트로 주입한다.
- 모델은 컨텍스트를 바꿀 수 없다 (읽기 전용, 저장되지 않음)
- ToolRuntime 인자는 모델에게 보이는 도구 스키마에서 빠진다
"""

import os
from dataclasses import dataclass
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.tools import ToolRuntime, tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@dataclass
class UserContext:
    """앱이 인증을 거친 뒤 채워 넣는 실행 컨텍스트."""

    user_id: str
    tier: Literal["free", "pro"]
    language: str = "ko"


FAKE_ORDERS = {"u-1": ["키보드"], "u-2": ["모니터", "노트북 거치대"]}
PROMPTS_SEEN: list[str] = []  # 데모용: 실제로 모델에 들어간 시스템 프롬프트 기록


@tool
def get_my_orders(runtime: ToolRuntime[UserContext]) -> str:
    """현재 로그인한 사용자의 주문 목록을 조회합니다."""
    uid = runtime.context.user_id  # 모델이 아니라 앱이 넣어 준 값 → 위조 불가
    return f"{uid}의 주문: {FAKE_ORDERS.get(uid, [])}"


@dynamic_prompt
def personalized_prompt(request: ModelRequest) -> str:
    """매 모델 호출 직전에 시스템 프롬프트를 계산한다."""
    ctx: UserContext = request.runtime.context
    prompt = f"너는 쇼핑몰 상담원이다. 답변 언어: {ctx.language}."
    if ctx.tier == "pro":
        prompt += " 이 고객은 PRO 회원이므로 무료 반품과 우선 배송을 안내해도 된다."
    else:
        prompt += " 무료 반품은 PRO 회원 전용임을 안내해라."
    PROMPTS_SEEN.append(prompt)
    return prompt


def main() -> None:
    agent = create_agent(
        MODEL,
        tools=[get_my_orders],
        middleware=[personalized_prompt],
        context_schema=UserContext,
    )

    print("=" * 60)
    print("모델에게 보이는 도구 스키마 (runtime 인자가 없다!)")
    print("=" * 60)
    print("  ", get_my_orders.tool_call_schema.model_json_schema().get("properties", {}))

    question = {"messages": [{"role": "user", "content": "내 주문 목록 보여주고 반품 되는지 알려줘"}]}
    for ctx in (UserContext(user_id="u-1", tier="free"), UserContext(user_id="u-2", tier="pro")):
        PROMPTS_SEEN.clear()
        result = agent.invoke(question, context=ctx)
        tool_outputs = [m.content for m in result["messages"] if m.type == "tool"]
        print("\n" + "=" * 60)
        print(f"컨텍스트: {ctx}")
        print("=" * 60)
        print("  시스템 프롬프트 :", PROMPTS_SEEN[0])
        print("  모델 호출 수    :", len(PROMPTS_SEEN), "(호출마다 다시 계산됨)")
        print("  도구 결과       :", tool_outputs)
        print("  최종 답변       :", str(result["messages"][-1].content)[:70])
        print("  상태에 컨텍스트가 저장되었나? ->", "user_id" in result)


if __name__ == "__main__":
    main()
