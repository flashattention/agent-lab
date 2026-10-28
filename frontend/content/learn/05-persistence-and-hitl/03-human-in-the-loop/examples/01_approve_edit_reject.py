"""예제 1: interrupt()로 이메일 발송 전 사람의 승인 받기 (승인 / 편집 / 거절).

흐름: draft(LLM 초안) → review(interrupt로 멈춤) → send 또는 cancel
사람의 입력은 스크립트 안에서 Command(resume=...)로 흉내 냅니다(실제 서비스에서는 승인 UI의 버튼).
"""

import os
from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)

SENT_EMAILS: list[dict] = []  # '실제로' 발송된 메일 (부수효과 기록용)


class EmailState(TypedDict, total=False):
    request: str
    to: str
    draft: str
    status: str
    reject_reason: str


def draft(state: EmailState) -> dict:
    """LLM으로 메일 초안을 작성한다."""
    reply = llm.invoke(f"다음 요청으로 짧은 업무 메일 본문을 써 줘: {state['request']}")
    return {"draft": reply.content[:120]}


def review(state: EmailState) -> Command[Literal["send", "cancel"]]:
    """사람에게 초안을 보여 주고 결정을 기다린다."""
    # 재개하면 이 노드가 '처음부터' 다시 실행되므로 이 줄은 두 번 출력된다.
    print(f"    (review 노드 실행: to={state['to']})")
    decision = interrupt(
        {
            "message": "이 메일을 보낼까요?",
            "to": state["to"],
            "draft": state["draft"],
            "allowed": ["approve", "edit", "reject"],
        }
    )
    # ↓ 여기부터는 재개 후에만 실행된다. decision = Command(resume=...)로 보낸 값
    if decision["action"] == "approve":
        return Command(goto="send")
    if decision["action"] == "edit":
        return Command(update={"to": decision.get("to", state["to"]), "draft": decision["draft"]}, goto="send")
    return Command(update={"reject_reason": decision.get("reason", "")}, goto="cancel")


def send(state: EmailState) -> dict:
    """부수효과(발송)는 interrupt '뒤'의 별도 노드에 둔다."""
    SENT_EMAILS.append({"to": state["to"], "body": state["draft"]})
    return {"status": "sent"}


def cancel(state: EmailState) -> dict:
    return {"status": f"cancelled ({state.get('reject_reason', '')})"}


builder = StateGraph(EmailState)
builder.add_node("draft", draft)
builder.add_node("review", review)
builder.add_node("send", send)
builder.add_node("cancel", cancel)
builder.add_edge(START, "draft")
builder.add_edge("draft", "review")
builder.add_edge("send", END)
builder.add_edge("cancel", END)
graph = builder.compile(checkpointer=InMemorySaver())  # interrupt에는 체크포인터 필수


def run_with_human(thread_id: str, human_decision: dict) -> dict:
    """그래프를 실행하고, 멈추면 사람의 결정(human_decision)으로 재개한다."""
    config = {"configurable": {"thread_id": thread_id}}
    print(f"\n[{thread_id}] 1) 실행 시작")
    out = graph.invoke({"request": "회의 일정 변경 안내", "to": "team@example.com"}, config, version="v2")

    # 멈춘 상태 확인
    assert out.interrupts, "review에서 멈춰야 한다"
    request = out.interrupts[0].value
    print(f"[{thread_id}] 2) 멈춤! next={graph.get_state(config).next}")
    print(f"    승인 요청: {request['message']} to={request['to']}")
    print(f"    초안: {request['draft'][:50]}...")

    # ---- 여기서 시간이 얼마든 흘러도 된다. 상태는 체크포인터에 저장되어 있다 ----
    print(f"[{thread_id}] 3) 사람의 결정으로 재개: {human_decision}")
    final = graph.invoke(Command(resume=human_decision), config, version="v2")
    print(f"[{thread_id}] 4) 결과: status={final.value['status']}, to={final.value['to']}")
    return final.value


print("=" * 64)
r1 = run_with_human("mail-approve", {"action": "approve"})
r2 = run_with_human(
    "mail-edit",
    {"action": "edit", "to": "leaders@example.com", "draft": "회의가 목요일 3시로 변경되었습니다."},
)
r3 = run_with_human("mail-reject", {"action": "reject", "reason": "이미 공지됨"})

print("\n" + "=" * 64)
print("실제로 발송된 메일:")
for m in SENT_EMAILS:
    print("  -", m["to"], "|", m["body"][:40])

assert r1["status"] == "sent" and r2["status"] == "sent"
assert r2["to"] == "leaders@example.com", "편집된 수신자로 발송되어야 한다"
assert r3["status"].startswith("cancelled")
assert len(SENT_EMAILS) == 2, "거절된 메일은 발송되지 않는다"
print("\n✔ 승인/편집/거절 세 가지 흐름이 모두 동작했습니다.")
