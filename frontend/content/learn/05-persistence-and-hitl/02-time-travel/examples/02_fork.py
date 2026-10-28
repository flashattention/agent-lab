"""예제 2: 포크(Fork) — 과거 상태를 고쳐 다른 미래 만들기.

plan 노드가 나쁜 검색어("랭그래프")를 골라 엉뚱한 답이 나왔다고 가정합니다.
- 포크 A: search 직전으로 돌아가 query만 고쳐서 다시 실행 (as_node 생략 → search부터)
- 포크 B: as_node="search"로 사람이 검색 결과를 직접 넣음 (search는 건너뛰고 answer부터)
"""

from collections import Counter
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

RUN_COUNT: Counter = Counter()

FAKE_INDEX = {
    "LangGraph checkpointer": "체크포인터는 슈퍼스텝마다 상태를 저장한다.",
}


class ResearchState(TypedDict, total=False):
    question: str
    query: str
    docs: str
    answer: str


def plan(state: ResearchState) -> dict:
    RUN_COUNT["plan"] += 1
    return {"query": "랭그래프"}  # 일부러 나쁜 검색어


def search(state: ResearchState) -> dict:
    RUN_COUNT["search"] += 1
    return {"docs": FAKE_INDEX.get(state["query"], "관련 문서를 찾지 못했습니다.")}


def answer(state: ResearchState) -> dict:
    RUN_COUNT["answer"] += 1
    return {"answer": f"[query={state['query']}] {state['docs']}"}


builder = StateGraph(ResearchState)
builder.add_node("plan", plan)
builder.add_node("search", search)
builder.add_node("answer", answer)
builder.add_edge(START, "plan")
builder.add_edge("plan", "search")
builder.add_edge("search", "answer")
builder.add_edge("answer", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "research-2"}}
original = graph.invoke({"question": "LangGraph 체크포인터가 뭐야?"}, config)
print("원래 결과 :", original["answer"])

# search 직전 체크포인트 찾기
before_search = next(s for s in graph.get_state_history(config) if s.next == ("search",))

print("\n" + "=" * 64)
print("포크 A: query만 고치고 search부터 다시 실행")
print("=" * 64)
fork_a = graph.update_state(before_search.config, {"query": "LangGraph checkpointer"})
print("포크 A의 next:", graph.get_state(fork_a).next)  # ('search',) 유지
result_a = graph.invoke(None, fork_a)
print("포크 A 결과 :", result_a["answer"])

print("\n" + "=" * 64)
print("포크 B: as_node='search' → 사람이 search 결과를 직접 제공")
print("=" * 64)
search_before = RUN_COUNT["search"]
fork_b = graph.update_state(
    before_search.config,
    {"docs": "(사람이 직접 입력) 체크포인터 = 세이브 파일 자동 저장 기능"},
    as_node="search",  # "search가 방금 이 값을 반환했다"고 간주
)
print("포크 B의 next:", graph.get_state(fork_b).next)  # ('answer',) → search 건너뜀
result_b = graph.invoke(None, fork_b)
print("포크 B 결과 :", result_b["answer"])
assert RUN_COUNT["search"] == search_before, "포크 B에서는 search가 실행되지 않아야 한다"

print("\n" + "=" * 64)
print("이력 살펴보기: source='update'는 update_state로 만든 체크포인트")
print("=" * 64)
for s in graph.get_state_history(config):
    mark = "  ← 사람이 고친 지점" if s.metadata["source"] == "update" else ""
    print(f"step={s.metadata['step']:>2} source={s.metadata['source']:<6} next={str(s.next):<12}{mark}")

print("\n노드 실행 횟수:", dict(RUN_COUNT))
print("plan은 1번만 실행되었습니다. 포크는 앞 단계를 다시 실행하지 않습니다.")
assert RUN_COUNT["plan"] == 1
