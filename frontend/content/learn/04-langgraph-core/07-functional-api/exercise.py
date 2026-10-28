"""4.7 실습 — Functional API로 '새 글만' 요약하는 뉴스 다이제스트

과제
----
매번 실행할 때 '아직 보지 않은 기사'만 병렬로 요약해 다이제스트를 만드는 워크플로입니다.

1. news_digest 는 체크포인터(InMemorySaver)를 가진 entrypoint 입니다. (이미 설정됨)
2. previous(지난 실행에서 저장한 '본 기사 id 목록')를 이용해 새 기사만 고르세요.
3. 새 기사들을 summarize task 로 '병렬' 요약하세요. (퓨처를 먼저 모두 만든 뒤 .result())
4. entrypoint.final 로
     value = {"digest": [요약들], "new_count": 새 기사 수}
     save  = 지금까지 본 기사 id 전체 목록 (정렬된 list)
   을 반환하세요.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

ARTICLES = {
    1: "LangGraph 1.2 출시, 노드 타임아웃 지원",
    2: "에이전트 평가 방법론 정리",
    3: "MCP 서버 생태계 확장",
    4: "벡터 DB 하이브리드 검색 벤치마크",
}


@task
def fetch_ids(limit: int) -> list[int]:
    """'현재 피드에 있는 기사 id 목록'을 가져온다 (외부 API 라고 가정)."""
    return sorted(ARTICLES)[:limit]


@task
def summarize(article_id: int) -> str:
    """기사 하나를 요약한다 (LLM 호출이라고 가정)."""
    return f"[{article_id}] {ARTICLES[article_id]}"


@entrypoint(checkpointer=InMemorySaver())
def news_digest(limit: int, *, previous: list[int] | None = None):
    seen = set(previous or [])
    ids = fetch_ids(limit).result()

    # TODO: ids 중 seen 에 없는 것만 new_ids 로 고르세요.
    new_ids: list[int] = []

    # TODO: new_ids 각각에 summarize task 를 '먼저 모두' 호출해 퓨처를 만들고, 그다음 .result() 로 모으세요.
    digest: list[str] = []

    # TODO: entrypoint.final(value={"digest": ..., "new_count": ...}, save=본 기사 id 전체 정렬 목록) 을 반환하세요.
    return {"digest": digest, "new_count": len(new_ids)}


# ----------------------------------------------------------------- 자가 채점
cfg = {"configurable": {"thread_id": "reader-1"}}

first = news_digest.invoke(2, cfg)  # 피드에 기사 1, 2
assert first == {"digest": ["[1] LangGraph 1.2 출시, 노드 타임아웃 지원", "[2] 에이전트 평가 방법론 정리"], "new_count": 2}, first

second = news_digest.invoke(4, cfg)  # 피드에 1~4, 그중 3, 4만 새 글
assert second["new_count"] == 2 and [d[:3] for d in second["digest"]] == ["[3]", "[4]"], second

third = news_digest.invoke(4, cfg)  # 새 글 없음
assert third == {"digest": [], "new_count": 0}, third

# 다른 스레드는 기억을 공유하지 않는다
fresh = news_digest.invoke(4, {"configurable": {"thread_id": "reader-2"}})
assert fresh["new_count"] == 4, fresh

# 병렬 요약이 task 로 실행되었는지 이벤트로 확인
events = [next(iter(c)) for c in news_digest.stream(3, {"configurable": {"thread_id": "r3"}}, stream_mode="updates")]
assert events.count("summarize") == 3 and events[0] == "fetch_ids", events

print("1회차:", first)
print("2회차:", second)
print("3회차:", third)
print("✅ 모든 테스트 통과!")
