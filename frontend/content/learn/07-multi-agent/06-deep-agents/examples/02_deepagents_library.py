"""deepagents 라이브러리: create_deep_agent 로 같은 구조를 한 번에

deepagents 0.7 기본 구성 (설치된 소스 기준)
- 파일 도구: ls, read_file, write_file, edit_file, delete, glob, grep  (기본 백엔드 = 그래프 상태의 files)
- execute: 셸 실행 (샌드박스 백엔드일 때만 동작, 기본 백엔드에서는 오류 메시지를 돌려줌)
- task: 서브에이전트 호출 (기본 'general-purpose' + 우리가 넘긴 subagents)
- write_todos 는 0.7 기본 스택에 없다 → langchain 의 TodoListMiddleware 를 middleware 로 직접 추가한다.
"""

import os

from deepagents import SubAgent, create_deep_agent
from deepagents.backends.utils import create_file_data
from langchain.agents.middleware import TodoListMiddleware
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.errors import GraphRecursionError

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def search_web(query: str) -> str:
    """웹에서 정보를 검색한다."""
    return f"[검색 결과] '{query[:25]}…' 관련 문서 5건"


# 서브에이전트는 TypedDict(SubAgent) 로 '선언'만 하면 라이브러리가 만들어 준다
researcher: SubAgent = {
    "name": "researcher",
    "description": "하나의 주제를 깊이 조사해 요약 보고서를 돌려준다. 한 번에 한 주제만 맡긴다.",
    "system_prompt": "당신은 조사 전문가입니다. search_web 으로 조사하고 핵심만 요약하세요.",
    "tools": [search_web],
}

agent = create_deep_agent(
    model=MODEL,  # 문자열이면 init_chat_model 로 초기화된다
    tools=[search_web],
    system_prompt="당신은 리서치 리드입니다. 계획을 세우고, 조사는 researcher 에게 맡기고, 결과는 파일로 남기세요.",
    subagents=[researcher],
    middleware=[TodoListMiddleware()],  # write_todos 도구 추가
    name="research_lead",
)


def show(title: str, out: dict) -> None:
    print("=" * 60)
    print(title)
    for m in out["messages"]:
        if isinstance(m, AIMessage) and m.tool_calls:
            print("  → 도구 호출:", [c["name"] for c in m.tool_calls])
        elif isinstance(m, ToolMessage):
            print(f"  ← {m.name}: {m.text[:70]}")
    print("  todos:", [(t["status"], t["content"][:25]) for t in out.get("todos", [])])
    print("  files:", list(out.get("files", {})))


if __name__ == "__main__":
    tool_names = list(agent.nodes["tools"].bound.tools_by_name)
    print("에이전트가 가진 도구:", tool_names)

    # 가상 파일시스템에 과제 설명 파일을 미리 넣어 시작할 수 있다
    seed_files = {"/brief.md": create_file_data("과제: 국내 전기차 충전 인프라 현황 조사")}
    config = {"recursion_limit": 30}  # 메인 에이전트의 상한 (서브에이전트도 별도로 상한을 둔다)

    try:
        out = agent.invoke({"messages": [HumanMessage("todo list 를 작성해 줘")], "files": seed_files}, config)
        show("[1] 계획 세우기 → write_todos", out)

        out = agent.invoke({"messages": [HumanMessage("researcher subagent 에게 task 위임")], "files": seed_files}, config)
        show("[2] 서브에이전트 위임 → task", out)
        print("-" * 60)
        print("참고: Mock 모델은 subagent_type 에 임의 문자열을 넣기 때문에 task 도구가")
        print("'허용된 타입은 general-purpose, researcher' 라는 오류를 '도구 결과'로 돌려줍니다.")
        print("예외로 멈추지 않고 모델이 스스로 고칠 기회를 주는 설계입니다. 실제 모델은 researcher 를 고릅니다.")
    except GraphRecursionError:
        print("⚠️ recursion_limit 도달: 에이전트가 작업을 끝내지 못했습니다.")
