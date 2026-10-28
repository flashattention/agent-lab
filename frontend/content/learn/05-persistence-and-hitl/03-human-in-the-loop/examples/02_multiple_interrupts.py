"""예제 2: 여러 개의 interrupt 다루기.

(1) 한 노드 안의 반복 interrupt — 입력 검증 루프 (사람이 잘못 답하면 다시 묻기)
(2) 병렬 노드의 동시 interrupt — interrupt id → 값 매핑으로 한 번에 재개
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

# ---------------------------------------------------------------------------
# (1) 입력 검증 루프
# ---------------------------------------------------------------------------
MAX_ASKS = 3  # 사람에게 묻는 횟수에도 상한을 둔다


class SignupState(TypedDict, total=False):
    name: str
    age: int
    note: str


def ask_age(state: SignupState) -> dict:
    """나이를 물어보고, 숫자가 아니면 다시 묻는다."""
    prompt = f"{state['name']}님의 나이를 숫자로 입력하세요"
    for attempt in range(1, MAX_ASKS + 1):
        answer = interrupt({"prompt": prompt, "attempt": attempt})
        # 재개 시 이 노드는 처음부터 실행된다.
        # 이미 답한 interrupt는 저장된 값을 '순서대로' 즉시 돌려주고, 새 interrupt에서만 멈춘다.
        if str(answer).isdigit():
            return {"age": int(answer)}
        prompt = f"'{answer}'은(는) 숫자가 아닙니다. 다시 입력하세요"
    return {"note": "입력 실패 - 상담원 연결 필요"}


b1 = StateGraph(SignupState)
b1.add_node("ask_age", ask_age)
b1.add_edge(START, "ask_age")
b1.add_edge("ask_age", END)
signup = b1.compile(checkpointer=InMemorySaver())

print("=" * 64)
print("(1) 입력 검증 루프")
print("=" * 64)
cfg = {"configurable": {"thread_id": "signup-1"}}
out = signup.invoke({"name": "민수"}, cfg, version="v2")
simulated_human_answers = ["스무살", "20"]  # 첫 답은 잘못, 두 번째는 올바름
for human in simulated_human_answers:
    print("  질문:", out.interrupts[0].value["prompt"], f"(시도 {out.interrupts[0].value['attempt']})")
    print("  사람:", human)
    out = signup.invoke(Command(resume=human), cfg, version="v2")
print("  결과:", out.value, "| 대기 중인 interrupt:", out.interrupts)
assert out.value["age"] == 20 and not out.interrupts

# ---------------------------------------------------------------------------
# (2) 병렬 검토: 법무팀과 보안팀이 동시에 검토
# ---------------------------------------------------------------------------


class ReviewState(TypedDict):
    doc: str
    approvals: Annotated[list[str], operator.add]  # 병렬 노드가 동시에 쓰므로 리듀서 필수


def legal_review(state: ReviewState) -> dict:
    verdict = interrupt({"team": "법무", "doc": state["doc"]})
    return {"approvals": [f"법무:{verdict}"]}


def security_review(state: ReviewState) -> dict:
    verdict = interrupt({"team": "보안", "doc": state["doc"]})
    return {"approvals": [f"보안:{verdict}"]}


def publish(state: ReviewState) -> dict:
    return {"approvals": ["게시 완료"]}


b2 = StateGraph(ReviewState)
b2.add_node("legal", legal_review)
b2.add_node("security", security_review)
b2.add_node("publish", publish)
b2.add_edge(START, "legal")  # START에서 두 갈래 → 같은 슈퍼스텝에서 병렬 실행
b2.add_edge(START, "security")
b2.add_edge(["legal", "security"], "publish")  # 둘 다 끝나야 publish
b2.add_edge("publish", END)
review = b2.compile(checkpointer=InMemorySaver())

print("\n" + "=" * 64)
print("(2) 병렬 노드의 동시 interrupt")
print("=" * 64)
cfg2 = {"configurable": {"thread_id": "release-notes-7"}}
out = review.invoke({"doc": "v2.0 릴리스 노트", "approvals": []}, cfg2, version="v2")
print(f"  대기 중인 interrupt {len(out.interrupts)}개:")
for intr in out.interrupts:
    print(f"    id={intr.id[:10]}…  value={intr.value}")

# 팀별로 다른 답을 id에 매핑해서 한 번에 재개
decisions = {"법무": "승인", "보안": "조건부 승인"}
resume_map = {intr.id: decisions[intr.value["team"]] for intr in out.interrupts}
out = review.invoke(Command(resume=resume_map), cfg2, version="v2")
print("  결과:", out.value["approvals"])
assert "게시 완료" in out.value["approvals"] and not out.interrupts
print("\n✔ 두 가지 다중 interrupt 패턴이 모두 동작했습니다.")
