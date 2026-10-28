"""4.2 실습 — 글 품질 검사기: 병렬 검사 결과를 리듀서로 합치기

과제
----
세 검사 노드(check_length, check_banned, check_style)가 '병렬로' 실행되며 같은 키에 결과를 씁니다.

    START ─┬─ check_length ─┐
           ├─ check_banned ─┼─ finalize → END
           └─ check_style  ─┘

1. ReviewState 의 issues  : 여러 노드의 지적 사항을 이어 붙이도록 operator.add 리듀서를 붙이세요.
2. ReviewState 의 penalty : 감점을 더하도록 operator.add 리듀서를 붙이세요.
3. merge_metrics 커스텀 리듀서를 구현하세요. 두 dict 를 합친 '새' dict 를 반환합니다(인자 수정 금지).
4. finalize 노드에서 score = max(0, 100 - penalty) 를 계산하세요.
5. 그래프의 출력은 OutputState(score, issues)로 제한하세요(output_schema).
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

BANNED = {"대박", "완전"}


def merge_metrics(current: dict, update: dict) -> dict:
    """두 지표 dict 를 합친 새 dict 를 반환한다."""
    # TODO: current 와 update 를 합친 '새' dict 를 반환하세요. (current.update(...) 금지)
    return current


class InputState(TypedDict):
    text: str


class OutputState(TypedDict):
    score: int
    issues: list[str]  # TODO: Annotated[..., operator.add] 로 바꾸세요


class ReviewState(InputState, OutputState):
    penalty: int  # TODO: 감점이 더해지도록 리듀서를 붙이세요
    metrics: dict  # TODO: merge_metrics 리듀서를 붙이세요


def check_length(state: ReviewState) -> dict:
    n = len(state["text"])
    issues = ["너무 짧음"] if n < 20 else []
    return {"issues": issues, "penalty": 30 if issues else 0, "metrics": {"chars": n}}


def check_banned(state: ReviewState) -> dict:
    found = [w for w in BANNED if w in state["text"]]
    return {
        "issues": [f"금칙어: {w}" for w in sorted(found)],
        "penalty": 10 * len(found),
        "metrics": {"banned": len(found)},
    }


def check_style(state: ReviewState) -> dict:
    exclaims = state["text"].count("!")
    issues = ["느낌표 과다"] if exclaims > 2 else []
    return {"issues": issues, "penalty": 5 if issues else 0, "metrics": {"exclaims": exclaims}}


def finalize(state: ReviewState) -> dict:
    # TODO: score = max(0, 100 - penalty) 를 반환하세요.
    return {}


# TODO: input_schema=InputState, output_schema=OutputState 를 지정하세요.
builder = StateGraph(ReviewState)
for fn in (check_length, check_banned, check_style, finalize):
    builder.add_node(fn)
for checker in ("check_length", "check_banned", "check_style"):
    builder.add_edge(START, checker)
builder.add_edge(["check_length", "check_banned", "check_style"], "finalize")
builder.add_edge("finalize", END)
graph = builder.compile()


# ----------------------------------------------------------------- 자가 채점
# 커스텀 리듀서: 새 dict 반환 + 인자 불변
a, b = {"x": 1}, {"y": 2}
assert merge_metrics(a, b) == {"x": 1, "y": 2}, "merge_metrics 는 두 dict 를 합쳐야 합니다"
assert a == {"x": 1}, "리듀서가 인자를 수정하면 안 됩니다"

good = graph.invoke({"text": "오늘 배운 리듀서 개념은 병렬 노드를 안전하게 만든다."})
assert set(good) == {"score", "issues"}, f"출력은 score, issues 만: {set(good)}"
assert good == {"score": 100, "issues": []}, good

bad = graph.invoke({"text": "완전 대박!!!"})
assert sorted(bad["issues"]) == sorted(["너무 짧음", "금칙어: 대박", "금칙어: 완전", "느낌표 과다"]), bad
assert bad["score"] == 100 - (30 + 20 + 5), bad

# 내부 상태에는 metrics 가 세 노드 결과를 모두 담고 있어야 한다
updates = [c for c in graph.stream({"text": "완전 대박!!!"}, stream_mode="updates")]
names = [next(iter(c)) for c in updates]
assert names[-1] == "finalize" and set(names[:3]) == {"check_length", "check_banned", "check_style"}

print("좋은 글:", good)
print("나쁜 글:", bad)
print("✅ 모든 테스트 통과!")
