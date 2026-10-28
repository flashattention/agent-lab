"""4.1 예제 2 — 팬아웃(fan-out)과 팬인(fan-in).

parse 다음에 두 검사 노드가 '같은 슈퍼스텝'에서 병렬 실행되고,
add_edge([...], "decide") 로 두 노드가 모두 끝난 뒤에 decide 가 실행된다.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

BANNED_WORDS = {"바보", "멍청이"}


class ReviewState(TypedDict, total=False):
    text: str
    tokens: list[str]
    length_ok: bool  # check_length 가 쓰는 키
    clean_ok: bool  # check_profanity 가 쓰는 키 (서로 다른 키 → 충돌 없음)
    verdict: str


def parse(state: ReviewState) -> dict:
    return {"tokens": state["text"].split()}


def check_length(state: ReviewState) -> dict:
    """리뷰가 3단어 이상 50단어 이하인지 검사."""
    n = len(state["tokens"])
    return {"length_ok": 3 <= n <= 50}


def check_profanity(state: ReviewState) -> dict:
    """금칙어 포함 여부 검사."""
    return {"clean_ok": not any(t in BANNED_WORDS for t in state["tokens"])}


def decide(state: ReviewState) -> dict:
    ok = state["length_ok"] and state["clean_ok"]
    return {"verdict": "게시 승인" if ok else "검토 필요"}


builder = StateGraph(ReviewState)
for fn in (parse, check_length, check_profanity, decide):
    builder.add_node(fn)

builder.add_edge(START, "parse")
builder.add_edge("parse", "check_length")  # 팬아웃: parse → 두 노드
builder.add_edge("parse", "check_profanity")
builder.add_edge(["check_length", "check_profanity"], "decide")  # 팬인: 둘 다 끝나야 실행
builder.add_edge("decide", END)
graph = builder.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())

    reviews = [
        "배송이 빠르고 품질도 정말 좋아요",
        "이걸 판 사람은 바보 입니다",
        "별로",
    ]
    for text in reviews:
        print("-" * 60)
        print(f"입력: {text}")
        # stream_mode="debug" 이벤트에는 슈퍼스텝 번호(step)가 들어 있다.
        # check_length / check_profanity 가 같은 step 에서 실행되는 것을 확인하자.
        for event in graph.stream({"text": text}, stream_mode="debug"):
            if event["type"] == "task_result":  # 노드 실행이 끝난 이벤트만 출력
                payload = event["payload"]
                print(f"  superstep {event['step']}: {payload['name']:<16} → {dict(payload['result'])}")
        print("  최종 판정:", graph.invoke({"text": text})["verdict"])
