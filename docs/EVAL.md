# 평가 (Eval)

AgentLab의 핵심 주장 세 가지를 수치로 확인합니다.

1. **생성된 코드는 실행된다.** 그래프에서 만든 LangGraph 프로젝트가 수정 없이 끝까지 돈다.
2. **구조 분석기는 실행 전에 결함을 잡는다.** 그리고 정상적인 변경을 오류로 막지 않는다.
3. **분석기가 없으면 결함이 어떻게 드러나는가.** 실행해 보면 예외, 무한 루프, 또는 아무 증상 없이 지나간다.

모든 결과는 아래 명령으로 다시 만들 수 있고, 원본 데이터는 [`docs/eval/`](eval/)에 있습니다.

> 측정 환경: Mock LLM(결정적 모의 모델, API 키 불필요), WSL2 Linux, 샌드박스 기본 제한. 실행 시간에는 Python과 LangChain을 불러오는 시간(약 2초)이 대부분입니다.

## 1. 패턴 실행 (12종 × 3회)

**성공률 100%** (36/36회). 실행·노드·LLM·도구 수는 실행 트레이스에서 셉니다.

| 패턴 | 분류 | 성공 | p50 (ms) | 실행된 노드 | LLM 호출 | 도구 호출 | 트레이스 이벤트 |
|---|---|---|---|---|---|---|---|
| ReAct Agent (직접 구성) (`react-agent`) | 기초 | 3/3 | 2,114 | 3 | 2 | 1 | 18 |
| create_agent 한 줄 에이전트 (`prebuilt-agent`) | 기초 | 3/3 | 2,179 | 5 | 2 | 1 | 18 |
| Prompt Chaining (`prompt-chaining`) | 워크플로 | 3/3 | 2,099 | 4 | 3 | 0 | 16 |
| Routing (의도 분류) (`router`) | 워크플로 | 3/3 | 2,135 | 5 | 3 | 1 | 20 |
| Parallelization (Sectioning) (`parallel`) | 워크플로 | 3/3 | 2,053 | 4 | 4 | 0 | 18 |
| Map-Reduce (Send API) (`map-reduce`) | 멀티 에이전트 | 3/3 | 2,051 | 3 | 3 | 0 | 16 |
| Reflection / Evaluator-Optimizer (`reflection`) | 워크플로 | 3/3 | 2,036 | 2 | 2 | 0 | 16 |
| Plan-and-Execute (`plan-execute`) | 멀티 에이전트 | 3/3 | 2,178 | 8 | 5 | 1 | 36 |
| Supervisor 멀티 에이전트 (`supervisor`) | 멀티 에이전트 | 3/3 | 2,180 | 15 | 9 | 2 | 70 |
| Agentic RAG (Corrective) (`agentic-rag`) | RAG | 3/3 | 2,271 | 3 | 2 | 0 | 20 |
| Human-in-the-loop 승인 (`hitl`) | 프로덕션 | 3/3 | 2,204 | 12 | 4 | 2 | 42 |
| 고객지원 시스템 (종합) (`support-system`) | 프로덕션 | 3/3 | 2,404 | 3 | 3 | 0 | 22 |

- 노드 수에는 서브그래프 안쪽 노드도 포함됩니다. 예를 들어 Supervisor 패턴은 워커가 `create_agent` 서브그래프라서 15개입니다.
- 같은 패턴 12종은 CI(`backend/tests/test_patterns.py`)에서 push할 때마다 다시 실행됩니다.

```bash
cd frontend && npm run export:patterns                     # 생성 코드 fixture 갱신
cd backend && uv run python scripts/eval_patterns.py --runs 3 --json ../docs/eval/patterns-mock.json
```

## 2. 구조 분석기: 결함 주입 실험

정상 패턴 12종에 결함 10종과 정상 변경 4종을 하나씩 주입하고, 분석기가 오류를 내는지 봅니다. 패턴 구조상 적용할 수 없는 경우(예: Tools 노드가 없는 패턴의 "도구 제거")는 제외했습니다.

