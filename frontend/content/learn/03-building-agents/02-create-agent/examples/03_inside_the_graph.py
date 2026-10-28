"""create_agent의 내부: LangGraph 그래프 들여다보기.

1) draw_mermaid()로 그래프 구조 출력
2) stream_mode="updates"로 노드 단위 실행 흐름 관찰
3) recursion_limit으로 반복 상한 걸기 (GraphRecursionError)
"""

import os

from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.errors import GraphRecursionError

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def search_docs(query: str) -> str:
    """사내 문서에서 query와 관련된 내용을 검색합니다."""
    return f"'{query[:20]}' 관련 문서 2건: 휴가 규정, 출장비 규정"


def main() -> None:
    agent = create_agent(MODEL, tools=[search_docs], system_prompt="사내 규정 도우미", name="docs_agent")

    print("=" * 60)
    print("1) 그래프 구조 (mermaid)")
    print("=" * 60)
    print(agent.get_graph().draw_mermaid())

    print("=" * 60)
    print("2) stream_mode='updates' → 노드가 끝날 때마다 변경분이 나온다")
    print("=" * 60)
    inputs = {"messages": [{"role": "user", "content": "출장비 규정 찾아줘"}]}
    for i, chunk in enumerate(agent.stream(inputs, stream_mode="updates"), start=1):
        for node_name, update in chunk.items():
            last = update["messages"][-1]
            detail = last.tool_calls[0]["name"] if getattr(last, "tool_calls", None) else str(last.content)[:50]
            print(f"  step {i}: [{node_name:<5}] {type(last).__name__:<11} {detail}")

    print("\n" + "=" * 60)
    print("3) recursion_limit: 상한을 너무 작게 잡으면?")
    print("=" * 60)
    for limit in (2, 10):
        try:
            out = agent.invoke(inputs, {"recursion_limit": limit})
            print(f"  limit={limit:>2} → 성공, 메시지 {len(out['messages'])}개")
        except GraphRecursionError:
            # 현업: 사용자에게 친절한 안내 + 로그/메트릭 기록
            print(f"  limit={limit:>2} → GraphRecursionError (model→tools→model 은 최소 3단계)")


if __name__ == "__main__":
    main()
