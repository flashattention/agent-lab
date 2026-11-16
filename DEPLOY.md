# 배포 가이드: Cloud Run (백엔드) + Vercel Hobby (프론트엔드)

```
브라우저 ──▶ Vercel (Next.js, 정적 페이지 중심)
   │
   └─ 코드 실행/검증/고도화 요청 ──▶ Cloud Run: agentlab-api (서울 리전)
                                       └─ GCS 버킷: 검증된 고도화 코드 캐시
```

## 0. 준비 (최초 1회)

1. **GitHub 저장소:** 이 폴더를 GitHub에 올립니다. Vercel이 저장소를 연동해 push할 때마다 자동으로 배포합니다.
2. **Google Cloud**
   - <https://console.cloud.google.com>에서 프로젝트를 만들고 결제 계정을 연결합니다. 무료 사용량 안에서는 과금되지 않습니다.
   - CLI를 설치하고 로그인합니다.
     ```bash
     # macOS
     brew install --cask google-cloud-sdk
     # Linux / WSL (Ubuntu)
     curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
     echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
     sudo apt-get update && sudo apt-get install -y google-cloud-cli

     gcloud auth login
     ```
3. **Vercel:** <https://vercel.com>에 GitHub 계정으로 가입합니다(Hobby).

## 0-1. Supabase: 로그인과 프로젝트 저장 (최초 1회)

Google 로그인, 프로젝트 저장, 링크 공유는 Supabase를 씁니다. 무료 요금제로 충분합니다.

1. <https://supabase.com>에서 프로젝트를 만듭니다(리전은 Seoul 권장).
   - Data API: **켜기** · Automatically expose new tables: **끄기** · automatic RLS: **켜기** (schema.sql이 필요한 권한을 직접 부여합니다)
2. **SQL Editor**에 [`supabase/schema.sql`](supabase/schema.sql) 내용을 붙여 넣고 실행합니다. `projects` 테이블과 행 단위 보안 정책이 만들어집니다.
   이미 실행한 적이 있어도 새 버전으로 한 번 더 실행합니다. 에이전트 프리셋을 저장하는 `agent_presets` 테이블이 추가되었습니다.
3. **Project Settings → API**에서 두 값을 적어 둡니다.
   - Project URL (`https://xxxx.supabase.co`)
   - anon public key 또는 publishable key(`sb_publishable_...`) (브라우저에 노출되어도 되는 키입니다. `service_role`/secret 키는 어디에도 넣지 않습니다.)
   - URL은 끝의 `/rest/v1/` 없이 `https://xxxx.supabase.co`만 씁니다.
4. Google 로그인 연결
   1. <https://console.cloud.google.com> → **API 및 서비스 → OAuth 동의 화면**을 만듭니다(외부, 앱 이름과 이메일만 입력).
   2. **사용자 인증 정보 → OAuth 클라이언트 ID 만들기 → 웹 애플리케이션**을 선택합니다.
      - 승인된 리디렉션 URI: `https://xxxx.supabase.co/auth/v1/callback`
   3. 발급된 클라이언트 ID와 보안 비밀을 Supabase **Authentication → Sign In / Providers → Google**에 넣고 켭니다.
5. Supabase **Authentication → URL Configuration**
   - Site URL: 운영 주소 (`https://agentlab-ai.vercel.app`)
   - Redirect URLs: `https://agentlab-ai.vercel.app/**`, `http://localhost:3000/**`

> **앱 게시 조건:** 브랜딩에 홈페이지(`https://agentlab-ai.vercel.app`), 개인정보처리방침(`/privacy`), 서비스 약관(`/terms`) 링크를 넣고, 승인된 도메인에 `agentlab-ai.vercel.app`과 `xxxx.supabase.co`를 모두 등록해야 **앱 게시** 버튼이 활성화됩니다. 링크는 실제로 열려야 하므로 Vercel 배포 후에 입력합니다.
>
> OAuth 동의 화면이 "테스트" 상태이면 등록한 테스트 사용자만 로그인할 수 있습니다. 누구나 쓰게 하려면 **앱 게시**를 누릅니다. 이메일과 프로필만 요청하므로 Google 심사는 필요 없습니다.

## 1. 프론트엔드 주소 정하기

Vercel 프로젝트 이름이 운영 주소가 됩니다. 예: 이름이 `agentlab-ai`이면 주소는 `https://agentlab-ai.vercel.app`입니다.
백엔드 CORS 설정에 이 주소가 필요하므로 이름을 먼저 정합니다.

## 2. 백엔드 배포 (Cloud Run)

```bash
PROJECT=<GCP 프로젝트 ID> WEB_ORIGIN=https://agentlab-ai.vercel.app \
SUPABASE_URL=https://xxxx.supabase.co SUPABASE_ANON_KEY=<anon public key> \
./deploy/cloudrun.sh
```

`SUPABASE_URL`과 `SUPABASE_ANON_KEY`를 주면 코드 실행·검증·고도화 요청에 로그인이 필요해지고, 사용자별 하루 한도가 적용됩니다. 생략하면 누구나 로그인 없이 실행할 수 있으므로 운영 배포에서는 꼭 넣습니다.

스크립트는 다음을 차례로 수행합니다.

