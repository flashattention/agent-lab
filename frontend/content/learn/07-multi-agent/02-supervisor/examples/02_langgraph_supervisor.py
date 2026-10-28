"""langgraph-supervisor 라이브러리로 같은 구조를 몇 줄 만에 만들기

create_supervisor 는 내부적으로
- 작업자마다 핸드오프 도구(transfer_to_<이름>)를 만들어 관리자에게 붙이고
- 작업자가 끝나면 transfer_back_to_supervisor 메시지를 자동으로 넣어
  관리자에게 제어를 돌려준다.

직접 구현(01 예제)과 달리 라우팅이 '구조화 출력'이 아니라 '도구 호출'로 이뤄진다는 점을 비교해 보자.
"""

import os

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain.tools import tool
from langgraph.errors import GraphRecursionError
from langgraph_supervisor import create_supervisor

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def search_web(query: str) -> str:
    """웹에서 자료를 검색한다."""
    return f"'{query}' 검색 결과: 2026년 서울 인구는 약 930만 명이다."


@tool
def multiply(a: float, b: float) -> float:
    """두 숫자를 곱한다."""
    return a * b


# 작업자: 반드시 name 을 지정해야 한다 (핸드오프 도구 이름이 여기서 만들어진다)
research_agent = create_agent(
    MODEL, tools=[search_web], system_prompt="당신은 조사 전문가입니다. 계산은 하지 마세요.", name="research_expert"
)
math_agent = create_agent(
    MODEL, tools=[multiply], system_prompt="당신은 계산 전문가입니다. 검색은 하지 마세요.", name="math_expert"
)

workflow = create_supervisor(
    [research_agent, math_agent],
    model=init_chat_model(MODEL),
    prompt=(
        "당신은 팀 관리자입니다. 조사는 research_expert, 계산은 math_expert 에게 맡기세요. "
        "한 번에 한 작업자에게만 일을 맡기고, 모든 답이 모이면 직접 최종 답변을 하세요."
    ),
    output_mode="last_message",  # 작업자의 '마지막 메시지'만 관리자 기록에 남긴다 (full_history 와 비교)
)
app = workflow.compile()  # create_supervisor 는 StateGraph 를 돌려주므로 compile 이 필요하다

if __name__ == "__main__":
    question = "서울 인구를 조사 전문가에게 검색시키고, 그 수에 2를 곱해 줘"
    print("질문:", question)
    print("=" * 60)
    try:
        # stream_mode="updates" 로 어떤 노드가 어떤 순서로 실행됐는지 관찰
        for chunk in app.stream({"messages": [HumanMessage(question)]}, {"recursion_limit": 30}, stream_mode="updates"):
            for node, update in chunk.items():
                print(f"▶ 노드 실행: {node}")
                for m in (update or {}).get("messages", []):
                    calls = getattr(m, "tool_calls", None)
                    body = f"tool_calls={[c['name'] for c in calls]}" if calls else m.text[:60]
                    print(f"    {type(m).__name__:12} name={m.name!s:18} {body}")
    except GraphRecursionError:
        # 실제 LLM 이 작업자 사이를 계속 오가면 여기서 멈춘다. 현업에서는 사용자에게 안전한 실패 메시지를 준다.
        print("⚠️ recursion_limit 에 도달해 중단했습니다. 프롬프트나 종료 조건을 점검하세요.")
    print("=" * 60)
    print("완료: 관리자 → 작업자 → 관리자 순서로 핸드오프가 일어났는지 확인하세요.")
