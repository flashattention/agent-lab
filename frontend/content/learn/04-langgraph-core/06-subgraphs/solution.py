"""4.6 실습 — 두 가지 방식으로 서브그래프 조립하기 (정답)

과제
----
리뷰 분석 파이프라인을 두 개의 서브그래프로 조립합니다.

    부모: START → preprocess(공유 상태 서브그래프) → score(래퍼 노드: 변환 상태) → END

1. preprocess 서브그래프(이미 구현됨)는 부모와 review, tokens 키를 공유합니다.
   → 부모 그래프에 컴파일된 preprocess_graph 를 "preprocess" 라는 노드로 '직접' 추가하세요.
2. scorer 서브그래프(이미 구현됨)는 {words, positive, negative} 라는 전혀 다른 스키마를 씁니다.
   → score 래퍼 노드에서 tokens 를 words 로 넘겨 scorer_graph 를 invoke 하고,
     결과로 sentiment("긍정" | "부정" | "중립")와 score(= positive - negative)를 반환하세요.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

POSITIVE = {"좋아요", "최고", "빠름", "만족"}
NEGATIVE = {"별로", "느림", "불만", "고장"}


# ---------------------------------------------------------------- 부모 상태
class ReviewState(TypedDict, total=False):
    review: str
    tokens: list[str]
    score: int
    sentiment: str


# ---------------------------------------------------------------- 서브그래프 1: 공유 상태
class PreprocessState(TypedDict, total=False):
    review: str  # 부모와 공유
    tokens: list[str]  # 부모와 공유
    lowered: str  # 내부 전용


def lower(state: PreprocessState) -> dict:
    return {"lowered": state["review"].lower().replace(",", " ").replace(".", " ")}


def tokenize(state: PreprocessState) -> dict:
    return {"tokens": state["lowered"].split()}


pre = StateGraph(PreprocessState)
pre.add_node(lower)
pre.add_node(tokenize)
pre.add_edge(START, "lower")
pre.add_edge("lower", "tokenize")
pre.add_edge("tokenize", END)
preprocess_graph = pre.compile()


# ---------------------------------------------------------------- 서브그래프 2: 변환 상태
class ScorerState(TypedDict, total=False):
    words: list[str]
    positive: int
    negative: int


def count(state: ScorerState) -> dict:
    return {
        "positive": sum(w in POSITIVE for w in state["words"]),
        "negative": sum(w in NEGATIVE for w in state["words"]),
    }


sc = StateGraph(ScorerState)
sc.add_node(count)
sc.add_edge(START, "count")
sc.add_edge("count", END)
scorer_graph = sc.compile()


# ---------------------------------------------------------------- 부모 그래프
def score(state: ReviewState) -> dict:
    """래퍼 노드: 부모 → 자식 입력 변환, 자식 출력 → 부모 업데이트 변환"""
    out = scorer_graph.invoke({"words": state["tokens"]})
    value = out["positive"] - out["negative"]
    sentiment = "긍정" if value > 0 else "부정" if value < 0 else "중립"
    return {"score": value, "sentiment": sentiment}


builder = StateGraph(ReviewState)
builder.add_node("preprocess", preprocess_graph)
builder.add_node(score)
builder.add_edge(START, "preprocess")
builder.add_edge("preprocess", "score")
builder.add_edge("score", END)
graph = builder.compile()


# ----------------------------------------------------------------- 자가 채점
assert "preprocess" in graph.get_graph().nodes, "preprocess 노드를 추가하세요"
assert "preprocess:tokenize" in graph.get_graph(xray=True).nodes, "preprocess 는 컴파일된 서브그래프를 직접 추가해야 합니다"

cases = {
    "배송 빠름, 품질 최고. 만족 합니다": ("긍정", 3),
    "포장 별로, 배송 느림.": ("부정", -2),
    "그냥 그래요": ("중립", 0),
}
for text, (expected, value) in cases.items():
    out = graph.invoke({"review": text})
    assert "lowered" not in out, "서브그래프 내부 키(lowered)는 부모로 새면 안 됩니다"
    assert out.get("sentiment") == expected and out.get("score") == value, (text, out)
    print(f"{text:<22} → {out['sentiment']} ({out['score']:+d})")

namespaces = {ns for ns, _ in graph.stream({"review": "최고"}, stream_mode="updates", subgraphs=True)}
assert any(ns and ns[0].startswith("preprocess") for ns in namespaces), "서브그래프 내부 이벤트가 보여야 합니다"

print("✅ 모든 테스트 통과!")
