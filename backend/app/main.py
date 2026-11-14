"""AgentLab API 서버."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from importlib.metadata import version

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .auth import AUTH_REQUIRED, daily_limit, require_user
from .refine import cache_get, refine, structure_key
from .runner import RunError, stream_run
from .validate import validate

app = FastAPI(title="AgentLab API", version="1.0.0")

origins = [o.strip() for o in os.getenv("AGENTLAB_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # 예: r"https://agentlab(-[a-z0-9-]+)?\.vercel\.app" — Vercel 프리뷰 배포 주소까지 허용
    allow_origin_regex=os.getenv("AGENTLAB_CORS_ORIGIN_REGEX") or None,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------- rate limit
LIMITS = {
    "run": int(os.getenv("AGENTLAB_RATE_RUN", 30)),
    "validate": int(os.getenv("AGENTLAB_RATE_VALIDATE", 15)),
    "refine": int(os.getenv("AGENTLAB_RATE_REFINE", 6)),
    "lookup": int(os.getenv("AGENTLAB_RATE_LOOKUP", 120)),
}
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _client_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "?")


def rate_limit(req: Request, bucket: str) -> None:
    now = time.time()
    q = _hits[(_client_ip(req), bucket)]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= LIMITS[bucket]:
        raise HTTPException(429, f"요청이 너무 많습니다. 1분에 {LIMITS[bucket]}회까지 가능합니다.")
    q.append(now)


def _key(req: Request) -> str | None:
    k = (req.headers.get("x-openai-key") or "").strip()
    return k or None


# ---------------------------------------------------------------- schemas
class RunRequest(BaseModel):
    files: dict[str, str] = Field(..., description="경로 → 소스코드")
    entry: str = "main.py"
    timeout: int = 30
    stdin: str | None = None
    model: str | None = None


class ValidateRequest(BaseModel):
    files: dict[str, str]
    entry: str = "main.py"


class LookupRequest(BaseModel):
    graph: dict


class RefineRequest(BaseModel):
    graph: dict
    files: dict[str, str]
    model: str | None = None


# ---------------------------------------------------------------- routes
@app.get("/api/health")
async def health():
    pkgs = ["langgraph", "langchain", "langchain-core", "langchain-openai", "pydantic"]
    return {"ok": True, "versions": {p: version(p) for p in pkgs}, "python": os.sys.version.split()[0], "auth_required": AUTH_REQUIRED}


@app.post("/api/run")
async def run(req: Request, body: RunRequest):
    """NDJSON 스트리밍으로 실행 이벤트를 전달한다."""
    rate_limit(req, "run")
    daily_limit(await require_user(req), "run")
    api_key = _key(req)

    async def gen():
        try:
            async for ev in stream_run(
                body.files, body.entry, api_key=api_key, model=body.model, timeout=body.timeout, stdin=body.stdin
            ):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except RunError as e:
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})


@app.post("/api/validate")
async def validate_route(req: Request, body: ValidateRequest):
    rate_limit(req, "validate")
    daily_limit(await require_user(req), "validate")
    try:
        return await validate(body.files, body.entry)
    except RunError as e:
        raise HTTPException(400, str(e))


@app.post("/api/refine")
async def refine_route(req: Request, body: RefineRequest):
    rate_limit(req, "refine")
    daily_limit(await require_user(req), "refine")
    try:
        return await refine(body.graph, body.files, _key(req), body.model)
    except RunError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # OpenAI 오류 등
        raise HTTPException(502, f"LLM 호출 실패: {type(e).__name__}: {e}")


@app.post("/api/refine/cached")
async def refine_cached(req: Request, body: LookupRequest):
    """LLM 호출 없이 캐시만 조회한다 (그래프가 바뀔 때마다 호출됨)."""
    rate_limit(req, "lookup")
    key = structure_key(body.graph)
    hit = await asyncio.to_thread(cache_get, key)
    return {"key": key, "hit": hit}


@app.get("/api/models")
async def models(req: Request):
    """사용자 키로 사용 가능한 OpenAI 채팅 모델 목록."""
    api_key = _key(req)
    if not api_key:
        return {"models": []}
    from openai import AsyncOpenAI

    try:
        res = await AsyncOpenAI(api_key=api_key).models.list()
    except Exception as e:
        raise HTTPException(400, f"키 확인 실패: {e}")
    ids = sorted(
        (m.id for m in res.data if m.id.startswith(("gpt-", "o")) and not any(x in m.id for x in ("audio", "realtime", "tts", "transcribe", "image", "search"))),
        reverse=True,
    )
    return {"models": ids}
