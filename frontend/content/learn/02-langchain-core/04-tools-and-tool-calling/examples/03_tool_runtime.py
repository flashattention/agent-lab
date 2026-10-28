"""ToolRuntime: 모델에게 숨긴 채 도구에 컨텍스트·상태를 주입하기.

- user_id 를 도구 인자로 두면 모델이 값을 '채우게' 된다 → 틀리거나 조작될 수 있다
- runtime: ToolRuntime 인자는 모델 스키마에서 빠지고, 실행 시 자동으로 채워진다
- ToolRuntime 은 LangGraph 위에서(create_agent, ToolNode) 실행될 때 주입된다
  (create_agent 는 3.2에서 자세히 배운다. 여기서는 도구 주입만 관찰한다)
"""

import os
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.utils.function_calling import convert_to_openai_tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@dataclass
class UserContext:
    """요청마다 서버가 채우는 불변 컨텍스트 (모델이 바꿀 수 없다)."""

    user_id: str
    plan: str


ORDERS = {"u-42": ["A-1001 무선 이어폰", "A-1007 키보드"], "u-77": ["A-2001 모니터"]}


# ❌ 나쁜 예: 모델이 user_id 를 채운다 (프롬프트 인젝션으로 남의 주문을 볼 수도!)
@tool
def my_orders_unsafe(user_id: str) -> str:
    """사용자의 최근 주문 목록을 조회한다."""
    return ", ".join(ORDERS.get(user_id, []))


# ✅ 좋은 예: user_id 는 runtime.context 에서 꺼낸다
@tool
def my_orders(runtime: ToolRuntime[UserContext]) -> str:
    """로그인한 사용자의 최근 주문 목록을 조회한다."""
    ctx = runtime.context  # 호출 시 넘긴 UserContext
    n_messages = len(runtime.state["messages"])  # 현재 에이전트 상태
    orders = ORDERS.get(ctx.user_id, [])
    return f"[{ctx.user_id}/{ctx.plan}] 주문 {len(orders)}건: {', '.join(orders)} (대화 메시지 {n_messages}개, call={runtime.tool_call_id})"


print("=" * 12, "모델에게 보이는 스키마 비교", "=" * 12)
for t in [my_orders_unsafe, my_orders]:
    params = convert_to_openai_tool(t)["function"]["parameters"]
    print(f"{t.name:<18} 인자: {list(params.get('properties', {}).keys())}")
print("→ my_orders 에는 runtime 인자가 보이지 않는다!")

print("\n" + "=" * 12, "create_agent 로 실행 (context 주입)", "=" * 12)
agent = create_agent(llm, tools=[my_orders], context_schema=UserContext)

for ctx in [UserContext(user_id="u-42", plan="pro"), UserContext(user_id="u-77", plan="free")]:
    result = agent.invoke(
        {"messages": [HumanMessage("내 최근 주문 목록 조회해 줘")]},
        context=ctx,  # 요청마다 서버가 인증 정보에서 채운다
        config={"recursion_limit": 10},  # 에이전트 루프 상한 (항상 둘 것)
    )
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    print(f"\n사용자 {ctx.user_id}:")
    print("  도구 결과:", tool_msgs[0].content if tool_msgs else "(도구 미호출)")
    print("  최종 답변:", result["messages"][-1].text[:70])
