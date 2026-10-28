"""예제 1: 리플레이(Replay) — 과거 체크포인트에서 다시 실행하기.

plan → search → answer 3단계 그래프를 한 번 실행한 뒤,
'search 실행 직전' 체크포인트를 찾아 그 지점부터 다시 실행합니다.
노드별 실행 횟수를 세어, 리플레이 지점 이전 노드는 다시 실행되지 않음을 확인합니다.
"""

from collections import Counter
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

RUN_COUNT: Counter = Counter()  # 노드별 실행 횟수


class ResearchState(TypedDict, total=False):
    question: str
    query: str
    docs: str
    answer: str


def plan(state: ResearchState) -> dict:
    RUN_COUNT["plan"] += 1
    return {"query": state["question"].replace("?", "").strip()}


def search(state: ResearchState) -> dict:
    RUN_COUNT["search"] += 1
    # 실제라면 검색 API 호출. 여기서는 실행 횟수를 결과에 섞어 '다시 실행됨'을 보이게 한다
    return {"docs": f"'{state['query']}' 검색 결과 (search 실행 #{RUN_COUNT['search']})"}


def answer(state: ResearchState) -> dict:
    RUN_COUNT["answer"] += 1
    return {"answer": f"근거: {state['docs']}"}


builder = StateGraph(ResearchState)
builder.add_node("plan", plan)
builder.add_node("search", search)
builder.add_node("answer", answer)
builder.add_edge(START, "plan")
builder.add_edge("plan", "search")
builder.add_edge("search", "answer")
builder.add_edge("answer", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "research-1"}}

print("=" * 64)
print("1) 처음 실행")
print("=" * 64)
first = graph.invoke({"question": "체크포인터란?"}, config)
print("answer   :", first["answer"])
print("실행 횟수:", dict(RUN_COUNT))

print("\n" + "=" * 64)
print("2) 체크포인트 이력 (최신 → 과거)")
print("=" * 64)
history = list(graph.get_state_history(config))
for snap in history:
    print(f"  step={snap.metadata['step']:>2}  next={str(snap.next):<14} keys={sorted(snap.values)}")

# 'search가 실행되기 직전' = next에 search가 들어 있는 체크포인트
before_search = next(s for s in history if s.next == ("search",))
print("\n선택한 체크포인트: step", before_search.metadata["step"], "/ next =", before_search.next)
print("그 시점의 상태  :", before_search.values)

print("\n" + "=" * 64)
print("3) 리플레이: invoke(None, 과거 config)")
print("=" * 64)
replayed = graph.invoke(None, before_search.config)  # 입력 None = 새 입력 없이 이어서 실행
print("answer   :", replayed["answer"])
print("실행 횟수:", dict(RUN_COUNT))

assert RUN_COUNT["plan"] == 1, "plan은 리플레이 지점 이전이므로 다시 실행되지 않는다"
assert RUN_COUNT["search"] == 2 and RUN_COUNT["answer"] == 2

new_history = list(graph.get_state_history(config))
print(f"\n체크포인트 수: {len(history)} → {len(new_history)} (원래 이력은 보존되고 새 가지가 추가됨)")
print("현재(최신) 상태의 answer:", graph.get_state(config).values["answer"])