1. API 활성화
2. 캐시용 GCS 버킷 생성
3. 최소 권한 서비스 계정 생성 (버킷 쓰기 권한만 부여)
4. Cloud Build로 이미지 빌드
5. 서울 리전에 배포

배포가 끝나면 `https://agentlab-api-xxxx.a.run.app` 형태의 주소가 출력됩니다.

비용 상한을 낮추려면 `MAX_INSTANCES=1`을 함께 줍니다(현재 운영 설정).

> **새 프로젝트에서 `PERMISSION_DENIED: Build failed because the default service account is missing required IAM permissions`가 나면** 빌드용 기본 서비스 계정에 권한을 주고, 1~5분 뒤 다시 실행합니다.
> ```bash
> N=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
> gcloud projects add-iam-policy-binding $PROJECT \
>   --member=serviceAccount:$N-compute@developer.gserviceaccount.com --role=roles/run.builder
> ```

## 3. 프론트엔드 배포 (Vercel)

1. Vercel 대시보드에서 **Add New → Project**를 누르고 GitHub 저장소를 선택합니다.
2. **Project Name:** 1단계에서 정한 이름(`agentlab-ai`)을 입력합니다.
3. **Root Directory:** `frontend`를 지정합니다.
4. **Environment Variables:** 세 가지를 넣습니다.
   - `NEXT_PUBLIC_API_URL`: 2단계에서 출력된 Cloud Run 주소
   - `NEXT_PUBLIC_SUPABASE_URL`: Supabase Project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase anon public key
5. **Deploy**를 누릅니다.

> `NEXT_PUBLIC_*` 값은 빌드할 때 코드에 박힙니다. 값을 바꾸면 **Redeploy**해야 반영됩니다.

## 4. 확인

- 사이트 우상단 배지가 **Runtime(초록)**이면 백엔드와 연결된 것입니다.
- 우상단 **로그인**으로 Google 로그인이 되는지 확인합니다.
- 플레이그라운드에서 **프로젝트로 저장** → 새로고침해도 그대로인지, **공유** 링크를 시크릿 창에서 열면 보기 전용으로 열리는지 확인합니다.
- 로그인한 상태에서 강의 페이지와 플레이그라운드의 ▶ 실행이 되는지, 로그아웃하면 로그인 안내가 나오는지 확인합니다.

## 운영 설정 요약

| 항목 | 값 | 이유 |
| --- | --- | --- |
| 리전 | `asia-northeast3` (서울) | 국내 사용자 지연 최소화 |
| 인스턴스 | 2 vCPU / 4GiB, 동시 요청 8 | 실행 1회에 약 300~500MB 사용 |
| 최소/최대 인스턴스 | 0 / 3 | 요청이 없으면 0원. 최대 개수로 비용 상한을 둠 |
| 요청 타임아웃 | 300초 | 코드 실행 상한은 90초 |
| 하루 한도 (사용자별) | 실행 200 / 검증 100 / 고도화 20 | `AGENTLAB_DAILY_RUN`, `AGENTLAB_DAILY_VALIDATE`, `AGENTLAB_DAILY_REFINE`로 조정. 인스턴스 메모리에 기록하므로 인스턴스가 여러 개이거나 재시작되면 실제 허용량은 더 커질 수 있음 |
| 캐시 | GCS `refine-cache/<구조해시>.json` | 인스턴스끼리 공유되고, 재시작해도 유지됨 |

## 예상 비용

- **Vercel Hobby:** 무료. 비상업적 용도로만 쓸 수 있습니다.
- **Cloud Run:** 요청을 처리하는 동안에만 과금됩니다. 매월 무료 사용량(약 vCPU 18만 초, 메모리 36만 GiB-초)이 있습니다.
  - 개인 학습 수준(하루 실행 수십~수백 회)이면 대부분 **0원 ~ 월 몇 천 원**입니다.
  - 상한: 인스턴스 3개가 한 달 내내 쉬지 않고 바쁜 최악의 경우 월 수십만 원이 될 수 있습니다. `MAX_INSTANCES=1`로 낮추면 상한도 함께 내려갑니다.
- **Cloud Build / Artifact Registry / GCS:** 배포 빈도가 낮으면 거의 0원입니다(이미지 저장 수백 MB 수준).
- **OpenAI:** 방문자가 각자의 키를 쓰므로(BYOK) 운영자 부담은 없습니다.

> **결제 알림 설정을 권장합니다:** 콘솔 → 결제 → 예산 및 알림에서 예를 들어 월 1만 원 예산과 50/90/100% 알림을 걸어 두세요.

## 콜드 스타트

최소 인스턴스가 0이라 한동안 요청이 없으면 첫 실행에 5~15초가 더 걸립니다.
항상 빠르게 응답해야 한다면 `--min-instances 1`로 바꿀 수 있지만, 상시 비용이 생깁니다(월 수만 원 수준).

## 부록: 다른 배포 방식

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

## 보안 · 운영 설정

샌드박스 네트워크 허용 목록, 프록시 홉 수, 요청 크기 상한 같은 설정과 남은 인프라 과제(실행 서비스 분리, 분산 rate limit 등)는
[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md)에 정리되어 있습니다.
