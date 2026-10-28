"""그래프 스트림 → UI 이벤트 프로토콜 (8.1강).

  {"event": "agent",       "name": "order_agent"}       ← 어떤 전문가가 맡았나
  {"event": "token",       "text": "..."}
  {"event": "tool_call",   "name": "...", "args": {...}}
  {"event": "tool_result", "name": "...", "preview": "..."}
  {"event": "progress",    "data": {...}}
  {"event": "interrupt",   "value": {...}}
  {"event": "done",        "route": "..."}
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

SPECIALISTS = {"faq_agent", "order_agent", "smalltalk"}


def stream_ui_events(graph, payload: Any, config: dict, context: Any) -> Iterator[dict[str, Any]]:
    route = None
    announced: set[str] = set()
    seen_interrupts: set[str] = set()  # 서브그래프와 부모 양쪽에서 같은 interrupt 가 올라오므로 중복 제거
    for part in graph.stream(payload, config, context=context,
                             stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2"):
        kind, data, ns = part["type"], part["data"], part["ns"]
        owner = ns[0].split(":")[0] if ns else None  # 서브그래프 안이면 전문가 이름
        if owner in SPECIALISTS and owner not in announced:
            announced.add(owner)
            yield {"event": "agent", "name": owner}

        if kind == "messages":
            chunk, meta = data
            node = meta.get("langgraph_node")
            is_answer = (node == "model" and owner in SPECIALISTS) or "final_answer" in (meta.get("tags") or [])
            if not is_answer or chunk.type != "AIMessageChunk":
                continue
            for tc in getattr(chunk, "tool_call_chunks", None) or []:
                if tc.get("name"):
                    yield {"event": "tool_call", "name": tc["name"]}
            if chunk.content:
                yield {"event": "token", "text": chunk.content}
        elif kind == "updates":
            if "__interrupt__" in data:
                for intr in data["__interrupt__"]:
                    if intr.id not in seen_interrupts:
                        seen_interrupts.add(intr.id)
                        yield {"event": "interrupt", "id": intr.id, "value": intr.value}
            if not ns and "route" in data:
                route = data["route"].get("route")
            if not ns and "guard" in data and data["guard"]:
                route = data["guard"].get("route")
                for m in data["guard"].get("messages", []):
                    yield {"event": "token", "text": m.content}
            if ns and "tools" in data:
                for m in data["tools"].get("messages", []):
                    yield {"event": "tool_result", "name": m.name, "preview": str(m.content)[:60]}
        elif kind == "custom":
            yield {"event": "progress", "data": data}
    if route is None and config.get("configurable", {}).get("thread_id"):
        route = graph.get_state(config).values.get("route")  # resume 실행이면 상태에서 읽는다
    yield {"event": "done", "route": route}
