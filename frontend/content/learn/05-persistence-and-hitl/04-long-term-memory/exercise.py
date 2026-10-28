"""실습: 스레드를 넘어 기억하는 '선호도 메모' 그래프

그래프: remember → recall
- remember: 입력에 note가 있으면 그 사용자의 장기 메모리에 저장한다.
- recall  : 그 사용자의 장기 메모리를 모두 읽어 상태의 memories에 넣는다.
사용자 ID는 반드시 Runtime context(서버가 인증한 값)에서 가져옵니다.

할 일
1. TODO 1: 사용자별 네임스페이스를 돌려주는 함수를 완성하세요. 형식: (user_id, "notes")
2. TODO 2: remember 노드에서 runtime.store.put으로 note를 저장하세요. 키는 uuid 문자열, 값은 {"text": note}.
3. TODO 3: recall 노드에서 runtime.store.search로 그 사용자의 메모를 모두 가져와 text 목록을 만드세요.
4. TODO 4: 그래프를 컴파일할 때 store를 붙이세요. (단기 메모리용 checkpointer도 함께)
"""

import uuid
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore


def todo(value, hint: str):
    """빈칸(None)이 남아 있으면 친절한 메시지와 함께 멈춘다."""
    if value is None:
        raise NotImplementedError(f"아직 채우지 않은 빈칸이 있습니다: {hint}")
    return value


class Context(TypedDict):
    user_id: str


class NoteState(TypedDict, total=False):
    note: str
    memories: list[str]


def notes_ns(user_id: str) -> tuple[str, str]:
    # TODO 1
    return todo(None, "TODO 1 - (user_id, 'notes') 튜플 반환")


def remember(state: NoteState, runtime: Runtime[Context]) -> dict:
    note = state.get("note")
    if note:
        # TODO 2
        #         힌트: runtime.store.put(네임스페이스, 키, 값)  /  사용자 ID: runtime.context["user_id"]
        todo(None, "TODO 2 - runtime.store.put(...)")
    return {}


def recall(state: NoteState, runtime: Runtime[Context]) -> dict:
    # TODO 3
    #         힌트: runtime.store.search(네임스페이스, limit=50) → 각 item.value["text"]
    texts = todo(None, "TODO 3 - store.search 결과에서 text 목록 만들기")
    return {"memories": texts}


builder = StateGraph(NoteState, context_schema=Context)
builder.add_node("remember", remember)
builder.add_node("recall", recall)
builder.add_edge(START, "remember")
builder.add_edge("remember", "recall")
builder.add_edge("recall", END)

store = InMemoryStore()
# TODO 4
graph = builder.compile(checkpointer=InMemorySaver())  # ← store가 빠졌습니다


def run(thread_id: str, user_id: str, note: str | None = None) -> list[str]:
    config = {"configurable": {"thread_id": thread_id}}
    inputs: NoteState = {"note": note} if note else {"note": ""}
    out = graph.invoke(inputs, config, context={"user_id": user_id})
    return out["memories"]


# 민수: 서로 다른 세 개의 스레드(대화)에서 메모
run("minsu-mon", "minsu", "땅콩 알레르기")
run("minsu-tue", "minsu", "채식주의자")
minsu_wed = run("minsu-wed", "minsu")  # 메모 없이 조회만
# 지영: 별도 사용자
jiyoung = run("jiyoung-mon", "jiyoung", "매운 음식 좋아함")

print("민수(수요일 새 스레드)가 기억하는 것:", minsu_wed)
print("지영이 기억하는 것:", jiyoung)

# ---- 자가 채점 ----
assert notes_ns("abc") == ("abc", "notes"), "TODO 1: 네임스페이스 형식을 확인하세요"
assert sorted(minsu_wed) == ["땅콩 알레르기", "채식주의자"], "새 스레드에서도 이전 스레드의 메모가 보여야 합니다"
assert jiyoung == ["매운 음식 좋아함"], "다른 사용자의 메모가 섞이면 안 됩니다"
assert len(store.search(("minsu",))) == 2, "store에 실제로 저장되어야 합니다"
print("✅ 모든 테스트 통과!")
