"""정책 기반 HITL 승인 + 코드 실행 샌드박스.

Part 1. 금액 기반 승인 정책
  - 5만 원 이하 환불은 자동 처리, 초과하면 interrupt() 로 사람 승인을 받는다.
  - 내장 HumanInTheLoopMiddleware 는 '도구 단위'로 항상 멈춘다.
    '인자 값에 따라' 멈추려면 wrap_tool_call 안에서 직접 interrupt() 를 호출한다.
  - 승인자는 approve / edit(금액 수정) / reject 중 하나를 고른다.

Part 2. LLM 이 만든 코드를 격리 실행
  - 별도 프로세스, 빈 환경변수(비밀키 없음), 임시 작업 폴더, 시간 제한.
  - 실무에서는 컨테이너/마이크로VM(gVisor, Firecracker) 기반 샌드박스를 쓴다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallRequest, wrap_tool_call
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
AUTO_APPROVE_LIMIT = 50_000  # 원


# ====================================================================== Part 1
@tool
def issue_refund(order_id: str, amount: int) -> str:
    """주문 order 에 대해 amount 원을 환불 refund 한다."""
    return f"{order_id} 에 {amount:,}원 환불 완료"


@wrap_tool_call
def refund_approval_policy(request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage | Command]):
    call = request.tool_call
    if call["name"] != "issue_refund" or call["args"].get("amount", 0) <= AUTO_APPROVE_LIMIT:
        return handler(request)  # 정책 범위 안: 자동 실행

    # 정책 초과: 그래프를 멈추고 사람에게 묻는다. 재개되면 resume 값이 여기로 돌아온다.
    decision = interrupt({
        "type": "refund_approval",
        "order_id": call["args"]["order_id"],
        "amount": call["args"]["amount"],
        "reason": f"자동 승인 한도({AUTO_APPROVE_LIMIT:,}원) 초과",
    })
    if decision["type"] == "reject":
        return ToolMessage(content=f"환불이 거절되었습니다: {decision.get('message', '')}",
                           tool_call_id=call["id"], name=call["name"], status="error")
    if decision["type"] == "edit":
        # 승인자가 금액을 고쳤다 → 고친 인자로 실행
        new_call = {**call, "args": {**call["args"], **decision["args"]}}
        return handler(request.override(tool_call=new_call))
    return handler(request)  # approve


agent = create_agent(
    MODEL,
    tools=[issue_refund],
    middleware=[refund_approval_policy],
    checkpointer=InMemorySaver(),
)


def ask(thread: str, text: str):
    cfg = {"configurable": {"thread_id": thread}}
    out = agent.invoke({"messages": [HumanMessage(text)]}, cfg, version="v2")
    return cfg, out


def last_tool_result(out) -> str:
    return [m for m in out.value["messages"] if isinstance(m, ToolMessage)][-1].content


print("=" * 70 + "\nPart 1-A) 3만 원 환불 → 자동 승인\n" + "=" * 70)
cfg, out = ask("r1", "30000원 refund 해줘 (주문 A-1)")
assert not out.interrupts
print("결과:", last_tool_result(out))

print("\n" + "=" * 70 + "\nPart 1-B) 12만 원 환불 → 승인 대기 → 금액 수정(edit) 후 승인\n" + "=" * 70)
cfg, out = ask("r2", "120000원 refund 해줘 (주문 B-7)")
assert out.interrupts, "한도 초과면 멈춰야 한다"
print("승인 요청:", out.interrupts[0].value)
out = agent.invoke(Command(resume={"type": "edit", "args": {"amount": 80_000}}), cfg, version="v2")
print("결과:", last_tool_result(out))
assert "80,000" in last_tool_result(out)

print("\n" + "=" * 70 + "\nPart 1-C) 50만 원 환불 → 거절(reject)\n" + "=" * 70)
cfg, out = ask("r3", "500000원 refund 해줘 (주문 C-3)")
out = agent.invoke(Command(resume={"type": "reject", "message": "증빙 부족"}), cfg, version="v2")
print("결과:", last_tool_result(out))


# ====================================================================== Part 2
def run_untrusted_code(code: str, timeout_s: float = 2.0) -> dict:
    """LLM 이 생성한 파이썬 코드를 격리된 프로세스에서 실행한다 (최소 예시).

    - python -I : 사용자 site-packages·PYTHON* 환경변수 무시 (격리 모드)
    - env={}    : API 키 같은 비밀값이 자식 프로세스로 새지 않음
    - cwd=임시폴더, timeout : 파일 오염·무한루프 방지
    ⚠️ 이것만으로는 네트워크·파일시스템 접근을 막지 못한다. 운영에서는 컨테이너 샌드박스가 필수.
    """
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=tmp, env={}, capture_output=True, text=True, timeout=timeout_s,
            )
            return {"ok": proc.returncode == 0, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()[-120:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": f"시간 초과({timeout_s}s) — 강제 종료"}


print("\n" + "=" * 70 + "\nPart 2) 코드 실행 샌드박스\n" + "=" * 70)
cases = {
    "정상 계산": "print(sum(range(101)))",
    "비밀키 탈취 시도": "import os; print('KEY=', os.environ.get('OPENAI_API_KEY'))",
    "무한 루프": "while True: pass",
}
for name, code in cases.items():
    r = run_untrusted_code(code)
    print(f"[{name:<10}] ok={r['ok']!s:<5} stdout={r['stdout']!r:<14} stderr={r['stderr']!r}")
assert run_untrusted_code(cases["비밀키 탈취 시도"])["stdout"] == "KEY= None"
