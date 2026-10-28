"""장기 메모리 (5.4강): 사용자 프로필·선호·최근 문의 이력을 Store 에 저장한다.

네임스페이스 설계
  ("users", user_id) / "profile"  → {"name", "tier", "prefers_concise"}       (semantic)
  ("users", user_id) / "history"  → {"recent": [{"route", "text"}, ...]}       (episodic)

선호 추출은 여기서는 규칙 기반이다. 현업에서는 대화가 끝난 뒤 백그라운드 작업으로
LLM 이 '기억할 만한 사실'을 구조화 출력으로 뽑아 저장한다.
"""

from __future__ import annotations

from langgraph.store.base import BaseStore

from .data import CUSTOMERS

MAX_HISTORY = 5


def ns(user_id: str) -> tuple[str, str]:
    return ("users", user_id)


def load_profile(store: BaseStore, user_id: str) -> dict:
    item = store.get(ns(user_id), "profile")
    if item is not None:
        return dict(item.value)
    base = CUSTOMERS.get(user_id, {"name": "고객", "tier": "STANDARD"})
    profile = {"name": base["name"], "tier": base["tier"], "prefers_concise": False}
    store.put(ns(user_id), "profile", profile)  # 첫 방문 시 CRM 에서 가져와 캐시
    return profile


def load_history(store: BaseStore, user_id: str) -> list[dict]:
    item = store.get(ns(user_id), "history")
    return list(item.value["recent"]) if item else []


def record_interaction(store: BaseStore, user_id: str, route: str, text: str) -> dict:
    """이번 턴을 이력에 남기고, 발화에서 선호를 추출해 프로필을 갱신한다."""
    history = (load_history(store, user_id) + [{"route": route, "text": text[:80]}])[-MAX_HISTORY:]
    store.put(ns(user_id), "history", {"recent": history})

    profile = load_profile(store, user_id)
    if any(k in text for k in ("짧게", "간단히", "요점만")):
        profile["prefers_concise"] = True
    elif "자세히" in text:
        profile["prefers_concise"] = False
    store.put(ns(user_id), "profile", profile)
    return profile
