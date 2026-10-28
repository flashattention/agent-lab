"""예제 1: InMemoryStore 기본기 — 네임스페이스, put/get/search/list_namespaces/delete.

장기 메모리는 '폴더(네임스페이스) + 파일 이름(키) + JSON 내용(값)' 구조입니다.
"""

from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# 네임스페이스 첫 요소를 사용자 ID로 → 사용자별 경계가 자연스럽게 생긴다
minsu_mem = ("user-minsu", "memories")
minsu_profile = ("user-minsu", "profile")
jiyoung_mem = ("user-jiyoung", "memories")

print("=" * 60)
print("1) put: 메모리 저장")
print("=" * 60)
store.put(minsu_mem, "diet", {"text": "채식주의자", "kind": "food"})
store.put(minsu_mem, "allergy", {"text": "땅콩 알레르기", "kind": "health"})
store.put(minsu_mem, "hobby", {"text": "주말마다 등산", "kind": "lifestyle"})
store.put(minsu_profile, "main", {"name": "민수", "language": "ko", "tone": "친근하게"})
store.put(jiyoung_mem, "diet", {"text": "매운 음식을 좋아함", "kind": "food"})
print("저장 완료")

print("\n" + "=" * 60)
print("2) get: 키로 정확히 조회")
print("=" * 60)
item = store.get(minsu_mem, "allergy")
print("value     :", item.value)
print("namespace :", item.namespace, "/ key:", item.key)
print("created_at:", item.created_at)

print("\n" + "=" * 60)
print("3) search: 네임스페이스 접두사 + filter")
print("=" * 60)
food = store.search(minsu_mem, filter={"kind": "food"})
print("민수의 food 메모리:", [i.value["text"] for i in food])
everything_minsu = store.search(("user-minsu",))  # 접두사 검색: memories + profile 모두
print("민수의 모든 항목 수:", len(everything_minsu))
assert all(i.namespace[0] == "user-minsu" for i in everything_minsu), "다른 사용자 데이터가 섞이면 안 된다"

print("\n" + "=" * 60)
print("4) 같은 키로 다시 put = 덮어쓰기(upsert) → 프로필 갱신 패턴")
print("=" * 60)
before = store.get(minsu_profile, "main")
store.put(minsu_profile, "main", {**before.value, "tone": "간결하게"})
after = store.get(minsu_profile, "main")
print("tone:", before.value["tone"], "→", after.value["tone"])
print("updated_at 갱신:", before.updated_at, "→", after.updated_at)
assert store.get(minsu_profile, "main").value["name"] == "민수", "기존 필드는 우리가 합쳐서 넣었으므로 유지된다"

print("\n" + "=" * 60)
print("5) list_namespaces / delete")
print("=" * 60)
print("전체 네임스페이스:", store.list_namespaces())
print("민수 네임스페이스:", store.list_namespaces(prefix=("user-minsu",)))
store.delete(minsu_mem, "hobby")  # "잊어 줘" 요청 처리
print("hobby 삭제 후 get:", store.get(minsu_mem, "hobby"))
assert store.get(minsu_mem, "hobby") is None
print("\n✔ Store의 기본 연산을 모두 실행했습니다.")
