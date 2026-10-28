"""[실습] 미니 에이전트 API 서버 만들기

과제 (모두 이 파일 안에서 완성하고 TestClient 로 채점한다)
1. lifespan: 시작 시 InMemorySaver 와 에이전트를 만들어 app.state.agent 에 저장하라.
2. POST /chat/{thread_id}
   - 헤더 X-User 가 없으면 401 (require_user 의존성 사용)
   - thread_id 는 f"{user}:{thread_id}" 로 사용자별로 격리한다
   - 응답: {"answer": 마지막 AI 메시지 내용, "turns": 이 스레드의 사람 메시지 수}
3. POST /chat/{thread_id}/stream  (response_class=EventSourceResponse)
   - model 노드의 토큰마다 ServerSentEvent(event="token", data={"text": ...})
   - 마지막에 ServerSentEvent(event="end", data={})
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def faq(topic: str) -> str:
    """배송/환불 FAQ 검색"""
    return "배송은 평균 2일 소요됩니다."


class ChatIn(BaseModel):
    message: str


def require_user(x_user: str = Header(default="")) -> str:
    if not x_user:
        raise HTTPException(status_code=401, detail="X-User header required")
    return x_user


def cfg(user: str, thread_id: str) -> dict:
    return {"configurable": {"thread_id": f"{user}:{thread_id}"}}


# ------------------------------------------------------------------ TODO 1
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # TODO 1: InMemorySaver 체크포인터로 create_agent(MODEL, tools=[faq], ...) 를 만들어 app.state.agent 에 저장
    yield


app = FastAPI(lifespan=lifespan)


# ------------------------------------------------------------------ TODO 2
@app.post("/chat/{thread_id}")
async def chat(thread_id: str, body: ChatIn, user: str = Depends(require_user)) -> dict:
    # TODO 2: ainvoke 로 실행하고 {"answer": ..., "turns": 사람 메시지 수} 를 반환하세요 (cfg(user, thread_id) 사용)
    raise NotImplementedError("TODO 2: chat")


# ------------------------------------------------------------------ TODO 3
@app.post("/chat/{thread_id}/stream", response_class=EventSourceResponse)
async def chat_stream(thread_id: str, body: ChatIn, user: str = Depends(require_user)):
    # TODO 3: astream(..., stream_mode="messages") 로 model 노드 토큰을 token 이벤트로 yield 하고, 마지막에 end 이벤트
    raise NotImplementedError("TODO 3: chat_stream")
    yield  # 이 함수를 async generator 로 만들기 위한 줄 (지우지 마세요)


# ================================================================== 자가 채점
with TestClient(app) as client:
    assert client.post("/chat/a", json={"message": "hi"}).status_code == 401
    print("1) 인증 없는 요청 401 통과")

    r1 = client.post("/chat/a", json={"message": "배송 faq 알려줘"}, headers={"X-User": "kim"}).json()
    r2 = client.post("/chat/a", json={"message": "고마워"}, headers={"X-User": "kim"}).json()
    r3 = client.post("/chat/a", json={"message": "안녕"}, headers={"X-User": "lee"}).json()
    assert r1["answer"] and r2["turns"] == 2, r2
    assert r3["turns"] == 1, "다른 사용자의 같은 thread_id 는 별개의 대화여야 합니다"
    print("2) 대화 지속 + 사용자 격리 통과:", r2["turns"], r3["turns"])

    events = []
    with client.stream("POST", "/chat/b/stream", json={"message": "환불 faq"}, headers={"X-User": "kim"}) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        current = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                current = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((current, json.loads(line.split(":", 1)[1])))
    kinds = [e for e, _ in events]
    assert kinds.count("token") > 1 and kinds[-1] == "end", kinds
    print("3) SSE 스트리밍 통과: token", kinds.count("token"), "개 + end")
print("✅ 모든 테스트 통과!")
