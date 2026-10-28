"""4.7 예제 1 — @entrypoint / @task 기초와 병렬 실행.

task 호출은 '퓨처'를 돌려준다.
- 호출하자마자 .result()  → 순차 실행
- 퓨처를 먼저 모두 만들고 나중에 .result() → 병렬 실행
"""

import time

from langgraph.func import entrypoint, task

PROFILES = {"u1": {"name": "김랭", "plan": "pro"}, "u2": {"name": "이그래프", "plan": "free"}}


# ---------------------------------------------------------------- 1) 가장 단순한 워크플로
@task
def fetch_profile(user_id: str) -> dict:
    return PROFILES[user_id]


@task
def write_greeting(profile: dict) -> str:
    badge = "⭐" if profile["plan"] == "pro" else ""
    return f"{profile['name']}님{badge}, 안녕하세요!"


@entrypoint()
def greet(user_id: str) -> str:
    """entrypoint 는 인자를 하나만 받는다. 여러 값이 필요하면 dict 로 묶는다."""
    profile = fetch_profile(user_id).result()  # task → future → .result()
    return write_greeting(profile).result()


print("=" * 60)
print("① 기본 워크플로")
print("  greet 의 타입:", type(greet).__name__, "(컴파일된 그래프와 같은 종류)")
print("  invoke:", greet.invoke("u1"))
print("  stream(updates):")
for chunk in greet.stream("u2", stream_mode="updates"):
    print("    ", chunk)  # task 이름별 결과가 차례로 나온다


# ---------------------------------------------------------------- 2) 순차 vs 병렬
@task
def slow_summarize(topic: str) -> str:
    time.sleep(0.3)  # 외부 API / LLM 호출이라고 가정
    return f"{topic} 요약"


@entrypoint()
def sequential(topics: list[str]) -> list[str]:
    return [slow_summarize(t).result() for t in topics]  # 하나 끝나야 다음 출발


@entrypoint()
def parallel(topics: list[str]) -> list[str]:
    futures = [slow_summarize(t) for t in topics]  # 모두 출발
    return [f.result() for f in futures]  # 모두 도착을 기다림


topics = ["상태", "노드", "엣지", "리듀서"]
print("=" * 60)
print("② 순차 vs 병렬 (task 하나당 0.3초)")
for name, wf in (("순차", sequential), ("병렬", parallel)):
    started = time.perf_counter()
    result = wf.invoke(topics)
    print(f"  {name}: {time.perf_counter() - started:.2f}초 → {result}")
