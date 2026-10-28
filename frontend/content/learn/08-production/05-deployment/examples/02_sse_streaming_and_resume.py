"""SSE 스트리밍 엔드포인트와 HITL 재개(resume) 흐름을 클라이언트 입장에서 따라가 본다.

브라우저라면 fetch() + ReadableStream (POST 이므로 EventSource 대신) 으로 읽는다.
여기서는 TestClient.stream() 으로 응답 바이트를 줄 단위로 읽어 SSE 이벤트로 파싱한다.

  event: token      data: {"text": "..."}
  event: tool       data: {"name": "...", "result": "..."}
  event: interrupt  data: {"action_requests": [...]}
  event: end        data: {"thread_id": "..."}
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from agent_service import app
from fastapi.testclient import TestClient

HEADERS = {"X-API-Key": "key-alice"}


def iter_sse(lines: Iterator[str]) -> Iterator[dict]:
    """text/event-stream 을 파싱한다. 빈 줄이 이벤트의 끝."""
    event: dict = {}
    for line in lines:
        if not line:
            if event:
                yield event
                event = {}
            continue
        field, _, value = line.partition(":")
        value = value.lstrip()
        if field == "data":
            event["data"] = json.loads(value)
        elif field in ("event", "id"):
            event[field] = value
    if event:
        yield event


def consume(client: TestClient, url: str, body: dict) -> list[dict]:
    events = []
    with client.stream("POST", url, json=body, headers=HEADERS) as resp:
        print(f"  HTTP {resp.status_code}  content-type={resp.headers['content-type']}")
        for ev in iter_sse(resp.iter_lines()):
            events.append(ev)
            if ev["event"] == "token":
                print(ev["data"]["text"], end="", flush=True)
            else:
                print(f"\n  ⮕ [{ev['event']}] id={ev.get('id')} {json.dumps(ev['data'], ensure_ascii=False)[:110]}")
    return events


with TestClient(app) as client:
    print("=" * 70 + "\n1) 일반 질문 스트리밍\n" + "=" * 70)
    evs = consume(client, "/threads/s1/runs/stream", {"message": "order A-3 상태 알려줘"})
    assert evs[-1]["event"] == "end" and any(e["event"] == "token" for e in evs)

    print("\n" + "=" * 70 + "\n2) 환불 요청 → interrupt 이벤트에서 스트림 종료\n" + "=" * 70)
    evs = consume(client, "/threads/s2/runs/stream", {"message": "A-7 refund 부탁해요"})
    pending = [e for e in evs if e["event"] == "interrupt"]
    assert pending, "승인 요청 이벤트가 와야 한다"
    print("\n  → 프론트엔드: 승인 모달 표시:", pending[0]["data"]["action_requests"][0]["name"])

    print("\n" + "=" * 70 + "\n3) 상담원 승인 → /resume 로 재개 스트리밍\n" + "=" * 70)
    evs = consume(client, "/threads/s2/resume", {"decision": "approve"})
    assert any(e["event"] == "tool" and e["data"]["name"] == "issue_refund" for e in evs)

    print("\n" + "=" * 70 + "\n4) 잘못된 결정 값은 검증 단계에서 거절\n" + "=" * 70)
    r = client.post("/threads/s2/resume", json={"decision": "maybe"}, headers=HEADERS)
    print("  HTTP", r.status_code, r.json()["detail"][0]["msg"])
    assert r.status_code == 422
