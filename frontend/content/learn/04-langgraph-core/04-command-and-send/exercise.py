"""4.4 실습 — 과제 채점 Map-Reduce + Command 라우팅

과제
----
학생 답안 목록을 받아 '답안마다 병렬로' 채점하고, 평균 점수에 따라 다른 후속 노드로 보냅니다.

    START → dispatch ──Send×N──→ grade ──→ summarize ─(Command)─┬→ celebrate → END
                                                                 └→ remediate → END

1. ClassState.grades 에 operator.add 리듀서를 붙여 병렬 채점 결과를 모으세요.
2. fan_out: submissions 각각에 대해 Send("grade", {"student": ..., "answer": ..., "keywords": ...}) 를 만드세요.
3. grade : answer 에 포함된 keywords 비율 × 100 을 점수(int)로 계산해 grades 에 [{"student", "score"}] 로 넣으세요. (이미 구현됨)
4. summarize: 평균 점수(average)를 기록하면서, 평균 70 이상이면 "celebrate", 아니면 "remediate" 로
   Command(update=..., goto=...) 를 반환하세요.
"""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send


class ClassState(TypedDict, total=False):
    keywords: list[str]
    submissions: dict[str, str]  # 학생 이름 → 답안
    grades: list[dict]  # TODO: 병렬 결과를 모으도록 Annotated[..., operator.add] 로 바꾸세요
    average: float
    message: str


class GradeInput(TypedDict):
    student: str
    answer: str
    keywords: list[str]


def dispatch(state: ClassState) -> dict:
    return {}  # 준비 단계 (여기서는 할 일 없음)


def fan_out(state: ClassState) -> list[Send]:
    # TODO: submissions 의 (name, answer) 마다
    #       Send("grade", {"student": name, "answer": answer, "keywords": state["keywords"]}) 를 만들어
    #       리스트로 반환하세요.
    return []


def grade(state: GradeInput) -> dict:
    hits = sum(1 for k in state["keywords"] if k in state["answer"])
    score = round(hits / len(state["keywords"]) * 100)
    return {"grades": [{"student": state["student"], "score": score}]}


def summarize(state: ClassState) -> Command[Literal["celebrate", "remediate"]]:
    scores = [g["score"] for g in state.get("grades", [])]
    average = sum(scores) / len(scores) if scores else 0.0
    # TODO: average 를 update 에 담고, 평균 70 이상이면 "celebrate", 아니면 "remediate" 로 가는
    #       Command 를 반환하세요.
    return Command(update={}, goto="remediate")


def celebrate(state: ClassState) -> dict:
    return {"message": f"평균 {state['average']:.1f}점! 다음 단원으로 넘어갑니다."}


def remediate(state: ClassState) -> dict:
    low = sorted(g["student"] for g in state["grades"] if g["score"] < 70)
    return {"message": f"평균 {state['average']:.1f}점. 보충 대상: {', '.join(low)}"}


builder = StateGraph(ClassState)
for fn in (dispatch, grade, summarize, celebrate, remediate):
    builder.add_node(fn)
builder.add_edge(START, "dispatch")
builder.add_conditional_edges("dispatch", fan_out, ["grade"])
builder.add_edge("grade", "summarize")
builder.add_edge("celebrate", END)
builder.add_edge("remediate", END)
graph = builder.compile()


# ----------------------------------------------------------------- 자가 채점
KEYWORDS = ["상태", "노드", "엣지", "리듀서"]
strong = graph.invoke(
    {
        "keywords": KEYWORDS,
        "submissions": {
            "민준": "상태와 노드, 엣지, 리듀서로 구성된다",
            "서연": "노드와 엣지와 상태가 핵심이다",
            "지우": "상태, 노드, 엣지, 리듀서 모두 중요",
        },
    }
)
assert len(strong.get("grades", [])) == 3, "학생 수만큼 grade 가 실행되어야 합니다 (Send + 리듀서)"
assert {g["student"]: g["score"] for g in strong["grades"]} == {"민준": 100, "서연": 75, "지우": 100}
assert strong["message"].startswith("평균 91.7점"), strong["message"]

weak = graph.invoke(
    {
        "keywords": KEYWORDS,
        "submissions": {"하준": "잘 모르겠어요", "도윤": "노드가 있다", "수아": "상태와 노드와 엣지와 리듀서"},
    }
)
assert "보충 대상: 도윤, 하준" in weak["message"], weak["message"]

steps = [next(iter(c)) for c in graph.stream({"keywords": KEYWORDS, "submissions": {"a": "상태", "b": "노드"}},
                                             stream_mode="updates")]
assert steps.count("grade") == 2 and steps.count("summarize") == 1, steps

print(graph.get_graph().draw_mermaid())
print("우수 반:", strong["message"])
print("보충 반:", weak["message"])
print("✅ 모든 테스트 통과!")
