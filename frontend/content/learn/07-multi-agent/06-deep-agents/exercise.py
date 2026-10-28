"""실습: 미니 Deep Agent 의 '파일 쓰기'와 '서브에이전트 위임' 도구 완성하기

완성할 것
1. write_file(content, path) 도구
   - Command(update={"files": {path: content}, "messages": [ToolMessage(..., tool_call_id=runtime.tool_call_id)]})
2. task(task_description, subagent_type) 도구
   - SUBAGENTS[subagent_type] 를 '새 대화'로 실행 (recursion_limit 10)
   - SUBAGENT_CALLS 에 subagent_type 기록
   - 최종 메시지 텍스트만 ToolMessage 로 돌려준다 (Command update)

자가 채점
- 파일 /report.md 가 생겼는가
- 서브에이전트가 1번 호출되었는가
- 서브에이전트 내부 도구(search_web) 흔적이 메인 대화에 없는가 (컨텍스트 격리)
"""

import os
from typing import Annotated, Literal, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def merge_files(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class DeepState(AgentState):
    files: NotRequired[Annotated[dict[str, str], merge_files]]


@tool
def write_file(content: str, runtime: ToolRuntime, path: str = "/report.md") -> Command:
    """report 를 가상 file 에 저장한다."""
    # TODO 1: Command(update={...}) 를 반환하세요.
    #   - "files": {path: content}
    #   - "messages": [ToolMessage("저장 완료 메시지", tool_call_id=runtime.tool_call_id)]
    raise NotImplementedError("TODO 1: write_file 을 완성하세요")


@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색한다."""
    return f"[검색] {query[:20]} 관련 자료"


SUBAGENTS = {
    "researcher": create_agent(MODEL, tools=[search_web], system_prompt="조사 후 요약하세요.", name="researcher"),
}
SUBAGENT_CALLS: list[str] = []


@tool
def task(task_description: str, subagent_type: Literal["researcher"], runtime: ToolRuntime) -> Command:
    """하위 작업을 researcher subagent 에게 위임하고 요약 결과만 받는다."""
    # TODO 2: SUBAGENT_CALLS 에 subagent_type 을 기록하세요.
    # TODO 3: SUBAGENTS[subagent_type] 를 {"messages": [HumanMessage(task_description)]} 로 실행하세요.
    #         (두 번째 인자 {"recursion_limit": 10})
    # TODO 4: 최종 메시지 텍스트만 담은 ToolMessage 를 Command(update={"messages": [...]}) 로 반환하세요.
    raise NotImplementedError("TODO 2~4: task 도구를 완성하세요")


agent = create_agent(
    MODEL,
    tools=[task, write_file],
    system_prompt="조사는 task 로 researcher 에게 맡기고, 결과는 write_file 로 저장하세요.",
    state_schema=DeepState,
)


if __name__ == "__main__":
    out = agent.invoke(
        {"messages": [HumanMessage("researcher subagent 에게 task 를 맡기고 report 를 file 로 저장해 줘")], "files": {}},
        {"recursion_limit": 15},
    )
    tool_names = [m.name for m in out["messages"] if isinstance(m, ToolMessage)]
    print("메인이 받은 도구 결과:", tool_names)
    print("files:", list(out.get("files", {})))
    print("서브에이전트 호출:", SUBAGENT_CALLS)

    assert "/report.md" in out.get("files", {}), "/report.md 파일이 저장되어야 합니다."
    assert SUBAGENT_CALLS == ["researcher"], "researcher 서브에이전트가 정확히 1번 호출되어야 합니다."
    assert "search_web" not in tool_names, "서브에이전트 내부 도구 결과가 메인 대화로 새어 나왔습니다."
    print("✅ 모든 테스트 통과!")