| | 결과 |
|---|---|
| **검출률 (결함 → 오류)** | **97/97 (100%)** |
| **오탐 (정상 변경 → 오류)** | **0/48** |

| 주입한 변경 | 종류 | 맞게 판정 |
|---|---|---|
| END 로 가는 엣지를 모두 끊음 (출구 없음) | 결함 | 12/12 |
| 노드가 자기 자신으로 무조건 돌아감 (무한 루프) | 결함 | 12/12 |
| 노드 이름을 잘못된 Python 식별자로 (코드 주입·문법 오류) | 결함 | 12/12 |
| 두 노드 이름이 중복 | 결함 | 11/11 |
| START 에서 나가는 엣지 제거 (도달 불가) | 결함 | 12/12 |
| START 노드 삭제 | 결함 | 12/12 |
| Tools 노드의 도구를 모두 제거 | 결함 | 1/1 |
| END 에서 나가는 엣지 추가 | 결함 | 12/12 |
| 어디에도 연결되지 않은 노드 추가 | 결함 | 12/12 |
| Human 노드가 있는데 Checkpointer 끔 | 결함 | 1/1 |
| 노드 위치 이동 | 정상 변경 | 12/12 |
| 노드 이름을 다른 올바른 이름으로 | 정상 변경 | 12/12 |
| 프롬프트에 따옴표·줄바꿈 추가 | 정상 변경 | 12/12 |
| 데모 입력 변경 | 정상 변경 | 12/12 |

**해석과 한계:** 결함 종류는 분석기가 다루는 규칙과 같은 범주에서 골랐습니다. 그래서 100%는 "알려진 결함 범주를 빠짐없이 처리한다"는 뜻이지, 모든 논리 오류를 잡는다는 뜻은 아닙니다. 예를 들어 프롬프트가 잘못 쓰인 경우처럼 의미 수준의 오류는 이 실험의 범위 밖입니다.

```bash
cd frontend && npx vite-node scripts/eval-analyzer.ts ../docs/eval/analyzer.json /tmp/defects.json
```

## 3. 분석기가 막지 않았다면

2번에서 만든 결함 그래프 97건의 코드를 그대로 생성해 샌드박스에서 실행했습니다.

| 결과 | 건수 | 비율 |
|---|---|---|
| 예외로 종료 (crash) | 55 | 57% |
| 무한 루프 / 시간 초과 (hang) | 11 | 11% |
| **오류 없이 지나감 (silent)** | **31** | **32%** |

| 결함 | crash | hang | silent |
|---|---|---|---|
| END 로 가는 엣지를 모두 끊음 (출구 없음) | 4 | 0 | 8 |
| 노드가 자기 자신으로 무조건 돌아감 (무한 루프) | 0 | 11 | 1 |
| 노드 이름을 잘못된 Python 식별자로 (코드 주입·문법 오류) | 12 | 0 | 0 |
| 두 노드 이름이 중복 | 11 | 0 | 0 |
| START 에서 나가는 엣지 제거 (도달 불가) | 12 | 0 | 0 |
| START 노드 삭제 | 12 | 0 | 0 |
| Tools 노드의 도구를 모두 제거 | 1 | 0 | 0 |
| END 에서 나가는 엣지 추가 | 0 | 0 | 12 |
| 어디에도 연결되지 않은 노드 추가 | 2 | 0 | 10 |
| Human 노드가 있는데 Checkpointer 끔 | 1 | 0 | 0 |

- **hang**: 무한 루프는 LangGraph의 `recursion_limit`이나 실행 시간 상한에 걸릴 때까지 LLM을 반복 호출합니다. 실제 모델이었다면 그만큼 비용이 듭니다.
- **silent**: 결함이 겉으로 드러나지 않는 경우입니다. 예를 들어 END에서 나가는 엣지는 생성 코드에서 빠지고, 연결되지 않은 노드는 등록만 되고 실행되지 않습니다. END로 가는 길이 끊긴 그래프도 마지막 노드에서 그냥 멈춥니다. 사용자가 그린 의도와 실제 동작이 다른데 아무 신호가 없습니다. 이런 결함은 실행해 봐도, 테스트를 돌려도 발견하기 어렵습니다. 실행 전 정적 분석이 필요한 이유입니다.

