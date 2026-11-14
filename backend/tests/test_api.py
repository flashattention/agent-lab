"""HTTP API: health 와 NDJSON 실행 스트림."""

import json

from fastapi.testclient import TestClient
from helpers import REACT_AGENT

from app.main import app

client = TestClient(app)


def run_stream(files: dict[str, str]) -> list[dict]:
    with client.stream("POST", "/api/run", json={"files": files, "entry": "main.py", "timeout": 60}) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in res.iter_lines() if line]


def test_health():
    r = client.get("/api/health").json()
    assert r["ok"] is True
    assert "langgraph" in r["versions"]
    assert r["auth_required"] is False


def test_run_stream_order():
    events = run_stream({"main.py": "print('hi')"})
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "exit" and events[-1]["code"] == 0
    assert any(e["type"] == "stdout" and "hi" in e["data"] for e in events)


def test_run_stream_includes_trace_events():
    events = run_stream({"main.py": REACT_AGENT})
    kinds = {e["event"]["kind"] for e in events if e["type"] == "trace" and e["event"]["ev"] == "start"}
    assert {"graph", "node", "llm", "tool"} <= kinds


def test_run_rejects_bad_paths_in_stream():
    events = run_stream({"main.py": "print(1)", "../x.py": ""})
    assert events[-1]["type"] == "error"
