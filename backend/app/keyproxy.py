"""샌드박스용 OpenAI 키 주입 프록시.

사용자 코드(샌드박스)에는 진짜 API 키를 넘기지 않는다. 대신
  OPENAI_BASE_URL = http://127.0.0.1:<port>/<실행별 토큰>/v1
  OPENAI_API_KEY  = 가짜 값
을 넘기고, 이 프록시가 요청에 진짜 키를 붙여 api.openai.com 으로만 전달한다.

- 토큰은 실행마다 새로 만들고 실행이 끝나면 지운다. 토큰 → 키 매핑은 이 프로세스 메모리에만 있다.
- 127.0.0.1 에만 바인딩하므로 외부에서는 접근할 수 없다.
- 허용한 추론용 엔드포인트만 전달한다 (파일·파인튜닝·조직 관리 등은 거부).
- uvicorn worker 마다 프록시가 하나씩 뜬다. 실행을 처리한 worker 의 프록시 주소를 그 실행에 넘기므로
  worker 가 여러 개여도 토큰이 어긋나지 않는다.

샌드박스 코드가 할 수 있는 일은 "실행 중에 그 키로 허용된 OpenAI API 를 호출하는 것"뿐이며,
키 문자열 자체는 알 수 없다. 사용량 상한은 사용자가 OpenAI 프로젝트 키에 거는 한도로 제한한다.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

UPSTREAM = os.getenv("AGENTLAB_OPENAI_UPSTREAM", "https://api.openai.com")
DUMMY_KEY = "sk-agentlab-proxy-key-hidden"
ALLOWED = (
    "v1/chat/completions",
    "v1/responses",
    "v1/embeddings",
    "v1/completions",
    "v1/moderations",
    "v1/models",
)
# 요청·응답에서 그대로 넘기지 않는 헤더
DROP_REQ = {"host", "authorization", "content-length", "connection", "accept-encoding", "openai-organization", "openai-project"}
DROP_RESP = {"content-length", "transfer-encoding", "connection", "content-encoding"}

_keys: dict[str, str] = {}
_port: int | None = None
_lock = asyncio.Lock()
_client: httpx.AsyncClient | None = None


def _allowed(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in ALLOWED)


async def _forward(request: Request):
    token = request.path_params["token"]
    path = request.path_params["path"]
    key = _keys.get(token)
    if not key:
        return JSONResponse({"error": {"message": "AgentLab: 만료되었거나 잘못된 실행 토큰입니다.", "type": "invalid_request_error"}}, 401)
    if not _allowed(path):
        return JSONResponse({"error": {"message": f"AgentLab: 샌드박스에서 허용하지 않는 OpenAI 엔드포인트입니다 (/{path}).", "type": "invalid_request_error"}}, 403)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in DROP_REQ}
    headers["authorization"] = f"Bearer {key}"
    assert _client is not None
    upstream = _client.build_request(
        request.method,
        f"{UPSTREAM}/{path}",
        params=request.query_params,
        headers=headers,
        content=await request.body(),
    )
    try:
        resp = await _client.send(upstream, stream=True)
    except httpx.HTTPError as e:
        return JSONResponse({"error": {"message": f"AgentLab: OpenAI 연결 실패 ({e.__class__.__name__})", "type": "api_connection_error"}}, 502)
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in DROP_RESP}
    return StreamingResponse(resp.aiter_bytes(), status_code=resp.status_code, headers=out_headers, background=BackgroundTask(resp.aclose))


_app = Starlette(routes=[Route("/{token}/{path:path}", _forward, methods=["GET", "POST", "DELETE"])])


async def _ensure_started() -> int:
    global _port, _client
    async with _lock:
        if _port is not None:
            return _port
        _client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10))
        config = uvicorn.Config(_app, host="127.0.0.1", port=0, log_level="warning", access_log=False, lifespan="off")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        asyncio.get_running_loop().create_task(server.serve())
        for _ in range(200):
            if server.started and server.servers:
                break
            await asyncio.sleep(0.01)
        else:
            raise RuntimeError("키 프록시를 시작하지 못했습니다.")
        _port = server.servers[0].sockets[0].getsockname()[1]
        return _port


@asynccontextmanager
async def proxied_key(api_key: str):
    """실행 하나 동안 쓸 (base_url, 가짜 키) 를 돌려준다. 블록을 벗어나면 토큰은 바로 무효가 된다."""
    port = await _ensure_started()
    token = secrets.token_urlsafe(24)
    _keys[token] = api_key
    try:
        yield f"http://127.0.0.1:{port}/{token}/v1", DUMMY_KEY
    finally:
        _keys.pop(token, None)
