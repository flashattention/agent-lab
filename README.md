# AgentLab

AI 에이전트를 그려서 설계하는 작업 공간이자 학습 플랫폼입니다. 그래프를 그리면 실행되는 LangGraph 코드가 만들어지고, Google 로그인으로 프로젝트를 저장하고 링크로 공유합니다. LangChain 1.4와 LangGraph 1.2를 기준으로 합니다.

| 공간 | 내용 |
| --- | --- |
| **학습** `/learn` | 8개 모듈, 40여 개 강의로 구성됩니다. 왼쪽에는 이론, 오른쪽에는 Monaco IDE가 있어 코드를 실행하고, traceback을 클릭해 오류 위치로 이동하며, 자동 채점 과제를 풀 수 있습니다. 강의마다 퀴즈가 있습니다. |
| **플레이그라운드** `/playground` | 노드를 드래그해 연결하면 LangGraph 프로젝트(파일 트리)가 실시간으로 생성됩니다. 구조 분석으로 오류는 빨강, 병목과 위험은 노랑으로 표시합니다. 패턴 13종을 제공하고, 실행, 검증, LLM 고도화와 결과 캐싱, ZIP 다운로드를 지원합니다. **Sub-agent** 노드를 더블클릭해 내부 그래프를 편집하고(중첩 가능), 만든 에이전트를 **프리셋**으로 저장해 다른 그래프에서 Sub-agent 로 불러옵니다. 노드별 모델, 커스텀 도구, 복사/붙여넣기, ⌘K 노드 검색, `agentlab.json` 가져오기/내보내기를 지원합니다. |
| **내 프로젝트** `/projects` | Google 로그인 후 프로젝트를 여러 개 만들고 자동 저장합니다. 공유 링크(`/playground?p=<id>`)를 받은 사람은 보기 전용으로 열고, 자기 작업 공간에 복제해 편집합니다. |
| **Docs** `/docs` | LangChain, LangGraph, Vector DB, 통합 도구의 한국어 API 레퍼런스입니다. ⌘K로 검색할 수 있습니다. |

## 구조

```
frontend/   Next.js 16 (App Router) · Tailwind 4 · React Flow · Monaco
  content/learn/<module>/<lesson>/   강의 (lesson.md, examples/, exercise.py, solution.py, quiz.json)
  content/docs/<category>/*.md       레퍼런스 문서
  src/lib/playground/                그래프 모델 · 구조 분석기 · 코드 생성기 · 패턴
  src/lib/playground/subgraph.ts     서브그래프 순회 · 묶기/펼치기
  src/lib/{supabase,auth,projects,presets}.ts  로그인 · 프로젝트 저장/공유 · 에이전트 프리셋
supabase/schema.sql                  projects · agent_presets 테이블과 행 단위 보안 정책
docs/PRODUCTION_READINESS.md         현업 사용을 위한 기능 · 보안 점검과 후속 과제
backend/    FastAPI · uv · Python 3.13
  app/auth.py        로그인 확인(Supabase) · 사용자별 하루 한도
  app/runner.py      격리된 subprocess 실행 (타임아웃, rlimit, 출력 상한, 동시성 제한)
  app/validate.py    ruff 정적 검사와 Mock 모드 실제 실행 검증
  app/policy.py      고도화 코드 보안 정책 (AST 허용 목록) — 통과해야 공유 캐시에 저장
  app/refine.py      고성능 LLM 고도화 → 검증 통과 시 그래프 구조 해시로 SQLite 캐시
  sandbox/agentlab_guard.py  샌드박스 보안 정책 (audit hook: 네트워크 허용 목록, 외부 프로그램 실행 차단)
  sandbox/           API Key가 없을 때 쓰는 Mock LLM (tool calling, 구조화 출력, 스트리밍 모사)
  scripts/check_content.py   모든 강의 코드를 실제로 실행해 검증
```

## 로컬 개발

```bash
# 1) 백엔드 (http://localhost:8000)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 2) 프론트엔드 (http://localhost:3000)
cd frontend
npm install
npm run dev            # 백엔드 주소를 바꾸려면 NEXT_PUBLIC_API_URL 환경변수를 지정합니다.
```

### 로그인과 프로젝트 저장 (선택)

`frontend/.env.example`을 `.env.local`로 복사해 Supabase 값을 채우고, 백엔드에는 `SUPABASE_URL`, `SUPABASE_ANON_KEY` 환경변수를 줍니다. 설정 방법은 [DEPLOY.md](DEPLOY.md)의 0-1 단계에 있습니다.

