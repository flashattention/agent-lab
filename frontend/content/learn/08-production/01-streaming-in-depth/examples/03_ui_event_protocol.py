"""그래프 스트림 → 프론트엔드용 'UI 이벤트 프로토콜' 변환기 (async).

현업 채팅 UI는 LangGraph 원시 이벤트를 그대로 받지 않는다.
백엔드가 아래처럼 '작고 안정적인' 이벤트 스키마로 바꿔서 SSE/WebSocket으로 보낸다.

    {"event": "token",       "text": "..."}
    {"event": "tool_call",   "name": "...", "args": {...}}
    {"event": "tool_result", "name": "...", "preview": "..."}
    {"event": "progress",    "data": {...}}
    {"event": "interrupt",   "value": {...}}     ← 사람 승인 요청 (HITL)
    {"event": "done"}

이 예제는 승인이 필요한 환불 도구를 가진 에이전트를 비동기(astream)로 실행하고,
interrupt 에서 멈췄다가 Command(resume=...)로 재개하는 전 과정을 이벤트로 보여준다.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def refund_order(order_id: str, runtime: ToolRuntime) -> str:
    """주문(order)을 환불(refund)한다. 실행 전 사람 승인이 필요하다."""
    runtime.stream_writer({"step": "결제사 환불 API 호출 중"})
    return f"주문 {order_id} 환불 완료"


agent = create_agent(
    MODEL,
    tools=[refund_order],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"refund_order": True})],
    checkpointer=InMemorySaver(),  # interrupt/resume 에는 체크포인터가 필수
)


async def to_ui_events(stream: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """LangGraph v2 스트림 파트를 UI 이벤트로 변환한다."""
    async for part in stream:
        kind, data = part["type"], part["data"]
        if kind == "messages":
            chunk, meta = data
            if meta["langgraph_node"] != "model":
                continue  # ToolMessage 등은 아래 updates 에서 처리
            for tc in getattr(chunk, "tool_call_chunks", None) or []:
                if tc.get("name"):  # 도구 호출의 첫 조각에만 이름이 있다
                    yield {"event": "tool_call", "name": tc["name"], "args": json.loads(tc.get("args") or "{}")}
            if chunk.content:
                yield {"event": "token", "text": chunk.content}
        elif kind == "updates":
            if "__interrupt__" in data:  # HITL: 그래프가 멈췄다
                for intr in data["__interrupt__"]:
                    yield {"event": "interrupt", "id": intr.id, "value": intr.value}
            for msg in (data.get("tools") or {}).get("messages", []):
                yield {"event": "tool_result", "name": msg.name, "preview": str(msg.content)[:40]}
        elif kind == "custom":
            yield {"event": "progress", "data": data}
    yield {"event": "done"}


async def run_turn(payload: Any, config: dict) -> list[dict[str, Any]]:
    """한 번의 요청(턴)을 실행하고 UI 이벤트를 출력/수집한다."""
    events = []
    stream = agent.astream(payload, config, stream_mode=["messages", "updates", "custom"], version="v2")
    async for ev in to_ui_events(stream):
        events.append(ev)
        if ev["event"] == "token":
            print(ev["text"], end="", flush=True)  # 타자 치듯 출력
        else:
            print(f"\n  ⮕ {json.dumps(ev, ensure_ascii=False, default=str)[:140]}")
    return events


async def main() -> None:
    config = {"configurable": {"thread_id": "ui-demo-1"}}

    print("=" * 70 + "\n① 사용자: 환불 요청 → 승인 대기에서 멈춤\n" + "=" * 70)
    first = await run_turn({"messages": [{"role": "user", "content": "주문 A-1001 refund 해주세요"}]}, config)
    interrupts = [e for e in first if e["event"] == "interrupt"]
    assert interrupts, "환불 도구는 interrupt 를 발생시켜야 한다"

    # 프론트엔드는 interrupt 이벤트를 받으면 '승인/거절' 버튼을 띄운다.
    # 상담원이 승인했다고 가정하고 같은 thread_id 로 resume 한다.
    print("\n" + "=" * 70 + "\n② 상담원: 승인 → 같은 thread 로 재개\n" + "=" * 70)
    resume = Command(resume={"decisions": [{"type": "approve"}]})
    second = await run_turn(resume, config)
    assert any(e["event"] == "tool_result" for e in second)
    assert second[-1]["event"] == "done"
    print("\n이벤트 종류:", sorted({e["event"] for e in first + second}))


asyncio.run(main())
