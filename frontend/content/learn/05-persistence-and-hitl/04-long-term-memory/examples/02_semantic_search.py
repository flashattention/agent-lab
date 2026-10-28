"""예제 2: 임베딩 index를 켠 Store로 시맨틱(의미) 검색하기.

API 키가 없으면 Mock 임베딩(단어 겹침 기반)이 쓰이므로 순위가 단순합니다.
키를 넣고 다시 실행해 실제 임베딩의 '의미 이해'와 비교해 보세요.
"""

from langchain_openai import OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(
    index={
        "embed": OpenAIEmbeddings(model="text-embedding-3-small"),
        "dims": 1536,  # text-embedding-3-small의 차원
        "fields": ["text"],  # 값 중 text 필드만 임베딩한다
    }
)

ns = ("user-minsu", "memories")
facts = {
    "f1": {"text": "땅콩 알레르기가 있어 땅콩 음식은 먹으면 안 된다", "kind": "health"},
    "f2": {"text": "고기를 먹지 않는 채식주의자 식단을 유지한다", "kind": "food"},
    "f3": {"text": "주말에는 북한산 등산을 즐긴다", "kind": "lifestyle"},
    "f4": {"text": "파이썬으로 데이터 분석 일을 한다", "kind": "work"},
    "f5": {"text": "매운 음식 중에서는 떡볶이를 가장 좋아한다", "kind": "food"},
}
for key, value in facts.items():
    store.put(ns, key, value)

# 임베딩하지 않을 큰 문서는 index=False (검색 비용·저장 비용 절약)
store.put(ns, "raw-log", {"text": "2026-10-01 상담 원문 전체 ...", "kind": "log"}, index=False)


def show(query: str, **kwargs) -> list:
    hits = store.search(ns, query=query, limit=3, **kwargs)
    print(f"\n질의: {query!r} {kwargs if kwargs else ''}")
    for h in hits:
        score = "None " if h.score is None else f"{h.score:.3f}"
        print(f"  score={score}  [{h.value['kind']:<9}] {h.value['text']}")
    return hits


print("=" * 64)
print("시맨틱 검색: query와 의미가 가까운 메모리 순으로")
print("=" * 64)
hits = show("저녁 음식 메뉴 추천할 때 주의할 점")
assert len(hits) == 3 and hits[0].score is not None

show("주말 취미 활동")

print("\n" + "=" * 64)
print("filter + query: 먼저 kind로 좁히고 그 안에서 의미 검색")
print("=" * 64)
food_hits = show("좋아하는 음식", filter={"kind": "food"})
assert all(h.value["kind"] == "food" for h in food_hits)

print("\n" + "=" * 64)
print("index=False 문서는 의미 점수가 없다(score=None)")
print("=" * 64)
log_hits = store.search(ns, query="상담 원문", filter={"kind": "log"})
print("  ", [(h.key, h.score) for h in log_hits])
assert log_hits[0].score is None
print("\n✔ 시맨틱 검색 예제 완료")
