"""정답: 기억하고, 사용자를 알아보는 사내 IT 헬프데스크 에이전트

요구사항
  - 직원 정보(employee_id, department, is_admin)는 인증 시스템이 런타임 컨텍스트로 넣어 준다.
  - 도구 list_my_devices는 반드시 '컨텍스트의 employee_id'로 조회해야 한다 (모델이 인자로 지어내면 안 됨).
  - 시스템 프롬프트는 부서와 관리자 여부에 따라 달라진다.
  - 같은 thread_id에서는 대화가 이어지고, 다른 thread_id는 격리된다.

TODO ① list_my_devices: runtime 인자(ToolRuntime[EmployeeContext])에서 employee_id를 꺼내 조회하세요.
TODO ② helpdesk_prompt : @dynamic_prompt로 만들고, 부서 이름을 포함한 프롬프트를 반환하세요.
         is_admin이면 ADMIN_NOTE 문장을 덧붙이세요.
TODO ③ build_agent     : tools, middleware, context_schema, checkpointer를 모두 연결하세요.

채점 기준(Mock 모드에서도 통과)
- 도구 결과에 컨텍스트의 employee_id가 들어 있다
- 관리자 컨텍스트로 실행하면 실제 시스템 프롬프트에 ADMIN_NOTE가 포함된다
- 같은 thread의 2번째 호출 결과에는 1번째 질문이 남아 있고, 다른 thread에는 없다
"""

import os
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
ADMIN_NOTE = "이 직원은 관리자이므로 장비 초기화 절차를 안내해도 된다."
DEVICES = {"E-100": ["노트북 L-1", "모니터 M-7"], "E-200": ["노트북 L-9"]}
PROMPTS_SEEN: list[str] = []


@dataclass
class EmployeeContext:
    employee_id: str
    department: str
    is_admin: bool = False


@tool
def list_my_devices(runtime: ToolRuntime[EmployeeContext]) -> str:
    """현재 로그인한 직원에게 지급된 장비 목록을 조회합니다."""
    # ① 모델이 아니라 인증 시스템이 넣어 준 값으로 조회 → 위조 불가
    employee_id = runtime.context.employee_id
    return f"{employee_id}: {DEVICES.get(employee_id, [])}"


# ② 매 모델 호출 직전에 컨텍스트로 프롬프트를 계산
@dynamic_prompt
def helpdesk_prompt(request: ModelRequest) -> str:
    ctx: EmployeeContext = request.runtime.context
    prompt = f"너는 사내 IT 헬프데스크다. 지금 대화 중인 직원의 부서는 {ctx.department}이다."
    if ctx.is_admin:
        prompt += " " + ADMIN_NOTE
    PROMPTS_SEEN.append(prompt)
    return prompt


def build_agent():
    # ③ 도구 + 동적 프롬프트 + 컨텍스트 스키마 + 단기 메모리
    return create_agent(
        MODEL,
        tools=[list_my_devices],
        middleware=[helpdesk_prompt],
        context_schema=EmployeeContext,
        checkpointer=InMemorySaver(),
    )


# ───────────────────────── 자가 채점 ─────────────────────────
if __name__ == "__main__":
    agent = build_agent()
    admin = EmployeeContext(employee_id="E-100", department="재무팀", is_admin=True)
    staff = EmployeeContext(employee_id="E-200", department="마케팅팀")

    cfg_a = {"configurable": {"thread_id": "E-100:t1"}}
    agent.invoke({"messages": [{"role": "user", "content": "내 장비 목록 알려줘"}]}, cfg_a, context=admin)
    second = agent.invoke({"messages": [{"role": "user", "content": "노트북 초기화 방법은?"}]}, cfg_a, context=admin)

    tool_outputs = [m.content for m in second["messages"] if m.type == "tool"]
    humans = [m.content for m in second["messages"] if m.type == "human"]
    print("도구 결과:", tool_outputs)
    print("프롬프트 예:", PROMPTS_SEEN[-1] if PROMPTS_SEEN else None)

    assert any("E-100" in t for t in tool_outputs), "도구가 컨텍스트의 employee_id를 써야 합니다 (TODO ①)"
    assert any(ADMIN_NOTE in p and "재무팀" in p for p in PROMPTS_SEEN), "동적 프롬프트를 확인하세요 (TODO ②, ③)"
    assert "내 장비 목록 알려줘" in humans, "같은 thread에서는 이전 질문이 남아 있어야 합니다 (TODO ③ checkpointer)"

    PROMPTS_SEEN.clear()
    other = agent.invoke(
        {"messages": [{"role": "user", "content": "내 장비 목록 알려줘"}]},
        {"configurable": {"thread_id": "E-200:t1"}},
        context=staff,
    )
    other_humans = [m.content for m in other["messages"] if m.type == "human"]
    assert other_humans == ["내 장비 목록 알려줘"], "다른 thread는 격리되어야 합니다"
    assert all(ADMIN_NOTE not in p for p in PROMPTS_SEEN), "관리자가 아니면 ADMIN_NOTE가 없어야 합니다"
    assert any("E-200" in m.content for m in other["messages"] if m.type == "tool")

    print("✅ 모든 테스트 통과!")
