"""FastAPI 에이전트 서버를 프로세스 안에서 호출해 본다 (fastapi.testclient).

TestClient 는 실제 HTTP 소켓 없이 ASGI 앱을 직접 호출한다.
`with TestClient(app)` 블록에 들어가면 lifespan(startup/shutdown)도 실행된다.
→ 서버를 띄우지 않고도 '배포될 앱과 똑같은 코드'를 검증할 수 있다. (API 통합 테스트의 표준)
"""

from __future__ import annotations

import json

from agent_service import app
from fastapi.testclient import TestClient

ALICE = {"X-API-Key": "key-alice"}
BOB = {"X-API-Key": "key-bob"}


def show(title: str, resp) -> dict:
    body = resp.json()
    print(f"\n▶ {title}\n  HTTP {resp.status_code}  {json.dumps(body, ensure_ascii=False)[:150]}")
    return body


with TestClient(app) as client:  # lifespan 실행 → 에이전트/체크포인터 생성
    print("=" * 70 + "\n1) 헬스 체크와 OpenAPI 문서\n" + "=" * 70)
    show("GET /healthz", client.get("/healthz"))
    paths = list(client.get("/openapi.json").json()["paths"])
    print("  OpenAPI 경로:", paths)

    print("\n" + "=" * 70 + "\n2) 인증과 입력 검증\n" + "=" * 70)
    r = client.post("/threads/t1/runs", json={"message": "안녕"})
    show("API 키 없이 호출", r)
    assert r.status_code == 401
    r = client.post("/threads/t1/runs", json={"message": ""}, headers=ALICE)
    show("빈 메시지 (Pydantic 검증 실패)", r)
    assert r.status_code == 422

    print("\n" + "=" * 70 + "\n3) 실행 → 같은 thread 로 이어서 대화 (체크포인터 덕분)\n" + "=" * 70)
    b1 = show("alice: order 상태", client.post("/threads/t1/runs", json={"message": "order A-1 상태?"}, headers=ALICE))
    assert b1["tool_calls"] == ["get_order_status"] and b1["answer"]
    show("alice: 후속 질문", client.post("/threads/t1/runs", json={"message": "고마워요"}, headers=ALICE))
    state = show("alice: 스레드 상태 조회", client.get("/threads/t1/state", headers=ALICE))
    print("  저장된 메시지 수:", len(state["messages"]))

    print("\n" + "=" * 70 + "\n4) 테넌트 격리 — bob 은 alice 의 t1 스레드를 볼 수 없다\n" + "=" * 70)
    r = client.get("/threads/t1/state", headers=BOB)
    show("bob: t1 상태 조회", r)
    assert r.status_code == 404

    print("\n" + "=" * 70 + "\n5) HITL — 환불 요청은 승인 대기 상태로 응답\n" + "=" * 70)
    b = show("alice: refund 요청", client.post("/threads/t2/runs", json={"message": "A-9 refund 해줘"}, headers=ALICE))
    assert b["interrupt"] is not None and b["answer"] is None
    st = show("대기 중인 interrupt 확인", client.get("/threads/t2/state", headers=ALICE))
    assert st["pending_interrupts"]
print("\n(블록을 벗어나면 lifespan shutdown 이 실행된다)")
