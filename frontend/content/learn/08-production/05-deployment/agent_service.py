"""에이전트를 HTTP API 로 서빙하는 FastAPI 애플리케이션 (프로덕션 구조의 축소판).

엔드포인트
  GET  /healthz                         헬스 체크 (로드밸런서/쿠버네티스 probe)
  POST /threads/{thread_id}/runs        동기 실행: 최종 답변 + interrupt 정보 반환
  POST /threads/{thread_id}/runs/stream SSE 스트리밍 실행 (token / tool / interrupt / end 이벤트)
  POST /threads/{thread_id}/resume      HITL 승인 결과로 재개 (SSE)
  GET  /threads/{thread_id}/state       체크포인트에 저장된 현재 상태 조회

프로덕션 패턴
  - lifespan 에서 무거운 객체(에이전트, 체크포인터)를 한 번만 만든다
  - 인증 헤더 → 사용자 컨텍스트 (모델이 아니라 서버가 권한을 정한다)
  - 동시 실행 상한(Semaphore) + 요청 타임아웃 → 과부하 시 503/504 로 빠르게 실패
  - 같은 thread 동시 실행 방지(Lock) → 409 (double-texting 문제)

이 파일은 서버를 '띄우지' 않는다. 예제에서는 TestClient / ASGITransport 로 프로세스 안에서 호출한다.
실제 실행: uvicorn agent_service:app --host 0.0.0.0 --port 8000 --workers 2
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ModelCallLimitMiddleware
from langchain.messages import AIMessage
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
API_KEYS = {"key-alice": "alice", "key-bob": "bob"}  # 실무: JWT 검증 / API 게이트웨이


# ============================================================ 에이전트
@dataclass
class UserCtx:
    user_id: str


@tool
async def get_order_status(order_id: str, runtime: ToolRuntime[UserCtx]) -> str:
    """주문 order 배송 상태를 조회한다."""
    await asyncio.sleep(0.2)  # 외부 API I/O 대기 흉내 — async 라서 다른 요청을 막지 않는다
    return f"[{runtime.context.user_id}] {order_id}: 배송 중"


@tool
async def issue_refund(order_id: str) -> str:
    """주문을 환불 refund 한다. 사람 승인 필요."""
    return f"{order_id} 환불 완료"


def build_agent(checkpointer: Any):
    """에이전트 팩토리 — 테스트에서 체크포인터/모델을 바꿔 끼울 수 있게 분리."""
    return create_agent(
        MODEL,
        tools=[get_order_status, issue_refund],
        system_prompt="쇼핑몰 상담원",
        context_schema=UserCtx,
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"issue_refund": True}),
            ModelCallLimitMiddleware(run_limit=6),
        ],
        checkpointer=checkpointer,
    )


# ============================================================ 앱 설정
MAX_CONCURRENT_RUNS = int(os.getenv("MAX_CONCURRENT_RUNS", "8"))
RUN_TIMEOUT_S = float(os.getenv("RUN_TIMEOUT_S", "30"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 운영: async with AsyncPostgresSaver.from_conn_string(DB_URI) as saver: await saver.setup() ...
    app.state.checkpointer = InMemorySaver()
    app.state.agent = build_agent(app.state.checkpointer)
    app.state.run_slots = asyncio.Semaphore(MAX_CONCURRENT_RUNS)
    app.state.thread_locks = defaultdict(asyncio.Lock)
    yield
    # 종료 시 정리: DB 커넥션 풀 닫기, 진행 중인 작업 마무리 등


app = FastAPI(title="Support Agent API", version="1.0.0", lifespan=lifespan)


# ============================================================ 스키마 & 의존성
class RunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)  # 입력 크기 제한도 보안/비용 장치


class ResumeRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    message: str | None = None


class RunResponse(BaseModel):
    thread_id: str
    answer: str | None
    interrupt: dict | None = None
    tool_calls: list[str] = []


def current_user(x_api_key: str = Header(default="")) -> UserCtx:
    user = API_KEYS.get(x_api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    return UserCtx(user_id=user)


def run_config(user: UserCtx, thread_id: str) -> dict:
    # thread_id 에 사용자 ID 를 섞어 다른 사용자의 대화에 접근하지 못하게 한다
    return {
        "configurable": {"thread_id": f"{user.user_id}:{thread_id}"},
        "metadata": {"user_id": user.user_id},
        "tags": ["api"],
    }


@asynccontextmanager
async def run_guard(thread_id: str):
    """동시 실행 상한 + 같은 스레드 중복 실행 방지 + 타임아웃."""
    lock: asyncio.Lock = app.state.thread_locks[thread_id]
    if lock.locked():
        raise HTTPException(status_code=409, detail="이 스레드에서 이미 실행 중입니다")
    slots: asyncio.Semaphore = app.state.run_slots
    if slots.locked():
        raise HTTPException(status_code=503, detail="서버가 바쁩니다. 잠시 후 다시 시도하세요",
                            headers={"Retry-After": "2"})
    async with lock, slots:
        yield


def summarize(result: Any, thread_id: str) -> RunResponse:
    msgs = result.value["messages"]
    last = msgs[-1]
    intr = result.interrupts[0].value if result.interrupts else None
    # 이번 턴(마지막 사람 메시지 이후)에 일어난 도구 호출만 모은다
    last_human = max(i for i, m in enumerate(msgs) if m.type == "human")
    calls = [tc["name"] for m in msgs[last_human:] if isinstance(m, AIMessage) for tc in m.tool_calls]
    answer = last.content if isinstance(last, AIMessage) and not last.tool_calls else None
    return RunResponse(thread_id=thread_id, answer=answer, interrupt=intr, tool_calls=calls)


# ============================================================ 엔드포인트
@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/threads/{thread_id}/runs", response_model=RunResponse)
async def run(thread_id: str, req: RunRequest, user: UserCtx = Depends(current_user)) -> RunResponse:
    async with run_guard(f"{user.user_id}:{thread_id}"):
        try:
            async with asyncio.timeout(RUN_TIMEOUT_S):
                result = await app.state.agent.ainvoke(
                    {"messages": [{"role": "user", "content": req.message}]},
                    run_config(user, thread_id), context=user, version="v2",
                )
        except TimeoutError:
            raise HTTPException(status_code=504, detail="에이전트 실행 시간 초과") from None
    return summarize(result, thread_id)


async def sse_events(payload: Any, user: UserCtx, thread_id: str) -> AsyncIterator[ServerSentEvent]:
    """LangGraph v2 스트림 → SSE 이벤트 (8.1강의 UI 이벤트 프로토콜)."""
    seq = 0
    async with run_guard(f"{user.user_id}:{thread_id}"):
        async for part in app.state.agent.astream(
            payload, run_config(user, thread_id), context=user,
            stream_mode=["messages", "updates"], version="v2",
        ):
            seq += 1
            if part["type"] == "messages":
                chunk, meta = part["data"]
                if meta["langgraph_node"] == "model" and chunk.content:
                    yield ServerSentEvent(event="token", data={"text": chunk.content}, id=str(seq))
            elif "__interrupt__" in part["data"]:
                for intr in part["data"]["__interrupt__"]:
                    yield ServerSentEvent(event="interrupt", data=intr.value, id=str(seq))
            elif "tools" in part["data"]:
                for m in part["data"]["tools"]["messages"]:
                    yield ServerSentEvent(event="tool", data={"name": m.name, "result": str(m.content)[:80]}, id=str(seq))
    yield ServerSentEvent(event="end", data={"thread_id": thread_id})


@app.post("/threads/{thread_id}/runs/stream", response_class=EventSourceResponse)
async def run_stream(thread_id: str, req: RunRequest, user: UserCtx = Depends(current_user)):
    payload = {"messages": [{"role": "user", "content": req.message}]}
    async for ev in sse_events(payload, user, thread_id):
        yield ev


@app.post("/threads/{thread_id}/resume", response_class=EventSourceResponse)
async def resume(thread_id: str, req: ResumeRequest, user: UserCtx = Depends(current_user)):
    decision: dict[str, Any] = {"type": req.decision}
    if req.decision == "reject" and req.message:
        decision["message"] = req.message
    async for ev in sse_events(Command(resume={"decisions": [decision]}), user, thread_id):
        yield ev


@app.get("/threads/{thread_id}/state")
async def get_state(thread_id: str, user: UserCtx = Depends(current_user)) -> dict:
    snap = await app.state.agent.aget_state(run_config(user, thread_id))
    if not snap.values:
        raise HTTPException(status_code=404, detail="thread not found")
    return {
        "messages": [{"type": m.type, "content": str(m.content)[:80]} for m in snap.values["messages"]],
        "next": list(snap.next),
        "pending_interrupts": [i.value for t in snap.tasks for i in t.interrupts],
    }
