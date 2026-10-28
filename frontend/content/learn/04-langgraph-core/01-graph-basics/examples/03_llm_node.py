"""4.1 예제 3 — LLM 노드도 그냥 노드다.

예제 1의 파이프라인에서 summarize 노드만 LLM 호출로 바꾼다.
API 키가 없으면 Mock 모델이 응답하지만 그래프 흐름은 동일하게 동작한다.
"""

import os
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)  # temperature 는 설정하지 않는다 (GPT-5 계열 추론 모델은 거부)


class TextState(TypedDict, total=False):
    raw: str
    cleaned: str
    word_count: int
    report: str
    tokens_used: int


def normalize(state: TextState) -> dict:
    return {"cleaned": " ".join(state["raw"].split())}


def count_words(state: TextState) -> dict:
    return {"word_count": len(state["cleaned"].split())}


def summarize_with_llm(state: TextState) -> dict:
    """결정적 단계(normalize, count_words)의 결과를 LLM에 넘겨 한 줄 요약을 만든다."""
    messages = [
        SystemMessage("너는 간결한 편집자다. 한 문장으로만 답한다."),
        HumanMessage(f"다음 글을 한 줄로 요약해 줘 (단어 {state['word_count']}개):\n{state['cleaned']}"),
    ]
    ai = llm.invoke(messages)
    usage = ai.usage_metadata or {}
    return {"report": ai.content, "tokens_used": usage.get("total_tokens", 0)}


builder = StateGraph(TextState)
builder.add_node(normalize)
builder.add_node(count_words)
builder.add_node("summarize", summarize_with_llm)  # 노드 이름은 그대로, 구현만 교체
builder.add_edge(START, "normalize")
builder.add_edge("normalize", "count_words")
builder.add_edge("count_words", "summarize")
builder.add_edge("summarize", END)
graph = builder.compile()

if __name__ == "__main__":
    text = """
        LangGraph 는 상태와 노드와 엣지로 에이전트의 흐름을 명시한다.
        덕분에 중단 후 재개, 병렬 실행, 스트리밍, 추적이 쉬워진다.
    """
    for chunk in graph.stream({"raw": text}, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"[{node}]")
            for k, v in update.items():
                print(f"   {k}: {v}")
    print("\n✔ 그래프 실행 완료 (Mock 모드라면 응답 내용 대신 흐름을 확인하세요)")
