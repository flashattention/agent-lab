"""AgentLab Mock LLM.

OPENAI_API_KEY 없이도 학습 예제가 끝까지 실행되도록 ChatOpenAI / OpenAIEmbeddings 를
결정적(deterministic) 모의 모델로 교체한다. tool calling, structured output, streaming 을
흉내 내며, 실제 LLM 의 "추론"은 하지 않는다.

규칙 요약
- 바인딩된 도구가 있고 마지막 사람 메시지 이후 도구 결과가 없으면 → 도구 호출 생성
- tool_choice 가 강제(any/required/특정 이름)되면 → 항상 도구 호출 (structured output 포함)
- Literal/enum 필드는 "이미 진행된 턴 수"에 따라 순환 선택, FINISH/END 류 옵션은 마지막에 선택
- 그 외에는 짧은 한국어 모의 응답 텍스트
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

FINISH_WORDS = {"finish", "end", "__end__", "done", "complete", "stop", "final", "respond"}


def _text(msg: BaseMessage) -> str:
    c = msg.content
    if isinstance(c, str):
        return c
    parts = []
    for b in c or []:
        if isinstance(b, str):
            parts.append(b)
        elif isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    return " ".join(parts)


def _last_human_index(messages: Sequence[BaseMessage]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return i
    return -1


class _Ctx:
    def __init__(self, messages: Sequence[BaseMessage]):
        self.messages = list(messages)
        hi = _last_human_index(messages)
        self.human = _text(messages[hi]) if hi >= 0 else ""
        if not self.human:
            # 사람 메시지가 없으면 마지막 비시스템 메시지 텍스트 사용
            for m in reversed(messages):
                if not isinstance(m, SystemMessage):
                    self.human = _text(m)
                    break
        self.after = list(messages[hi + 1 :]) if hi >= 0 else []
        self.turns = sum(1 for m in self.after if isinstance(m, (AIMessage, ToolMessage)))
        self.all_text = " ".join(_text(m) for m in messages)
        # 'B-2048' 같은 ID 의 숫자는 제외하고, '30,000' 같은 천 단위 구분은 허용한다
        nums = re.findall(r"(?<![\w-])\d[\d,]*(?:\.\d+)?", self.human)
        self.numbers = [float(x.replace(",", "")) if "." in x else int(x.replace(",", "")) for x in nums]
        self.ids = re.findall(r"\b[A-Z]{1,4}-\d{2,}\b|#\d{3,}", self.human)


def _pick_enum(options: list[Any], ctx: _Ctx, name: str) -> Any:
    lowered = ctx.human.lower()
    finish = [o for o in options if str(o).lower() in FINISH_WORDS]
    rest = [o for o in options if o not in finish]
    if not rest:
        return options[0]
    # 첫 턴에서는 질문에 등장하는 옵션을 우선 선택 (라우터 예제용)
    if ctx.turns == 0:
        for o in rest:
            if str(o).lower() in lowered:
                return o
    if finish and ctx.turns >= len(rest):
        return finish[0]
    return rest[ctx.turns % len(rest)]


def _fake_value(schema: dict, name: str, ctx: _Ctx, defs: dict, num_iter: Iterator) -> Any:
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return _fake_value(defs.get(ref, {}), name, ctx, defs, num_iter)
    if "enum" in schema:
        return _pick_enum(schema["enum"], ctx, name)
    if "const" in schema:
        return schema["const"]
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"] or schema[key]
            return _fake_value(options[0], name, ctx, defs, num_iter)
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    t = schema.get("type", "string")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    lname = name.lower()
    if t == "object":
        props = schema.get("properties", {})
        return {k: _fake_value(v, k, ctx, defs, num_iter) for k, v in props.items()}
    if t == "array":
        item = schema.get("items", {"type": "string"})
        n = max(1, min(3, schema.get("minItems", 2)))
        return [_fake_value(item, name, ctx, defs, num_iter) for _ in range(n)]
    if t == "boolean":
        return True
    if t in ("integer", "number"):
        if any(k in lname for k in ("score", "grade", "rating", "confidence")):
            v = 8 if t == "integer" else 0.8
        else:
            v = next(num_iter, None)
            if v is None:
                v = 2
        # 스키마의 범위 제약(ge/le)을 지켜 검증 재시도 루프를 피한다
        lo = schema.get("minimum", schema.get("exclusiveMinimum"))
        hi = schema.get("maximum", schema.get("exclusiveMaximum"))
        if hi is not None and v > hi:
            v = hi
        if lo is not None and v < lo:
            v = lo
        return int(v) if t == "integer" else float(v)
    # string
    if any(k in lname for k in ("query", "question", "input", "topic", "text", "search", "task", "request")):
        return ctx.human[:200] or "sample"
    if (lname.endswith("id") or lname.endswith("_no") or "number" in lname) and ctx.ids:
        return ctx.ids[0].lstrip("#")
    if any(k in lname for k in ("city", "location")):
        m = re.search(r"(서울|부산|도쿄|뉴욕|Seoul|Busan|Tokyo|New York|London|Paris)", ctx.human)
        return m.group(1) if m else "서울"
    if any(k in lname for k in ("reason", "explanation", "rationale", "feedback", "critique")):
        return "(mock) 입력을 검토한 결과에 따른 판단입니다."
    if any(k in lname for k in ("answer", "summary", "content", "response", "draft", "result")):
        return f"(mock) '{ctx.human[:60]}'에 대한 {name}"
    return f"(mock) {name}"


def _fake_args(tool: dict, ctx: _Ctx) -> dict:
    fn = tool.get("function", tool)
    params = fn.get("parameters", {}) or {}
    defs = params.get("$defs", params.get("definitions", {}))
    num_iter = iter(ctx.numbers)
    return {k: _fake_value(v, k, ctx, defs, num_iter) for k, v in params.get("properties", {}).items()}


def _score_tool(tool: dict, ctx: _Ctx) -> int:
    fn = tool.get("function", tool)
    words = re.findall(r"[a-z]+|[가-힣]+", (fn.get("name", "") + " " + fn.get("description", "")).lower())
    text = ctx.human.lower()
    return sum(1 for w in set(words) if len(w) > 2 and w in text)


class MockChatModel(BaseChatModel):
    """도구 호출과 구조화 출력을 흉내 내는 결정적 모의 채팅 모델."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    model: str = "mock-gpt"
    model_name: str | None = None
    bound_tools: list[dict] = Field(default_factory=list)
    tool_choice: Any = None

    def __init__(self, *args: Any, **kwargs: Any):
        if args and "model" not in kwargs:
            kwargs["model"] = args[0]
        known = {"model", "model_name", "bound_tools", "tool_choice", "callbacks", "tags", "metadata", "name"}
        if "model_name" in kwargs and "model" not in kwargs:
            kwargs["model"] = kwargs["model_name"]
        super().__init__(**{k: v for k, v in kwargs.items() if k in known})

    @property
    def _llm_type(self) -> str:
        return "agentlab-mock"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **kwargs: Any):
        converted = [convert_to_openai_tool(t) for t in tools]
        return self.model_copy(update={"bound_tools": converted, "tool_choice": tool_choice})

    # ------------------------------------------------------------------ core
    def _respond(self, messages: list[BaseMessage]) -> AIMessage:
        ctx = _Ctx(messages)
        tools = self.bound_tools
        forced = self.tool_choice not in (None, "auto", "none", False)
        has_tool_result = any(isinstance(m, ToolMessage) for m in ctx.after)

        if tools and (forced or not has_tool_result):
            chosen: list[dict]
            if isinstance(self.tool_choice, str) and self.tool_choice not in ("any", "required", True):
                chosen = [t for t in tools if t["function"]["name"] == self.tool_choice] or tools[:1]
            elif isinstance(self.tool_choice, dict):
                name = self.tool_choice.get("function", {}).get("name") or self.tool_choice.get("name")
                chosen = [t for t in tools if t["function"]["name"] == name] or tools[:1]
            else:
                scored = sorted(((_score_tool(t, ctx), i, t) for i, t in enumerate(tools)), key=lambda x: (-x[0], x[1]))
                chosen = [t for s, _, t in scored if s > 0][:3] or [scored[0][2]]
                if forced:
                    chosen = chosen[:1]
            calls = [
                {
                    "name": t["function"]["name"],
                    "args": _fake_args(t, ctx),
                    "id": "call_" + uuid.uuid4().hex[:12],
                    "type": "tool_call",
                }
                for t in chosen
            ]
            return AIMessage(content="", tool_calls=calls, response_metadata={"model_name": self.model})

        if has_tool_result:
            results = [_text(m)[:160] for m in ctx.after if isinstance(m, ToolMessage)]
            body = f"도구 실행 결과를 바탕으로 정리한 답변입니다: {' | '.join(results)}"
        else:
            body = f"'{ctx.human[:80]}'에 대한 모의 응답입니다. 실제 답변을 보려면 설정에서 OpenAI API Key를 입력하세요."
        return AIMessage(content=f"[mock:{self.model}] {body}", response_metadata={"model_name": self.model})

    def _usage(self, messages: list[BaseMessage], out: AIMessage) -> dict:
        inp = sum(len(_text(m)) for m in messages) // 3 + 1
        o = len(_text(out)) // 3 + 1 + 10 * len(out.tool_calls)
        return {"input_tokens": inp, "output_tokens": o, "total_tokens": inp + o}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = self._respond(messages)
        msg.usage_metadata = self._usage(messages, msg)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        msg = self._respond(messages)
        if msg.tool_calls:
            chunk = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": c["name"], "args": json.dumps(c["args"], ensure_ascii=False), "id": c["id"], "index": i}
                    for i, c in enumerate(msg.tool_calls)
                ],
                usage_metadata=self._usage(messages, msg),
            )
            yield ChatGenerationChunk(message=chunk)
            return
        tokens = re.findall(r"\S+\s*", _text(msg))
        for i, tok in enumerate(tokens):
            chunk = AIMessageChunk(content=tok)
            if i == len(tokens) - 1:
                chunk.usage_metadata = self._usage(messages, msg)
            if run_manager:
                run_manager.on_llm_new_token(tok, chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)


class MockEmbeddings(Embeddings):
    """해시 기반 bag-of-words 임베딩. 같은 단어를 공유하는 문장일수록 유사도가 높다."""

    def __init__(self, *args: Any, size: int = 256, **kwargs: Any):
        self.size = size

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.size
        for w in re.findall(r"[a-z0-9]+|[가-힣]+", text.lower()):
            for gram in {w} | ({w[i : i + 2] for i in range(len(w) - 1)} if len(w) > 2 else set()):
                h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
                vec[h % self.size] += 1.0 if gram == w else 0.5
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def install() -> None:
    """langchain_openai 의 클래스를 모의 구현으로 교체한다."""
    try:
        import langchain_openai
    except Exception:
        return
    langchain_openai.ChatOpenAI = MockChatModel  # type: ignore[attr-defined]
    langchain_openai.OpenAIEmbeddings = MockEmbeddings  # type: ignore[attr-defined]
    try:
        import langchain_openai.chat_models as cm

        cm.ChatOpenAI = MockChatModel  # type: ignore[attr-defined]
    except Exception:
        pass
