"""로컬 평가(eval) 하네스: 데이터셋 × 타깃 × 평가자 → 실험 리포트 → 회귀 게이트.

LangSmith 의 evaluate() 와 같은 구조를 네트워크 없이 직접 구현한다.
(LangSmith 버전 코드는 lesson.md 의 참고 코드블록을 보세요.)

  데이터셋(Dataset)   : 입력 + 기대값(reference) 묶음
  타깃(Target)        : 평가할 시스템 — 여기서는 create_agent 에이전트
  평가자(Evaluator)   : (outputs, reference) → {"key", "score", "comment"}
     - 코드 기반: 궤적 일치(trajectory match), 도구 호출 수 예산
     - LLM-as-judge: 구조화 출력으로 1~10 점수 + 근거
  실험(Experiment)    : 모든 예제 × 모든 평가자 결과표 + 집계
  회귀 게이트          : 기준선(baseline) 대비 떨어지면 배포 차단
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from statistics import mean
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage
from langchain.tools import tool
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
JUDGE_MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")  # 실무에서는 더 강한 모델을 judge 로 쓰기도 한다


# ======================================================================
# 1. 타깃 시스템
# ======================================================================
@tool
def lookup_order(order_id: str) -> str:
    """주문 order 의 배송 상태를 조회한다."""
    return f"{order_id}: 배송 중"


@tool
def search_policy(query: str) -> str:
    """환불·교환 policy 문서를 검색한다."""
    return "구매 후 30일 이내 환불 가능, 단순 변심은 왕복 배송비 고객 부담"


agent = create_agent(MODEL, tools=[lookup_order, search_policy], system_prompt="쇼핑몰 상담원")


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    """데이터셋 입력 → 에이전트 실행 → 평가에 필요한 출력만 추린다."""
    started = time.perf_counter()
    result = agent.invoke({"messages": [{"role": "user", "content": inputs["question"]}]})
    msgs = result["messages"]
    return {
        "answer": msgs[-1].content,
        "trajectory": [tc["name"] for m in msgs if isinstance(m, AIMessage) for tc in m.tool_calls],
        "latency_ms": (time.perf_counter() - started) * 1000,
    }


# ======================================================================
# 2. 데이터셋 — 실무에서는 운영 트레이스에서 실패 사례를 골라 계속 추가한다
# ======================================================================
DATASET: list[dict[str, Any]] = [
    {"id": "order-status", "inputs": {"question": "주문 A-1 order 배송 어디쯤인가요?"},
     "reference": {"trajectory": ["lookup_order"], "max_tool_calls": 1}},
    {"id": "refund-policy", "inputs": {"question": "환불 policy 가 어떻게 되나요?"},
     "reference": {"trajectory": ["search_policy"], "max_tool_calls": 1}},
    {"id": "mixed", "inputs": {"question": "order A-9 상태랑 교환 policy 둘 다 알려줘"},
     "reference": {"trajectory": ["lookup_order", "search_policy"], "max_tool_calls": 2}},
    {"id": "chitchat", "inputs": {"question": "안녕하세요, 좋은 아침이에요"},
     "reference": {"trajectory": [], "max_tool_calls": 0}},  # 인사에는 도구를 쓰면 안 된다
]


# ======================================================================
# 3. 평가자들
# ======================================================================
TrajectoryMode = Literal["strict", "unordered", "subset", "superset"]


def trajectory_match(actual: list[str], expected: list[str], mode: TrajectoryMode) -> bool:
    """agentevals 의 trajectory match 모드와 같은 의미.

    strict    : 순서와 개수까지 완전히 같아야 함
    unordered : 순서는 무관, 같은 도구 multiset
    subset    : 실제 호출 ⊆ 기대 (기대 밖의 도구를 쓰면 안 됨)
    superset  : 실제 호출 ⊇ 기대 (필수 도구는 반드시 호출)
    """
    if mode == "strict":
        return actual == expected
    if mode == "unordered":
        return sorted(actual) == sorted(expected)
    if mode == "subset":
        return set(actual) <= set(expected)
    if mode == "superset":
        return set(actual) >= set(expected)
    raise ValueError(mode)


def eval_trajectory(outputs: dict, reference: dict) -> dict:
    ok = trajectory_match(outputs["trajectory"], reference["trajectory"], "unordered")
    return {"key": "trajectory_unordered", "score": float(ok),
            "comment": f"actual={outputs['trajectory']} expected={reference['trajectory']}"}


def eval_tool_budget(outputs: dict, reference: dict) -> dict:
    n = len(outputs["trajectory"])
    return {"key": "tool_budget", "score": float(n <= reference["max_tool_calls"]), "comment": f"{n} calls"}


class Grade(BaseModel):
    """LLM 심판의 채점 결과. 근거를 먼저 쓰게 하면 점수가 더 일관된다."""

    reasoning: str = Field(description="채점 근거를 먼저 서술")
    score: int = Field(ge=1, le=10, description="1(매우 나쁨)~10(완벽)")


JUDGE_PROMPT = """너는 고객지원 답변 품질 심사위원이다. 아래 기준으로 1~10점을 매겨라.
- 정확성: 도구 결과와 모순되지 않는가
- 완결성: 질문의 모든 요소에 답했는가
- 어조: 공손하고 간결한가
[질문]
{question}
[답변]
{answer}"""

judge_llm = init_chat_model(JUDGE_MODEL).with_structured_output(Grade)


def eval_llm_judge(outputs: dict, reference: dict, inputs: dict) -> dict:
    grade: Grade = judge_llm.invoke(JUDGE_PROMPT.format(question=inputs["question"], answer=outputs["answer"]))
    return {"key": "judge_quality", "score": grade.score / 10, "comment": grade.reasoning[:40]}


EVALUATORS: list[Callable[..., dict]] = [eval_trajectory, eval_tool_budget, eval_llm_judge]


# ======================================================================
# 4. 실험 실행 + 리포트
# ======================================================================
def run_experiment(name: str) -> dict[str, float]:
    print("=" * 78 + f"\n실험: {name}  (예제 {len(DATASET)}개 × 평가자 {len(EVALUATORS)}개)\n" + "=" * 78)
    print(f"{'example':<14}{'trajectory':>12}{'budget':>9}{'judge':>8}{'latency':>10}  comment")
    rows: list[dict[str, float]] = []
    for ex in DATASET:
        outputs = target(ex["inputs"])
        scores: dict[str, float] = {}
        comment = ""
        for ev in EVALUATORS:
            kwargs = {"inputs": ex["inputs"]} if ev is eval_llm_judge else {}
            r = ev(outputs, ex["reference"], **kwargs)
            scores[r["key"]] = r["score"]
            if r["key"] == "trajectory_unordered" and not r["score"]:
                comment = r["comment"]
        rows.append(scores)
        print(f"{ex['id']:<14}{scores['trajectory_unordered']:>12.0f}{scores['tool_budget']:>9.0f}"
              f"{scores['judge_quality']:>8.1f}{outputs['latency_ms']:>8.0f}ms  {comment}")
    summary = {k: mean(r[k] for r in rows) for k in rows[0]}
    print("-" * 78)
    print("평균:", {k: round(v, 2) for k, v in summary.items()})
    return summary


# 기준선: 지난 릴리스의 점수. 실무에서는 파일/LangSmith 실험에 저장해 두고 비교한다.
BASELINE = {"trajectory_unordered": 0.75, "tool_budget": 0.75, "judge_quality": 0.7}
TOLERANCE = 0.05  # LLM 비결정성을 감안한 허용 오차


def regression_gate(current: dict[str, float]) -> bool:
    print("\n회귀 게이트 (baseline - tolerance 이상이어야 통과)")
    ok = True
    for key, base in BASELINE.items():
        passed = current[key] >= base - TOLERANCE
        ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'}  {key:<22} current={current[key]:.2f} baseline={base:.2f}")
    return ok


summary = run_experiment("support-agent@candidate")
gate_ok = regression_gate(summary)
print("\n결론:", "배포 가능 ✅" if gate_ok else "배포 차단 ⛔ (CI 에서는 sys.exit(1))")
