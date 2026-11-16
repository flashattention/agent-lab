"""로그인 확인과 사용자별 하루 한도, IP 기준 분당 한도."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth, main


def make_request(headers: dict[str, str] | None = None, client=("1.2.3.4", 1234)) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw, "client": client})


def test_daily_limit_blocks_after_quota(monkeypatch):
    monkeypatch.setitem(auth.DAILY_LIMITS, "run", 3)
    monkeypatch.setattr(auth, "_usage", {})
    for _ in range(3):
        auth.daily_limit("user-1", "run")
    with pytest.raises(HTTPException) as e:
        auth.daily_limit("user-1", "run")
    assert e.value.status_code == 429
    auth.daily_limit("user-2", "run")  # 다른 사용자는 영향 없음


def test_daily_limit_skipped_without_auth():
    for _ in range(1000):
        auth.daily_limit(None, "refine")


async def test_login_required_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_REQUIRED", True)
    with pytest.raises(HTTPException) as e:
        await auth.require_user(make_request())
    assert e.value.status_code == 401


async def test_valid_token_is_cached(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_REQUIRED", True)
    monkeypatch.setattr(auth, "_tokens", {})
    calls = []

    async def fake_fetch(token):
        calls.append(token)
        return "user-9"

    monkeypatch.setattr(auth, "_fetch_user_id", fake_fetch)
    req = make_request({"authorization": "Bearer abc"})
    assert await auth.require_user(req) == "user-9"
    assert await auth.require_user(req) == "user-9"
    assert calls == ["abc"]  # 두 번째는 캐시


async def test_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_REQUIRED", True)
    monkeypatch.setattr(auth, "_tokens", {})

    async def fake_fetch(token):
        return None

    monkeypatch.setattr(auth, "_fetch_user_id", fake_fetch)
    with pytest.raises(HTTPException) as e:
        await auth.require_user(make_request({"authorization": "Bearer bad"}))
    assert e.value.status_code == 401


def test_client_ip_ignores_spoofed_forwarded_for():
    # 클라이언트가 넣은 값(맨 앞)이 아니라 앞단 프록시가 덧붙인 값(맨 끝)을 쓴다
    req = make_request({"x-forwarded-for": "6.6.6.6, 9.9.9.9"})
    assert main._client_ip(req) == "9.9.9.9"
    assert main._client_ip(make_request()) == "1.2.3.4"


def test_rate_limit_per_ip(monkeypatch):
    monkeypatch.setitem(main.LIMITS, "run", 2)
    monkeypatch.setattr(main, "_hits", main.defaultdict(main.deque))
    req = make_request({"x-forwarded-for": "5.5.5.5"})
    main.rate_limit(req, "run")
    main.rate_limit(req, "run")
    with pytest.raises(HTTPException) as e:
        main.rate_limit(req, "run")
    assert e.value.status_code == 429
    main.rate_limit(make_request({"x-forwarded-for": "7.7.7.7"}), "run")