```bash
cd backend && uv run python scripts/eval_defects.py /tmp/defects.json --json ../docs/eval/defects-runtime.json
```

## 4. 실제 모델 (gpt-5-mini, 패턴 12종 × 1회)

**10/12 성공.** 실패 2건은 코드 오류가 아니라 **샌드박스 실행 상한(90초) 초과**입니다. 두 패턴 모두 중단될 때까지 노드가 정상적으로 진행 중이었습니다(Plan-Execute 노드 17개, Supervisor 노드 24개).

| 패턴 | 결과 | 시간 (초) | 실행된 노드 | LLM 호출 | 도구 호출 | 토큰 |
|---|---|---|---|---|---|---|
| ReAct Agent (직접 구성) (`react-agent`) | ✅ | 23.9 | 3 | 2 | 2 | 2,348 |
| create_agent 한 줄 에이전트 (`prebuilt-agent`) | ✅ | 15.8 | 5 | 2 | 1 | 1,542 |
| Prompt Chaining (`prompt-chaining`) | ✅ | 28.3 | 4 | 3 | 0 | 3,525 |
| Routing (의도 분류) (`router`) | ✅ | 13.7 | 5 | 3 | 1 | 1,265 |
| Parallelization (Sectioning) (`parallel`) | ✅ | 45.4 | 4 | 4 | 0 | 8,242 |
| Map-Reduce (Send API) (`map-reduce`) | ✅ | 49.8 | 6 | 6 | 0 | 9,049 |
| Reflection / Evaluator-Optimizer (`reflection`) | ✅ | 22.9 | 2 | 2 | 0 | 3,299 |
| Plan-and-Execute (`plan-execute`) | ⏱ 90초 초과 | 90.0 | 17 | 6 | 7 | 15,465 |
| Supervisor 멀티 에이전트 (`supervisor`) | ⏱ 90초 초과 | 90.0 | 24 | 11 | 7 | 19,934 |
| Agentic RAG (Corrective) (`agentic-rag`) | ✅ | 63.0 | 7 | 5 | 0 | 7,291 |
| Human-in-the-loop 승인 (`hitl`) | ✅ | 26.1 | 13 | 4 | 3 | 4,991 |
| 고객지원 시스템 (종합) (`support-system`) | ✅ | 52.9 | 5 | 5 | 0 | 6,404 |

전체 토큰은 83,355개입니다. 패턴별 실행 시간의 중앙값은 36.8초로, Mock(약 2초)과 달리 대부분 모델 응답 대기 시간입니다.

**발견한 것**
- **지연 시간이 주된 제약입니다.** 직렬 LLM 호출이 많은 멀티 에이전트 패턴(Plan-Execute, Supervisor)은 실제 모델에서 90초를 넘깁니다. 구조 분석기는 이미 "LLM 호출이 최소 N번 직렬로 일어납니다"라는 경고를 내지만, 실행 상한과 연결된 예상 시간은 보여 주지 않습니다.
- **Mock과 실제 모델의 경로는 다릅니다.** 같은 ReAct 패턴에서 실제 모델은 도구를 2번 호출했고(Mock은 1번), Map-Reduce는 분기 수가 달랐습니다. Mock eval은 "흐름이 끝까지 도는가"를 보는 것이고, 실제 동작은 이 측정으로 보완합니다.
- **다음 개선 후보:** 직렬 LLM 호출 수로 예상 실행 시간을 계산해 분석기 경고에 표시하기, 단계가 많은 그래프에 더 긴 실행 상한 허용하기.

```bash
OPENAI_API_KEY=sk-... uv run python scripts/eval_patterns.py --live --runs 1 --json ../docs/eval/patterns-live.json
AGENTLAB_MAX_TIMEOUT=180 OPENAI_API_KEY=sk-... uv run python scripts/eval_patterns.py --live --runs 1 --timeout 180   # 상한을 늘려 재측정
```
