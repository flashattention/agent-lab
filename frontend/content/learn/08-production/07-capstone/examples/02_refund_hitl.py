"""캡스톤 2: 환불 승인 정책 + Human-in-the-loop 운영 흐름.

Part 1. 정책 함수 decide_refund 의 판정표 (순수 함수 → 결정적)
Part 2. 그래프 실행 → interrupt 로 멈춤 → '상담원 콘솔'이 대기 건을 조회 → 결정 → 재개
        - 승인자 A: 금액·주문번호를 고쳐서 승인 (edit)
        - 승인자 B: 거절 (reject) → 에이전트가 고객에게 사유를 안내
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from support_desk import SupportContext, build_support_graph
from support_desk.policies import decide_refund

# ====================================================================== Part 1
print("=" * 72 + "\nPart 1) 환불 정책 판정표\n" + "=" * 72)
CASES = [
    ("A-1001", 50_000, "u-kim", "VIP", "본인·기간 내·VIP 한도 이내"),
    ("A-1001", 89_000, "u-kim", "STANDARD", "일반 등급 한도 초과"),
    ("A-1002", 12_000, "u-kim", "VIP", "아직 배송 중"),
    ("B-2001", 20_000, "u-lee", "STANDARD", "수령 후 10일 (기간 초과)"),
    ("B-2001", 20_000, "u-kim", "VIP", "타인 주문"),
]
for order_id, amount, user, tier, note in CASES:
    decision, why = decide_refund(order_id, amount, user, tier)
    print(f"{order_id} {amount:>7,}원 {user:<6} {tier:<8} → {decision:<6} | {why}   ({note})")
assert decide_refund("A-1001", 50_000, "u-kim", "VIP")[0] == "auto"

# ====================================================================== Part 2
graph = build_support_graph(checkpointer=InMemorySaver(), store=InMemoryStore())


def ask(thread: str, user: str, tier: str, text: str):
    ctx = SupportContext(user_id=user, tier=tier)
    cfg = {"configurable": {"thread_id": f"{user}:{thread}"}}
    out = graph.invoke({"messages": [{"role": "user", "content": text}]}, cfg, context=ctx, version="v2")
    return ctx, cfg, out


def agent_console(cfg: dict) -> list[dict]:
    """상담원 콘솔: 이 스레드에서 사람 결정을 기다리는 요청 목록 (체크포인트에서 조회)."""
    snap = graph.get_state(cfg, subgraphs=True)
    return [i.value for i in snap.interrupts]


def last_tool_text(out) -> str:
    tool_msgs = [m for m in out.value["messages"] if m.type == "tool"]
    return str(tool_msgs[-1].content) if tool_msgs else "(도구 실행 없음)"


print("\n" + "=" * 72 + "\nPart 2-A) VIP 고객의 큰 금액 환불 → 검토 → 금액 조정 후 승인(edit)\n" + "=" * 72)
ctx, cfg, out = ask("refund-1", "u-kim", "VIP", "헤드폰 A-1001 불량이라 refund 해주세요. 150000원 요청합니다")
if out.interrupts:
    pending = agent_console(cfg)
    print("대기 중인 검토 건:", pending[0]["reason"], "| 요청:", pending[0]["request"])
    # 상담원이 결제 금액(89,000원) 전액, 올바른 주문번호로 고쳐서 승인
    decision = {"type": "edit", "args": {"order_id": "A-1001", "amount": 89_000, "reason": "불량"}}
    out = graph.invoke(Command(resume=decision), cfg, context=ctx, version="v2")
print("도구 결과:", last_tool_text(out))
print("고객 안내:", str(out.value["messages"][-1].content)[:90])
assert not agent_console(cfg), "검토가 끝났으면 대기 건이 없어야 한다"

print("\n" + "=" * 72 + "\nPart 2-B) 기간이 지난 주문 환불 → 검토 → 거절(reject)\n" + "=" * 72)
ctx, cfg, out = ask("refund-2", "u-lee", "STANDARD", "B-2001 모니터 암 refund 원해요 45000원")
if out.interrupts:
    print("대기 중인 검토 건:", agent_console(cfg)[0]["reason"])
    out = graph.invoke(Command(resume={"type": "reject", "message": "수령 후 7일 경과"}), cfg,
                       context=ctx, version="v2")
print("도구 결과:", last_tool_text(out)[:80])
print("최종 route:", out.value["route"])
