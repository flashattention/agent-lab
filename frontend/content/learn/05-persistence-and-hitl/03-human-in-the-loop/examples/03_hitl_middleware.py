"""예제 3: create_agent + HumanInTheLoopMiddleware로 도구 실행 전 승인 받기.

- interrupt_on: 도구별 승인 정책 (True / False / {"allowed_decisions": [...]})
- interrupt_mode="batched"(기본): 한 턴의 모든 승인 요청을 interrupt 하나로 모아 보냄
- interrupt_mode="per_call": 도구 호출마다 interrupt 하나, id로 각각 답함
"""

import os

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
EXECUTED: list[str] = []  # 실제로 실행된 도구 기록


@tool
def send_email(to: str, subject: str) -> str:
    """Send an email to a recipient with a subject."""
    EXECUTED.append(f"send_email(to={to})")
    return f"메일 발송 완료: {to} / {subject}"


@tool
def delete_file(path: str) -> str:
    """Delete a file at the given path."""
    EXECUTED.append(f"delete_file({path})")
    return f"삭제 완료: {path}"


def build_agent(mode: str):
    return create_agent(
        MODEL,
        tools=[send_email, delete_file],
        system_prompt="너는 사내 업무 비서다. 필요한 도구를 호출하라.",
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "send_email": True,  # approve / edit / reject / respond 모두 허용
                    "delete_file": {
                        "allowed_decisions": ["approve", "reject"],  # 삭제는 편집 불가
                        "description": "⚠️ 파일 삭제는 되돌릴 수 없습니다. 신중히 승인하세요.",
                    },
                },
                interrupt_mode=mode,
            )
        ],
        checkpointer=InMemorySaver(),  # interrupt를 쓰므로 필수
    )


USER_MSG = {"role": "user", "content": "send email to the team, then delete file old_report.txt"}

# ---------------------------------------------------------------------------
print("=" * 64)
print('A) interrupt_mode="batched"')
print("=" * 64)
agent = build_agent("batched")
cfg = {"configurable": {"thread_id": "ops-1"}}
out = agent.invoke({"messages": [USER_MSG]}, cfg, version="v2")

hitl_request = out.interrupts[0].value  # HITLRequest
print(f"interrupt 수: {len(out.interrupts)} (batched는 한 턴에 하나)")
decisions = []
for action, review in zip(hitl_request["action_requests"], hitl_request["review_configs"]):
    print(f"  - {action['name']} {action['args']}  허용: {review['allowed_decisions']}")
    # 사람의 결정을 흉내 낸다: 메일은 수신자를 고쳐서 승인, 삭제는 거절
    if action["name"] == "send_email":
        edited_args = {**action["args"], "to": "team@example.com"}
        decisions.append({"type": "edit", "edited_action": {"name": "send_email", "args": edited_args}})
    else:
        decisions.append({"type": "reject", "message": "보관 정책상 삭제 금지"})

out = agent.invoke(Command(resume={"decisions": decisions}), cfg, version="v2")
for m in out.value["messages"]:
    if m.type == "tool":
        last_line = m.content.strip().splitlines()[-1]  # edit 결과에는 앞에 안내문이 붙는다
        print(f"  [ToolMessage:{m.name}] {last_line[:70]}")
print("실행된 도구:", EXECUTED)
assert EXECUTED == ["send_email(to=team@example.com)"], "삭제는 거절되어 실행되지 않아야 한다"

# ---------------------------------------------------------------------------
print("\n" + "=" * 64)
print('B) interrupt_mode="per_call"')
print("=" * 64)
EXECUTED.clear()
agent = build_agent("per_call")
cfg = {"configurable": {"thread_id": "ops-2"}}
out = agent.invoke({"messages": [USER_MSG]}, cfg, version="v2")
print(f"interrupt 수: {len(out.interrupts)} (도구 호출마다 하나)")

answers = {}
for intr in out.interrupts:
    req = intr.value  # ToolApprovalRequest: type/tool_call_id/name/args/description
    print(f"  - [{req['type']}] {req['name']}  schema 제공: {intr.response_schema is not None}")
    if req["name"] == "send_email":
        answers[intr.id] = {"type": "approve"}
    else:
        # delete_file은 approve/reject만 허용된다. per_call 모드에서는 response_schema로
        # 허용되지 않은 결정(예: edit, respond)을 보내면 저장 전에 검증 에러가 난다.
        answers[intr.id] = {"type": "reject", "message": "삭제 대신 아카이브하세요"}

out = agent.invoke(Command(resume=answers), cfg, version="v2")
print("최종 답변:", out.value["messages"][-1].content[:80])
print("실행된 도구:", EXECUTED)
assert len(EXECUTED) == 1 and EXECUTED[0].startswith("send_email")
assert not out.interrupts
print("\n✔ batched / per_call 두 모드 모두 동작했습니다.")
