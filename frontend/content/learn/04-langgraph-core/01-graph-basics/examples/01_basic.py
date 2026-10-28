"""4.1 예제 1 — 가장 단순한 StateGraph: 텍스트 처리 3단계 파이프라인.

LLM 없이 순수 Python 함수만으로 그래프의 뼈대(상태, 노드, 엣지, compile, invoke, stream)를 익힌다.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# 1) 상태(State): 그래프 전체가 공유하는 데이터의 "키 목록"을 선언한다.
class TextState(TypedDict):
    raw: str  # 입력 원문
    cleaned: str  # 공백 정리된 텍스트
    word_count: int  # 단어 수
    report: str  # 최종 보고서


# 2) 노드(Node): 상태를 받아 "바뀐 키만" 담은 dict를 반환하는 평범한 함수.
def normalize(state: TextState) -> dict:
    """앞뒤 공백 제거 + 연속 공백을 하나로 줄인다."""
    cleaned = " ".join(state["raw"].split())
    return {"cleaned": cleaned}  # 상태 전체가 아니라 업데이트만!


def count_words(state: TextState) -> dict:
    """정리된 텍스트의 단어 수를 센다."""
    return {"word_count": len(state["cleaned"].split())}


def summarize(state: TextState) -> dict:
    """앞 단계의 결과를 모아 보고서 문자열을 만든다."""
    preview = state["cleaned"][:30]
    return {"report": f"'{preview}' → 단어 {state['word_count']}개"}


# 3) 그래프 조립 (빌더 패턴)
builder = StateGraph(TextState)
builder.add_node("normalize", normalize)  # 이름을 직접 지정
builder.add_node(count_words)  # 이름 생략 → 함수 이름이 노드 이름
builder.add_node(summarize)

builder.add_edge(START, "normalize")
builder.add_edge("normalize", "count_words")
builder.add_edge("count_words", "summarize")
builder.add_edge("summarize", END)

# 4) 컴파일: 구조 검증 + 실행 가능한 앱 생성
graph = builder.compile()

if __name__ == "__main__":
    print("=" * 60)
    print("① 그래프 구조 (Mermaid)")
    print("=" * 60)
    print(graph.get_graph().draw_mermaid())

    user_input = {"raw": "   LangGraph 는    그래프로   에이전트를   만든다   "}

    print("=" * 60)
    print("② stream(stream_mode='updates') — 노드별 업데이트")
    print("=" * 60)
    for i, chunk in enumerate(graph.stream(user_input, stream_mode="updates"), start=1):
        # chunk 형태: {"노드이름": {업데이트 dict}}
        for node_name, update in chunk.items():
            print(f"[#{i}] {node_name:<12} → {update}")

    print("=" * 60)
    print("③ invoke — 최종 상태")
    print("=" * 60)
    final_state = graph.invoke(user_input)
    for key, value in final_state.items():
        print(f"  {key:<11}: {value!r}")

    # 노드는 그냥 함수이므로 그래프 없이도 테스트할 수 있다.
    assert normalize({"raw": "  a   b "}) == {"cleaned": "a b"}
    print("\n노드 단위 테스트 통과 ✔")
