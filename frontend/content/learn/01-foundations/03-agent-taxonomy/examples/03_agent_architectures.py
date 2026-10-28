"""에이전트 아키텍처 비교: ReAct vs Plan-and-Execute vs ReWOO (LLM 호출 횟수 관점).

LLM 대신 '호출 횟수를 세는 가짜 두뇌'를 써서, 같은 과제(정보 3개 수집 후 답변)를
각 아키텍처가 몇 번의 LLM 호출로 처리하는지 비교한다. 순수 Python 이므로 결과가 결정적이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FACTS = {"수도": "서울", "인구": "약 5천만 명", "화폐": "원(KRW)"}


@dataclass
class CallCounter:
    """LLM 호출을 흉내 내며 횟수를 센다."""

    calls: int = 0
    log: list[str] = field(default_factory=list)

    def think(self, purpose: str) -> None:
        self.calls += 1
        self.log.append(purpose)


def search(key: str) -> str:
    """가짜 검색 도구."""
    return FACTS[key]


def react(brain: CallCounter, needs: list[str], max_steps: int = 10) -> dict[str, str]:
    """ReAct: 생각 → 행동 → 관찰을 한 단계씩. 매 도구 호출 전에 LLM 이 다음 행동을 결정한다."""
    known: dict[str, str] = {}
    for _ in range(max_steps):
        brain.think("다음 행동 결정")
        missing = [k for k in needs if k not in known]
        if not missing:
            break  # 이번 호출이 최종 답변 생성
        known[missing[0]] = search(missing[0])  # 관찰 결과가 다음 결정에 반영됨
    return known


def plan_and_execute(brain: CallCounter, needs: list[str]) -> dict[str, str]:
    """Plan-and-Execute: 계획을 먼저 세우고, 각 단계를 실행(실행기도 LLM일 수 있음), 필요하면 재계획."""
    brain.think("전체 계획 수립")
    known = {}
    for k in needs:
        brain.think(f"단계 실행: {k}")  # 실행기 LLM (더 작은 모델을 쓰는 경우가 많다)
        known[k] = search(k)
    brain.think("재계획/최종 답변")
    return known


def rewoo(brain: CallCounter, needs: list[str]) -> dict[str, str]:
    """ReWOO: 계획 단계에서 도구 호출을 변수(#E1, #E2..)로 미리 모두 적고, 도구만 돌린 뒤 한 번에 종합."""
    brain.think("도구 호출 계획 일괄 작성 (#E1..#En)")
    evidence = {k: search(k) for k in needs}  # LLM 호출 없이 도구만 실행
    brain.think("증거를 모아 최종 답변")
    return evidence


if __name__ == "__main__":
    needs = list(FACTS)
    print(f"과제: 한국의 {', '.join(needs)} 정보를 모아 답하기\n")
    print(f"{'아키텍처':<18} {'LLM 호출':>8}  호출 목적")
    print("-" * 78)
    for name, fn in [("ReAct", react), ("Plan-and-Execute", plan_and_execute), ("ReWOO", rewoo)]:
        brain = CallCounter()
        result = fn(brain, needs)
        assert result == FACTS
        print(f"{name:<18} {brain.calls:>8}  {' → '.join(brain.log)[:50]}")
    print("-" * 78)
    print("💡 ReAct: 매 단계 관찰을 보고 적응 (유연, 호출 많음)")
    print("💡 Plan-and-Execute: 큰 그림 먼저, 실행은 작은 모델로 (긴 작업에 유리)")
    print("💡 ReWOO: 관찰 없이 미리 계획 (호출 최소, 중간 결과에 따른 적응은 약함)")
