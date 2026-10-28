"""관측성의 기본: run_name / tags / metadata 와 '나만의 미니 트레이서'.

LangSmith는 LangChain 콜백 시스템 위에서 동작한다. 환경변수만 켜면
(LANGSMITH_TRACING=true, LANGSMITH_API_KEY=...) 모든 실행이 자동으로 기록된다.
이 예제는 네트워크 없이 같은 원리를 체험하도록, 콜백 핸들러로 실행 트리를 직접 모은다.

- config 의 run_name / tags / metadata 가 트레이스에 어떻게 실리는지
- 모델 호출·도구 호출이 부모-자식 트리로 어떻게 엮이는지
- get_usage_metadata_callback() 으로 토큰 사용량을 집계하는 법
"""

from __future__ import annotations

import os
import time
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.callbacks import BaseCallbackHandler, get_usage_metadata_callback

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def lookup_order(order_id: str) -> str:
    """주문 번호(order)로 배송 상태를 조회한다."""
    time.sleep(0.05)  # 외부 API 지연 흉내
    return f"{order_id}: 배송 중 (내일 도착 예정)"


agent = create_agent(MODEL, tools=[lookup_order], system_prompt="고객 지원 에이전트")


class MiniTracer(BaseCallbackHandler):
    """LangSmith 트레이서를 아주 단순하게 흉내 낸 콜백 핸들러.

    각 run 을 {id, parent, type, name, tags, metadata, 시작/끝 시각} 레코드로 저장한다.
    """

    def __init__(self) -> None:
        self.runs: dict[UUID, dict[str, Any]] = {}

    # ---- 공통 헬퍼
    def _start(self, run_id: UUID, parent_run_id: UUID | None, kind: str, label: str, kw: dict[str, Any]) -> None:
        self.runs[run_id] = {
            "parent": parent_run_id,
            "kind": kind,
            "name": label,
            "tags": kw.get("tags") or [],
            "metadata": kw.get("metadata") or {},
            "start": time.perf_counter(),
            "end": None,
            "error": None,
        }

    def _end(self, run_id: UUID, error: BaseException | None = None) -> None:
        if run_id in self.runs:
            self.runs[run_id]["end"] = time.perf_counter()
            self.runs[run_id]["error"] = repr(error) if error else None

    # ---- 체인(그래프/노드) 이벤트
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kw):  # noqa: D401
        self._start(run_id, parent_run_id, "chain", kw.get("name") or "chain", kw)

    def on_chain_end(self, outputs, *, run_id, **kw):
        self._end(run_id)

    def on_chain_error(self, error, *, run_id, **kw):
        self._end(run_id, error)

    # ---- 모델 이벤트
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kw):
        name = (kw.get("metadata") or {}).get("ls_model_name", "chat_model")
        self._start(run_id, parent_run_id, "llm", name, kw)

    def on_llm_end(self, response, *, run_id, **kw):
        self._end(run_id)

    # ---- 도구 이벤트
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kw):
        self._start(run_id, parent_run_id, "tool", (serialized or {}).get("name") or kw.get("name") or "tool", kw)

    def on_tool_end(self, output, *, run_id, **kw):
        self._end(run_id)

    # ---- 트리 출력
    def print_tree(self, kinds: tuple[str, ...] = ("chain", "llm", "tool"), max_depth: int = 3) -> None:
        children: dict[UUID | None, list[UUID]] = {}
        for rid, r in self.runs.items():
            children.setdefault(r["parent"], []).append(rid)

        def walk(rid: UUID, depth: int) -> None:
            r = self.runs[rid]
            ms = ((r["end"] or r["start"]) - r["start"]) * 1000
            if r["kind"] in kinds and depth <= max_depth:
                icon = {"chain": "⛓", "llm": "🧠", "tool": "🔧"}[r["kind"]]
                extra = f" tags={r['tags']}" if depth == 0 else ""
                print(f"{'   ' * depth}{icon} {r['name']} ({ms:.0f}ms){extra}")
            for c in children.get(rid, []):
                walk(c, depth + 1)

        for root in children.get(None, []):
            walk(root, 0)


tracer = MiniTracer()

# 실무에서 트레이스에 꼭 넣는 정보: 누가(user_id), 어떤 대화(thread_id), 어떤 버전(app_version)
config = {
    "run_name": "support-agent",  # 트레이스 목록에서 보이는 이름
    "tags": ["prod", "support", "v2.3.1"],  # 필터링용 짧은 라벨
    "metadata": {"user_id": "u-42", "tenant": "acme", "prompt_version": "support-v7"},
    "callbacks": [tracer],
}

print("=" * 70 + "\n1) 에이전트 실행 + 사용량 집계\n" + "=" * 70)
with get_usage_metadata_callback() as usage_cb:
    result = agent.invoke({"messages": [{"role": "user", "content": "주문 A-77 order 상태 알려줘"}]}, config)
print("최종 답변:", result["messages"][-1].content[:80])
for model_name, usage in usage_cb.usage_metadata.items():
    print(f"토큰 사용량[{model_name}]: in={usage['input_tokens']} out={usage['output_tokens']}")

print("\n" + "=" * 70 + "\n2) 실행 트리 (LangSmith 트레이스 화면과 같은 구조)\n" + "=" * 70)
tracer.print_tree(max_depth=2)

print("\n" + "=" * 70 + "\n3) metadata 는 하위 run 으로 전파된다\n" + "=" * 70)
llm_runs = [r for r in tracer.runs.values() if r["kind"] == "llm"]
tool_runs = [r for r in tracer.runs.values() if r["kind"] == "tool"]
print("LLM 호출 수:", len(llm_runs), "| 도구 호출 수:", len(tool_runs))
print("LLM run 의 metadata.user_id =", llm_runs[0]["metadata"].get("user_id"))
print("LLM run 의 tags =", llm_runs[0]["tags"][:3])
assert llm_runs[0]["metadata"].get("user_id") == "u-42", "metadata 는 자식 run 에 상속된다"