- 값이 없으면 로그인 없이 동작합니다. 캔버스는 브라우저에만 저장되고, 코드 실행에 제한이 없습니다.
- 값이 있으면 코드 실행·검증·고도화는 로그인한 사용자만 쓸 수 있고, 사용자별 하루 한도가 적용됩니다(`backend/app/auth.py`).
- 프로젝트 데이터는 브라우저가 Supabase에 직접 읽고 씁니다. 접근 권한은 `supabase/schema.sql`의 행 단위 보안 정책이 정합니다.

OpenAI API Key는 사이트 우상단 **API Key**에서 입력합니다. 키는 브라우저 localStorage에만 저장되고, 실행 요청 헤더(`x-openai-key`)로만 전달되며, 서버는 저장하지 않습니다. 키가 없으면 모든 코드가 **Mock LLM 모드**로 실행됩니다.

### 콘텐츠 검증

```bash
cd backend && uv run python scripts/check_content.py          # 모든 강의 예제와 정답을 Mock 모드로 실행
cd frontend && node scripts/check-patterns.ts                 # 패턴 12종: 분석 → 코드 생성 → 백엔드 검증 (API=http://localhost:8000)
cd frontend && node scripts/check-frontmatter.mjs             # 마크다운 프론트매터 YAML 검사
```

## 배포 (누구나 접속해서 실행)

> **현재 채택한 구성: Cloud Run(백엔드) + Vercel Hobby(프론트엔드)** → 단계별 절차는 [DEPLOY.md](DEPLOY.md)를 참고하세요. 아래는 다른 배포 방식입니다.

### A. 단일 서버 (VPS, 권장)

```bash
WEB_ORIGIN=https://agentlab.example.com \
PUBLIC_API_URL=https://api.agentlab.example.com \
docker compose up -d --build
```

HTTPS는 앞단 리버스 프록시(Caddy, Nginx, Cloudflare Tunnel)에서 처리합니다. 예: `web:3000` → `agentlab.example.com`, `api:8000` → `api.agentlab.example.com`.

### B. 분리 배포

- **프론트엔드:** Vercel에 `frontend/`를 배포하고 `NEXT_PUBLIC_API_URL`을 백엔드 주소로 지정합니다.
- **백엔드:** `backend/Dockerfile`을 Fly.io, Railway, Render, Cloud Run 등 컨테이너 플랫폼에 배포합니다.
  - 환경변수 `AGENTLAB_CORS_ORIGINS`에 프론트엔드 도메인을 지정합니다.
  - 캐시 DB를 유지하려면 `/data`에 볼륨을 붙입니다.

### 백엔드 환경변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `AGENTLAB_CORS_ORIGINS` | `*` | 허용할 프론트엔드 Origin (쉼표로 구분) |
| `AGENTLAB_MAX_CONCURRENCY` | 8 | 동시에 실행할 수 있는 코드 수 |
| `AGENTLAB_MAX_TIMEOUT` | 90 | 실행 1회의 최대 시간(초) |
| `AGENTLAB_MEM_LIMIT_MB` | 1024 | 실행 1회의 메모리 상한 (Linux rlimit) |
| `AGENTLAB_RATE_RUN` / `_VALIDATE` / `_REFINE` | 30 / 15 / 6 | IP별 분당 요청 수 |
| `AGENTLAB_REFINE_MODEL` | `gpt-5` | 사용자가 모델을 지정하지 않았을 때 쓰는 고도화 모델 |
| `AGENTLAB_CACHE_DB` | `data/refine_cache.sqlite` | 검증된 고도화 코드 캐시 (로컬/VPS) |
| `AGENTLAB_CACHE_BUCKET` | (없음) | 지정하면 GCS 버킷을 캐시로 사용 (Cloud Run) |
| `AGENTLAB_CORS_ORIGIN_REGEX` | (없음) | 정규식 CORS 허용 (Vercel 프리뷰 주소 등) |

### 보안 메모 (공개 실행 서버)

공개 서버에서 임의의 Python을 실행하므로 다음과 같이 여러 겹으로 방어합니다.

- 실행마다 새 임시 디렉터리를 만들고, 최소한의 환경변수만 넘깁니다(서버 비밀값은 전달하지 않음).
- 프로세스 그룹 단위로 타임아웃 시 kill하고, 출력량에 상한을 둡니다.
- rlimit으로 CPU, 메모리, 파일 크기, 프로세스 수를 제한합니다.
- IP별 rate limit과 동시 실행 세마포어를 적용합니다.
- 컨테이너는 non-root 사용자, 읽기 전용 루트 FS, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`으로 실행합니다.

추가로 권장하는 조치:

- 백엔드를 **전용 호스트나 전용 VM**에서 실행합니다.
- 방화벽으로 아웃바운드를 `api.openai.com:443`만 허용합니다. 사용자 코드가 임의의 외부 요청을 보내지 못하게 하기 위해서입니다.
- 트래픽이 많아지면 gVisor(`runsc`) 런타임이나 Firecracker 기반 샌드박스로 격리 수준을 높입니다.
