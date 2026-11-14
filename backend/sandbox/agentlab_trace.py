"""AgentLab 실행 트레이서.

사용자 코드를 고치지 않고 LangChain/LangGraph 실행 이벤트(그래프·노드·LLM·도구·리트리버)를 수집해
AGENTLAB_TRACE_FD 파이프로 한 줄에 하나씩 JSON 으로 내보낸다. stdout/stderr 는 건드리지 않는다.

- LangChain 전역 configure hook 에 등록하므로 모든 invoke/stream 에 자동으로 붙는다.
- LangGraph 내부 실행 단위(tag "langsmith:hidden")는 숨기고, 그 자식은 가장 가까운 보이는 조상에 붙인다.
- 값은 JSON 으로 바꿀 수 있는 형태로 줄이고, 긴 문자열·큰 컬렉션은 잘라 낸다.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

ENV_FD = "AGENTLAB_TRACE_FD"
ENV_ON = "AGENTLAB_TRACE"
MAX_STR = 4000
MAX_ITEMS = 60
MAX_DEPTH = 8
MAX_EVENT_BYTES = 256_000
MAX_EVENTS = 4000
HIDDEN_TAG = "langsmith:hidden"


# ---------------------------------------------------------------- 직렬화
def _msg(m: Any) -> dict:
    d: dict[str, Any] = {"role": getattr(m, "type", m.__class__.__name__), "content": _ser(m.content, 1)}
    for attr in ("name", "tool_call_id", "id"):
        v = getattr(m, attr, None)
        if v:
            d[attr] = v
    tc = getattr(m, "tool_calls", None)
    if tc:
        d["tool_calls"] = [{"id": c.get("id"), "name": c.get("name"), "args": _ser(c.get("args"), 1)} for c in tc]
    usage = getattr(m, "usage_metadata", None)
    if usage:
        d["usage"] = _usage(usage)
    status = getattr(m, "status", None)
    if status and status != "success":
        d["status"] = status
    return d


def _usage(u: Any) -> dict | None:
    if not u:
        return None
    try:
        get = u.get if isinstance(u, dict) else lambda k, default=None: getattr(u, k, default)
        out = {
            "input": int(get("input_tokens", 0) or get("prompt_tokens", 0) or 0),
            "output": int(get("output_tokens", 0) or get("completion_tokens", 0) or 0),
        }
        out["total"] = int(get("total_tokens", 0) or out["input"] + out["output"])
        details = get("input_token_details") or {}
        if isinstance(details, dict) and details.get("cache_read"):
            out["cached"] = int(details["cache_read"])
        details = get("output_token_details") or {}
        if isinstance(details, dict) and details.get("reasoning"):
            out["reasoning"] = int(details["reasoning"])
        return out
    except Exception:
        return None


def _ser(v: Any, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        return "…"
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v if len(v) <= MAX_STR else v[:MAX_STR] + f"… (+{len(v) - MAX_STR}자)"
    if isinstance(v, (UUID, bytes)):
        return str(v)[:200]
    try:
        from langchain_core.messages import BaseMessage

        if isinstance(v, BaseMessage):
            return _msg(v)
    except Exception:
        pass
    try:
        from langchain_core.documents import Document

        if isinstance(v, Document):
            return {"page_content": _ser(v.page_content, depth + 1), "metadata": _ser(v.metadata, depth + 1)}
    except Exception:
        pass
    if isinstance(v, dict):
        items = list(v.items())
        out = {str(k): _ser(x, depth + 1) for k, x in items[:MAX_ITEMS]}
        if len(items) > MAX_ITEMS:
            out["…"] = f"+{len(items) - MAX_ITEMS}개"
        return out
    if isinstance(v, (list, tuple, set, frozenset)):
        items = list(v)
        out = [_ser(x, depth + 1) for x in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            out.append(f"… +{len(items) - MAX_ITEMS}개")
        return out
    # LangGraph Command / Send / Interrupt
    cls = v.__class__.__name__
    if cls in ("Command", "Send", "Interrupt"):
        fields = {k: getattr(v, k) for k in ("goto", "update", "resume", "graph", "node", "arg", "value") if getattr(v, k, None) is not None}
        return {"__type__": cls, **{k: _ser(x, depth + 1) for k, x in fields.items()}}
    if hasattr(v, "model_dump"):
        try:
            return {"__type__": cls, **_ser(v.model_dump(), depth + 1)}
        except Exception:
            pass
    if hasattr(v, "__dataclass_fields__"):
        try:
            return {"__type__": cls, **{k: _ser(getattr(v, k), depth + 1) for k in v.__dataclass_fields__}}
        except Exception:
            pass
    s = repr(v)
    return s if len(s) <= 500 else s[:500] + "…"


# ---------------------------------------------------------------- 출력
class _Sink:
    def __init__(self) -> None:
        fd = os.environ.get(ENV_FD)
        self.fd = int(fd) if fd and fd.isdigit() else None
        self.lock = threading.Lock()
        self.count = 0
        self.t0 = time.perf_counter()

    def emit(self, ev: dict) -> None:
        if self.fd is None:
            return
        ev["t"] = round((time.perf_counter() - self.t0) * 1000, 1)
        with self.lock:
            if self.count >= MAX_EVENTS:
                return
            self.count += 1
            line = json.dumps(ev, ensure_ascii=False, default=str)
            if len(line) > MAX_EVENT_BYTES:
                for key in ("inputs", "outputs", "messages"):
                    if key in ev:
                        ev[key] = "(너무 커서 생략)"
                line = json.dumps(ev, ensure_ascii=False, default=str)[:MAX_EVENT_BYTES]
            data = (line + "\n").encode("utf-8", errors="replace")
            try:
                while data:
                    n = os.write(self.fd, data)
                    data = data[n:]
            except OSError:
                self.fd = None


_sink = _Sink()


# ---------------------------------------------------------------- 콜백
class AgentLabTracer(BaseCallbackHandler):
    """프로세스 전체에서 하나만 쓰는 트레이서 (configure hook 이 여러 번 만들어도 같은 객체)."""

    run_inline = True  # 비동기 실행에서도 이벤트 순서를 보존한다
    raise_error = False
    _instance: "AgentLabTracer | None" = None

    def __new__(cls, *a, **kw):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def __init__(self) -> None:
        if self._ready:
            return
        super().__init__()
        self._ready = True
        self.lock = threading.Lock()
        self.visible_parent: dict[str, str | None] = {}  # run_id → 보이는 조상 id
        self.hidden: set[str] = set()

    # ---- 공통 ----------------------------------------------------------
    def _parent(self, parent_run_id: UUID | None) -> str | None:
        if parent_run_id is None:
            return None
        p = str(parent_run_id)
        with self.lock:
            return self.visible_parent.get(p, p) if p in self.hidden else p

    def _register(self, run_id: UUID, parent_run_id: UUID | None, hidden: bool) -> str | None:
        rid, parent = str(run_id), self._parent(parent_run_id)
        with self.lock:
            if hidden:
                self.hidden.add(rid)
                self.visible_parent[rid] = parent
        return parent

    def _end(self, run_id: UUID, **data: Any) -> None:
        rid = str(run_id)
        with self.lock:
            hidden = rid in self.hidden
        if not hidden:
            _sink.emit({"ev": "end", "id": rid, **data})

    @staticmethod
    def _meta(metadata: dict | None) -> dict:
        m = metadata or {}
        out = {}
        for k in ("langgraph_node", "langgraph_step", "langgraph_triggers", "ls_model_name", "ls_provider", "ls_temperature"):
            if m.get(k) is not None:
                out[k] = _ser(m[k], 1)
        return out

    @staticmethod
    def _name(serialized: dict | None, kwargs: dict, default: str) -> str:
        if kwargs.get("name"):
            return str(kwargs["name"])
        s = serialized or {}
        if s.get("name"):
            return str(s["name"])
        ident = s.get("id")
        if isinstance(ident, list) and ident:
            return str(ident[-1])
        return default

    # ---- 체인 (그래프·노드·조건 분기) ----------------------------------
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        tags = tags or []
        name = self._name(serialized, kwargs, "chain")
        hidden = HIDDEN_TAG in tags
        parent = self._register(run_id, parent_run_id, hidden)
        if hidden:
            return
        meta = self._meta(metadata)
        if meta.get("langgraph_node") == name:
            kind = "node"
        elif parent is None or name in ("LangGraph",) or tags and any(t.startswith("graph:") for t in tags):
            kind = "graph"
        else:
            kind = "chain"
        _sink.emit({"ev": "start", "id": str(run_id), "parent": parent, "kind": kind, "name": name, "meta": meta, "inputs": _ser(inputs)})

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._end(run_id, outputs=_ser(outputs))

    def on_chain_error(self, error, *, run_id, **kwargs):
        # interrupt 는 오류가 아니라 일시 정지
        name = error.__class__.__name__
        status = "interrupted" if name in ("GraphInterrupt", "NodeInterrupt", "ParentCommand") else "error"
        self._end(run_id, status=status, error=f"{name}: {str(error)[:1000]}")

    # ---- LLM ----------------------------------------------------------
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        parent = self._register(run_id, parent_run_id, False)
        params = kwargs.get("invocation_params") or {}
        tools = params.get("tools") or []
        tool_names = []
        for t in tools:
            fn = t.get("function", t) if isinstance(t, dict) else {}
            if isinstance(fn, dict) and fn.get("name"):
                tool_names.append(fn["name"])
        meta = self._meta(metadata)
        model = meta.get("ls_model_name") or params.get("model") or params.get("model_name")
        flat = [m for batch in messages for m in batch]
        _sink.emit({
            "ev": "start",
            "id": str(run_id),
            "parent": parent,
            "kind": "llm",
            "name": self._name(serialized, kwargs, "ChatModel"),
            "meta": meta,
            "model": model,
            "tools": tool_names,
            "tool_choice": _ser(params.get("tool_choice"), 1),
            "messages": [_msg(m) for m in flat[-MAX_ITEMS:]],
        })

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        parent = self._register(run_id, parent_run_id, False)
        _sink.emit({
            "ev": "start", "id": str(run_id), "parent": parent, "kind": "llm",
            "name": self._name(serialized, kwargs, "LLM"), "meta": self._meta(metadata),
            "messages": [{"role": "human", "content": _ser(p)} for p in prompts[:MAX_ITEMS]],
        })

    def on_llm_end(self, response, *, run_id, **kwargs):
        message, usage = None, None
        try:
            gen = response.generations[0][0]
            m = getattr(gen, "message", None)
            message = _msg(m) if m is not None else {"role": "ai", "content": _ser(gen.text)}
            usage = message.get("usage")
        except Exception:
            pass
        if not usage:
            out = response.llm_output or {}
            usage = _usage(out.get("token_usage") or out.get("usage"))
        self._end(run_id, message=message, usage=usage)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._end(run_id, status="error", error=f"{error.__class__.__name__}: {str(error)[:1000]}")

    # ---- 도구 ----------------------------------------------------------
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None, inputs=None, **kwargs):
        parent = self._register(run_id, parent_run_id, False)
        _sink.emit({
            "ev": "start", "id": str(run_id), "parent": parent, "kind": "tool",
            "name": self._name(serialized, kwargs, "tool"), "meta": self._meta(metadata),
            "inputs": _ser(inputs if inputs is not None else input_str),
        })

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._end(run_id, outputs=_ser(output))

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._end(run_id, status="error", error=f"{error.__class__.__name__}: {str(error)[:1000]}")

    # ---- 리트리버 -------------------------------------------------------
    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        parent = self._register(run_id, parent_run_id, False)
        _sink.emit({
            "ev": "start", "id": str(run_id), "parent": parent, "kind": "retriever",
            "name": self._name(serialized, kwargs, "retriever"), "meta": self._meta(metadata), "inputs": _ser(query),
        })

    def on_retriever_end(self, documents, *, run_id, **kwargs):
        self._end(run_id, outputs=_ser(list(documents)))

    def on_retriever_error(self, error, *, run_id, **kwargs):
        self._end(run_id, status="error", error=f"{error.__class__.__name__}: {str(error)[:1000]}")


_var: ContextVar[AgentLabTracer | None] = ContextVar("agentlab_tracer", default=None)


def install() -> None:
    if _sink.fd is None:
        return
    from langchain_core.tracers.context import register_configure_hook

    os.environ[ENV_ON] = "1"
    register_configure_hook(_var, inheritable=True, handle_class=AgentLabTracer, env_var=ENV_ON)
