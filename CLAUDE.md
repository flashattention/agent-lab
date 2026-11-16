# CLAUDE.md

이 저장소에서 일하는 AI 코딩 에이전트(Claude Code 등)와 사람을 위한 작업 지침입니다.
일반 원칙은 [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)(MIT)를 요약해 옮겼고, 나머지는 이 저장소의 규칙입니다.

## 1. 일하는 방식

- **가정을 드러냅니다.** 요청이 두 가지로 읽히면 고르지 말고 묻습니다. 더 단순한 방법이 있으면 먼저 말합니다.
- **필요한 만큼만 만듭니다.** 요청하지 않은 기능, 한 번만 쓰는 추상화, 쓰지 않을 설정 옵션은 만들지 않습니다.
- **필요한 곳만 고칩니다.** 바뀐 줄은 모두 요청으로 설명할 수 있어야 합니다. 옆 코드를 "개선"하거나 포맷을 바꾸지 않습니다. 내 변경이 만든 미사용 import·변수는 지우고, 원래 있던 죽은 코드는 지우지 말고 알립니다.
- **검증 가능한 목표로 바꿉니다.** "버그 고치기"는 "재현 테스트를 쓰고 통과시키기"로 바꿉니다. 여러 단계 작업은 `단계 → 확인 방법` 목록으로 시작합니다.
- 단순한 수정(오타, 한 줄짜리)에는 판단껏 가볍게 적용합니다.

## 2. 저장소 지도

| 경로 | 내용 |
| --- | --- |
| `frontend/src/lib/playground/` | 그래프 모델(`types.ts`), 구조 분석기(`analyze.ts`), 코드 생성기(`codegen/`), 서브그래프(`subgraph.ts`), 패턴 |
| `frontend/src/components/playground/` | 캔버스, 툴바, 패널, 프리셋 |
| `frontend/src/lib/presets.ts`, `components/market/` | 에이전트 프리셋과 마켓 |
| `backend/app/` | 실행(`runner.py`), 키 프록시(`keyproxy.py`), 검증(`validate.py`), 고도화(`refine.py`), 보안 정책(`policy.py`) |
| `backend/sandbox/` | 샌드박스 안에서 자동 로드: Mock LLM, 트레이서, 보안 가드(`agentlab_guard.py`) |
| `supabase/` | 스키마와 RLS, `tests/` 의 권한 테스트 |
| `docs/` | ARCHITECTURE · DECISIONS · EVAL · PRODUCTION_READINESS |

프론트엔드는 Next.js 16 입니다. API 가 예전과 다르니 [`frontend/AGENTS.md`](frontend/AGENTS.md) 대로 `node_modules/next/dist/docs/` 를 먼저 확인합니다.

## 3. 완료 기준

CI(`.github/workflows/ci.yml`)가 아래를 모두 요구합니다. 끝났다고 말하기 전에 해당하는 것을 돌리고, 결과를 그대로 보고합니다.

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build   # lint 경고도 0 이어야 한다
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

바꾼 곳에 따라 더 필요한 것:

| 바꾼 곳 | 함께 할 일 |
| --- | --- |
| 코드 생성기 (`codegen/`) | 스냅샷 차이가 의도한 변경뿐인지 확인한 뒤 `npx vitest run -u`, 그리고 `npm run export:patterns`(백엔드 fixture). 출력이 바뀌면 `GENERATOR_VERSION` 을 `codegen/context.ts` 와 `backend/app/refine.py` 두 곳에서 같이 올린다 |
| 고도화 프롬프트 (`refine.py`) | `PROMPT_VERSION` 을 올리고 `scripts/eval_refine.py` 로 이전 프롬프트와 비교한다 (실제 모델, 비용 발생) |
| 기본 도구 (`catalog.ts` 의 `TOOL_LIBRARY`) | `supabase/schema.sql` 의 `agentlab_is_declarative` 목록도 고친다 (테스트가 어긋남을 잡는다) |
| 샌드박스·보안 정책 (`runner.py`, `agentlab_guard.py`, `policy.py`) | `uv run python scripts/check_content.py` (강의 코드 162개). CI 는 Linux 라서 macOS 에서만 되는 동작에 기대지 않는다 |
| DB 스키마 (`supabase/schema.sql`) | 두 번 실행해도 안전하게(멱등) 쓰고, 빈 Postgres 에서 `psql -f supabase/tests/stub.sql -f supabase/schema.sql -f supabase/schema.sql -f supabase/tests/rls_test.sql`. 배포된 DB 에는 사람이 직접 다시 실행해야 하므로 알린다 |
| 화면 | 브라우저에서 실제로 확인한다. 확인하지 못했으면 못 했다고 쓴다 |

## 4. 지켜야 할 불변 조건

- **샌드박스 코드에는 진짜 API 키를 넘기지 않습니다.** 키 프록시만 거칩니다.
- **샌드박스 네트워크는 키 프록시 주소만 엽니다.** 가드나 정책을 느슨하게 하는 변경에는 그것을 증명하는 테스트(`backend/tests/test_security.py`)가 함께 있어야 합니다.
- **공유 캐시에 들어가는 LLM 출력은 검증과 보안 정책을 모두 통과해야 하고, 자동 적용하지 않습니다.**
- **마켓에 공개되는 프리셋은 선언형만 허용합니다.** 이 조건은 화면이 아니라 DB 제약이 강제합니다.
- 테스트를 통과시키려고 단언을 약하게 만들지 않습니다(`|| true`, 범위 넓히기 등). 기대가 틀렸다면 그 이유를 적고 고칩니다.

## 5. 글쓰기

- 사용자에게 보이는 문구, 주석, 문서는 한국어로 씁니다. 기존 파일의 말투와 형식을 따릅니다.
- 문서에는 측정하지 않은 수치를 쓰지 않습니다. 아직 측정하지 않았으면 그렇다고 적고 측정 방법을 남깁니다.
