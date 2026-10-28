"""실습: 번역 파이프라인을 타임 트래블로 고치기

그래프: draft → translate → publish
- draft: 원문을 정한다 (일부러 오타가 있는 원문 "helo world")
- translate: 원문을 대문자로 '번역'한다 (가짜 번역기)
- publish: 결과를 게시한다

원문 오타 때문에 게시물이 "HELO WORLD"가 되었습니다. 처음부터 다시 돌리지 말고 타임 트래블로 고치세요.

할 일
1. TODO 1: 체크포인트 이력에서 'translate 실행 직전' 스냅샷을 찾으세요.
2. TODO 2: 그 시점에서 text를 "hello world"로 고친 포크를 만드세요 (update_state).
3. TODO 3: 포크 지점부터 실행하세요.
4. TODO 4: 같은 지점에서 as_node="translate"로 사람이 번역문 "안녕 세상"을 직접 넣는 포크를 만들고 실행하세요.
"""

from collections import Counter
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

RUNS: Counter = Counter()


class PostState(TypedDict, total=False):
    text: str
    published: str


def draft(state: PostState) -> dict:
    RUNS["draft"] += 1
    return {"text": "helo world"}  # 오타!


def translate(state: PostState) -> dict:
    RUNS["translate"] += 1
    return {"text": state["text"].upper()}


def publish(state: PostState) -> dict:
    RUNS["publish"] += 1
    return {"published": f"게시됨: {state['text']}"}


builder = StateGraph(PostState)
builder.add_node("draft", draft)
builder.add_node("translate", translate)
builder.add_node("publish", publish)
builder.add_edge(START, "draft")
builder.add_edge("draft", "translate")
builder.add_edge("translate", "publish")
builder.add_edge("publish", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "post-1"}}
original = graph.invoke({}, config)
print("원래 결과:", original["published"])

# TODO 1: next가 ("translate",)인 스냅샷 찾기
before_translate = next(s for s in graph.get_state_history(config) if s.next == ("translate",))

# TODO 2: text를 고친 포크 만들기
fix_config = graph.update_state(before_translate.config, {"text": "hello world"})

# TODO 3: 포크 지점부터 실행
fixed = graph.invoke(None, fix_config)
print("포크 1 결과:", fixed["published"])

# TODO 4: as_node="translate"로 사람이 번역문을 넣고 실행
manual_config = graph.update_state(before_translate.config, {"text": "안녕 세상"}, as_node="translate")
manual = graph.invoke(None, manual_config)
print("포크 2 결과:", manual["published"])
print("실행 횟수:", dict(RUNS))

# ---- 자가 채점 ----
assert original["published"] == "게시됨: HELO WORLD"
assert before_translate.values["text"] == "helo world", "TODO 1: translate 직전 상태를 골라야 합니다"
assert fixed["published"] == "게시됨: HELLO WORLD", "TODO 2/3: 고친 원문이 번역되어 게시되어야 합니다"
assert manual["published"] == "게시됨: 안녕 세상", "TODO 4: as_node로 translate를 건너뛰어야 합니다"
assert RUNS["draft"] == 1, "draft는 다시 실행되면 안 됩니다 (타임 트래블의 핵심)"
assert RUNS["translate"] == 2, "translate는 원래 1번 + 포크 1에서 1번만 실행되어야 합니다"
assert graph.get_state(config).values["published"] == "게시됨: 안녕 세상", "최신 상태는 마지막 포크의 결과"
print("✅ 모든 테스트 통과!")
