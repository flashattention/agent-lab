"""[실습] 미니 에이전트 API 서버 만들기 — 정답

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
    app.state.agent = create_agent(MODEL, tools=[faq], checkpointer=InMemorySaver())
    yield


app = FastAPI(lifespan=lifespan)


# ------------------------------------------------------------------ TODO 2
@app.post("/chat/{thread_id}")
async def chat(thread_id: str, body: ChatIn, user: str = Depends(require_user)) -> dict:
    result = await app.state.agent.ainvoke(
        {"messages": [{"role": "user", "content": body.message}]}, cfg(user, thread_id)
    )
    msgs = result["messages"]
    return {"answer": msgs[-1].content, "turns": sum(m.type == "human" for m in msgs)}


# ------------------------------------------------------------------ TODO 3
@app.post("/chat/{thread_id}/stream", response_class=EventSourceResponse)
async def chat_stream(thread_id: str, body: ChatIn, user: str = Depends(require_user)):
    async for chunk, meta in app.state.agent.astream(
        {"messages": [{"role": "user", "content": body.message}]}, cfg(user, thread_id),
        stream_mode="messages",
    ):
        if meta["langgraph_node"] == "model" and chunk.content:
            yield ServerSentEvent(event="token", data={"text": chunk.content})
    yield ServerSentEvent(event="end", data={})


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
