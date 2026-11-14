"""로그인 확인과 사용자별 하루 사용량 제한.

SUPABASE_URL 과 SUPABASE_ANON_KEY 가 설정되면 코드 실행·검증·고도화 요청에 로그인이 필요하다.
둘 중 하나라도 없으면(로컬 개발) 로그인 없이 동작한다.

토큰은 Supabase Auth 에 물어 확인한다. 서명 키 방식(HS256 · 비대칭 키)이 프로젝트마다 달라도 같은 코드로 동작하고,
로그아웃하거나 정지된 계정의 토큰도 걸러 낸다. 확인 결과는 잠시 기억해 요청마다 왕복하지 않는다.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, Request

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
AUTH_REQUIRED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

DAILY_LIMITS = {
    "run": int(os.getenv("AGENTLAB_DAILY_RUN", 200)),
    "validate": int(os.getenv("AGENTLAB_DAILY_VALIDATE", 100)),
    "refine": int(os.getenv("AGENTLAB_DAILY_REFINE", 20)),
}
LABELS = {"run": "코드 실행", "validate": "검증", "refine": "고도화"}

_TOKEN_TTL = 300  # 초
_tokens: dict[str, tuple[str, float]] = {}  # 토큰 → (사용자 id, 만료 시각)
_usage: dict[tuple[str, str, str], int] = {}  # (사용자 id, 종류, 날짜) → 횟수


async def _fetch_user_id(token: str) -> str | None:
    """Supabase 에 토큰을 보내 사용자 id 를 받는다. 유효하지 않으면 None."""
    async with httpx.AsyncClient(timeout=8) as client:
        res = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "authorization": f"Bearer {token}"},
        )
    if res.status_code != 200:
        return None
    return res.json().get("id") or None


async def require_user(req: Request) -> str | None:
    """로그인이 필요한 요청에서 사용자 id 를 돌려준다. 인증을 쓰지 않는 환경에서는 None."""
    if not AUTH_REQUIRED:
        return None
    header = req.headers.get("authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(401, "로그인 후 사용할 수 있습니다.")

    now = time.time()
    hit = _tokens.get(token)
    if hit and hit[1] > now:
        return hit[0]
    try:
        user_id = await _fetch_user_id(token)
    except httpx.HTTPError:
        raise HTTPException(503, "로그인 확인 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.")
    if not user_id:
        _tokens.pop(token, None)
        raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인하세요.")
    if len(_tokens) > 5000:  # 오래된 항목 정리
        for k in [k for k, (_, exp) in _tokens.items() if exp <= now]:
            del _tokens[k]
    _tokens[token] = (user_id, now + _TOKEN_TTL)
    return user_id


def daily_limit(user_id: str | None, bucket: str) -> None:
    """사용자별 하루(UTC) 횟수 제한. 서버 인스턴스의 메모리에만 기록하므로 재시작하면 초기화된다."""
    if user_id is None:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = (user_id, bucket, today)
    used = _usage.get(key, 0)
    if used >= DAILY_LIMITS[bucket]:
        raise HTTPException(429, f"오늘 {LABELS[bucket]} 한도({DAILY_LIMITS[bucket]}회)를 모두 썼습니다. 내일 다시 이용할 수 있습니다.")
    if len(_usage) > 20000:  # 지난 날짜 정리
        for k in [k for k in _usage if k[2] != today]:
            del _usage[k]
    _usage[key] = used + 1
