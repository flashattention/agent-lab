"""컨텍스트 윈도우 관리: 일시적 트리밍 vs 요약.

A) wrap_model_call + trim_messages : 모델에게만 최근 메시지를 보여 준다 (저장 기록은 그대로)
B) SummarizationMiddleware          : 오래된 메시지를 요약 메시지로 '교체'한다 (저장 기록이 바뀜)
"""

import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, SummarizationMiddleware, wrap_model_call
from langchain.messages import trim_messages
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
SUMMARY_MODEL = "openai:gpt-5-nano"  # 요약은 저렴한 모델로
SEEN_BY_MODEL: list[int] = []  # 데모용: 모델이 실제로 받은 메시지 수


@wrap_model_call
def keep_recent(request: ModelRequest, handler) -> ModelResponse:
    """모델 호출 직전에만 메시지를 잘라서 보여 준다."""
    trimmed = trim_messages(
        request.messages,
        max_tokens=60,  # 데모용으로 아주 작게. 현업에서는 수천 토큰 단위
        token_counter="approximate",
        strategy="last",  # 최근 메시지부터 남긴다
        start_on="human",  # Human 메시지에서 시작 → tool_call/ToolMessage 짝이 깨지지 않게
    )
    SEEN_BY_MODEL.append(len(trimmed))
    return handler(request.override(messages=trimmed))


def chat(agent, thread_id: str, turns: int) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result: dict = {}
    for i in range(1, turns + 1):
        result = agent.invoke({"messages": [{"role": "user", "content": f"{i}번째 질문: 오늘의 추천 메뉴는?"}]}, config)
    return result


def main() -> None:
    print("=" * 60)
    print("A) 일시적 트리밍 (wrap_model_call + trim_messages)")
    print("=" * 60)
    agent_a = create_agent(MODEL, tools=[], middleware=[keep_recent], checkpointer=InMemorySaver())
    result = chat(agent_a, "trim-demo", turns=5)
    print("  저장된 전체 메시지 수   :", len(result["messages"]))
    print("  턴별로 모델이 본 메시지 :", SEEN_BY_MODEL)
    print("  → 기록은 모두 보존되고, 모델 입력만 짧게 유지됩니다.")

    print("\n" + "=" * 60)
    print("B) 요약 (SummarizationMiddleware)")
    print("=" * 60)
    agent_b = create_agent(
        MODEL,
        tools=[],
        middleware=[
            SummarizationMiddleware(
                model=SUMMARY_MODEL,
                trigger=("messages", 6),  # 메시지가 6개 이상이면 요약 (현업: ("tokens", 4000) 등)
                keep=("messages", 2),  # 최근 2개는 원문 유지
            )
        ],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "summary-demo"}}
    for i in range(1, 6):
        out = agent_b.invoke({"messages": [{"role": "user", "content": f"{i}번째 질문: 여행지 추천해줘"}]}, config)
        first = str(out["messages"][0].content).replace("\n", " ")[:45]
        print(f"  턴 {i}: 저장된 메시지 {len(out['messages'])}개 | 첫 메시지: {first}")
    print("  → 기준을 넘으면 오래된 메시지가 요약 1개로 교체되어 기록 자체가 짧아집니다.")


if __name__ == "__main__":
    main()
