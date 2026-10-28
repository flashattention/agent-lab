"""미니 Deep Agent 를 처음부터 만들기: 계획(todos) + 가상 파일시스템(files) + 서브에이전트(task)

Deep Agent 의 네 기둥
1. 상세한 시스템 프롬프트 (작업 방식 가이드)
2. 계획 도구 write_todos  → 상태의 todos 에 체크리스트 저장
3. 가상 파일시스템 ls/read_file/write_file → 상태의 files 에 '메모장' 저장 (컨텍스트 밖에 보관)
4. 서브에이전트 task → 새 컨텍스트에서 하위 작업 수행 후 결과만 반환 (컨텍스트 격리)

모든 도구는 Command(update=...) 로 상태를 바꾸고, ToolRuntime 으로 상태와 tool_call_id 를 읽는다.
"""

import os
from typing import Annotated, Literal, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from pydantic import BaseModel

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


# ---------------------------------------------------------------------------
# 1) 상태: 메시지 + todos + files
# ---------------------------------------------------------------------------
def merge_files(left: dict[str, str] | None, right: dict[str, str] | None) -> dict[str, str]:
    """파일 딕셔너리 리듀서: 병렬 도구 호출이 각각 쓴 파일을 합친다."""
    return {**(left or {}), **(right or {})}


class DeepState(AgentState):
    todos: NotRequired[list[dict]]
    files: NotRequired[Annotated[dict[str, str], merge_files]]


# ---------------------------------------------------------------------------
# 2) 계획 도구
# ---------------------------------------------------------------------------
class Todo(BaseModel):
    content: str
    status: Literal["pending", "in_progress", "completed"]


@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime) -> Command:
    """todo list 를 작성하거나 갱신한다. 여러 단계가 필요한 작업을 시작할 때 먼저 계획을 세운다."""
    items = [t.model_dump() if isinstance(t, BaseModel) else dict(t) for t in todos]
    return Command(
        update={
            "todos": items,
            "messages": [ToolMessage(f"todo {len(items)}개를 저장했습니다.", tool_call_id=runtime.tool_call_id)],
        }
    )


# ---------------------------------------------------------------------------
# 3) 가상 파일시스템 도구 (실제 디스크가 아니라 그래프 상태에 저장)
# ---------------------------------------------------------------------------
@tool
def ls(runtime: ToolRuntime) -> str:
    """가상 파일시스템의 파일 목록을 본다."""
    return ", ".join(sorted(runtime.state.get("files", {}))) or "(비어 있음)"


@tool
def read_file(path: str, runtime: ToolRuntime) -> str:
    """가상 파일시스템에서 파일을 읽는다."""
    files = runtime.state.get("files", {})
    return files.get(path, f"오류: {path} 파일이 없습니다. 먼저 ls 로 목록을 확인하세요.")


@tool
def write_file(content: str, runtime: ToolRuntime, path: str = "/notes.md") -> Command:
    """report 나 메모를 가상 file 에 저장한다. 긴 중간 결과는 대화 대신 파일에 저장한다."""
    return Command(
        update={
            "files": {path: content},  # 리듀서가 기존 파일과 합친다
            "messages": [ToolMessage(f"{path} 저장 완료 ({len(content)}자)", tool_call_id=runtime.tool_call_id)],
        }
    )


# ---------------------------------------------------------------------------
# 4) 서브에이전트와 task 도구
# ---------------------------------------------------------------------------
@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색한다."""
    return f"[검색 결과] '{query[:25]}…' 관련 문서 5건 (총 4,000자 분량이라고 가정)"


SUBAGENTS = {
    "researcher": create_agent(
        MODEL, tools=[search_web], name="researcher",
        system_prompt="당신은 조사 전문가입니다. 검색 후 핵심을 5줄 이내로 요약해 보고하세요.",
    ),
    "critic": create_agent(
        MODEL, tools=[], name="critic",
        system_prompt="당신은 비평가입니다. 주어진 내용의 약점을 3가지 지적하세요.",
    ),
}
subagent_log: list[tuple[str, int]] = []  # (서브에이전트, 내부 메시지 수) 관찰용


@tool
def task(task_description: str, subagent_type: Literal["researcher", "critic"], runtime: ToolRuntime) -> Command:
    """하위 작업을 subagent 에게 위임한다. researcher=조사, critic=비평. 결과 요약만 돌아온다."""
    sub = SUBAGENTS[subagent_type]
    result = sub.invoke({"messages": [HumanMessage(task_description)]}, {"recursion_limit": 10})
    subagent_log.append((subagent_type, len(result["messages"])))
    return Command(
        update={"messages": [ToolMessage(result["messages"][-1].text, tool_call_id=runtime.tool_call_id)]}
    )


# ---------------------------------------------------------------------------
# 5) 메인 Deep Agent
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 장기 과제를 수행하는 리서치 에이전트입니다.
작업 방식:
1. 여러 단계가 필요하면 먼저 write_todos 로 계획을 세우고, 진행하며 상태를 갱신하세요.
2. 조사처럼 많은 정보를 다루는 일은 task 로 researcher 에게 맡기세요. 결과 요약만 받습니다.
3. 긴 결과물은 write_file 로 파일에 저장하고, 답변에서는 파일 경로와 핵심만 말하세요.
"""

agent = create_agent(
    MODEL,
    tools=[write_todos, ls, read_file, write_file, task],
    system_prompt=SYSTEM_PROMPT,
    state_schema=DeepState,
    name="deep_agent",
)

if __name__ == "__main__":
    question = "todo list 를 만들고, researcher subagent 에게 조사 task 를 맡긴 뒤 report 를 file 로 저장해 줘"
    out = agent.invoke({"messages": [HumanMessage(question)], "files": {}}, {"recursion_limit": 25})

    print("=" * 60)
    print("[메인 에이전트의 도구 호출]")
    for m in out["messages"]:
        if isinstance(m, AIMessage) and m.tool_calls:
            for c in m.tool_calls:
                args = {k: (str(v)[:40] + "…" if len(str(v)) > 40 else v) for k, v in c["args"].items()}
                print(f"  → {c['name']}({args})")
    print("\n[todos]")
    for t in out.get("todos", []):
        print(f"  [{t['status']:^11}] {t['content'][:50]}")
    print("\n[files]")
    for path, content in out.get("files", {}).items():
        print(f"  {path}: {content[:60]}…")
    print("\n[서브에이전트 내부 메시지 수]", subagent_log, "→ 메인에는 ToolMessage 1개씩만 전달")
    print("\n[최종 답변]", out["messages"][-1].text[:120])
