"""키 주입 프록시: 샌드박스 코드는 진짜 키를 볼 수 없고, 허용된 추론 API 만 진짜 키로 전달된다."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from helpers import collect

from app import keyproxy

REAL_KEY = "sk-REAL-SECRET-for-test"


@pytest.fixture
def fake_openai(monkeypatch):
    """요청을 기록하고 고정된 chat.completion 을 돌려주는 가짜 OpenAI 서버."""
    seen: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            seen.append((self.path, self.headers.get("authorization")))
            out = {
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model", "m"),
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "프록시 응답"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            }
            data = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(keyproxy, "UPSTREAM", f"http://127.0.0.1:{srv.server_address[1]}")
    yield seen
    srv.shutdown()


CODE = f"""
import os, httpx
print("KEY", os.environ.get("OPENAI_API_KEY"))
print("LEAK", "{REAL_KEY}" in str(dict(os.environ)))
from langchain_openai import ChatOpenAI
r = ChatOpenAI(model="gpt-5-mini").invoke("hi")
print("LLM", r.content, r.usage_metadata["total_tokens"])
base = os.environ["OPENAI_BASE_URL"]
print("FILES", httpx.post(base + "/files", json={{}}).status_code)
print("BADTOKEN", httpx.post(base.rsplit("/", 2)[0] + "/nope/v1/chat/completions", json={{}}).status_code)
"""


async def test_sandbox_never_sees_real_key(fake_openai):
    r = await collect({"main.py": CODE}, api_key=REAL_KEY, timeout=60)
    out = dict(line.split(" ", 1) for line in r["stdout"].strip().splitlines())
    assert r["exit"]["code"] == 0, r["stderr"]
    assert r["start"]["mock"] is False
    assert out["KEY"] == keyproxy.DUMMY_KEY
    assert out["LEAK"] == "False"
    assert out["LLM"] == "프록시 응답 8"
    # 업스트림에는 진짜 키가 붙어서 갔다
    assert fake_openai == [("/v1/chat/completions", f"Bearer {REAL_KEY}")]
    # 비허용 엔드포인트·잘못된 토큰은 업스트림까지 가지 않는다
    assert out["FILES"] == "403"
    assert out["BADTOKEN"] == "401"


async def test_token_is_revoked_after_run(fake_openai):
    await collect({"main.py": "print(1)"}, api_key=REAL_KEY)
    assert keyproxy._keys == {}


@pytest.mark.parametrize(
    ("path", "ok"),
    [
        ("v1/chat/completions", True),
        ("v1/responses", True),
        ("v1/embeddings", True),
        ("v1/models", True),
        ("v1/files", False),
        ("v1/fine_tuning/jobs", False),
        ("v1/organization/users", False),
        ("v1/chat/completionsX", False),
    ],
)
def test_allowlist(path, ok):
    assert keyproxy._allowed(path) is ok
