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
     brew install --cask google-cloud-sdk
     gcloud auth login
     ```
3. **Vercel:** <https://vercel.com>에 GitHub 계정으로 가입합니다(Hobby).

## 1. 프론트엔드 주소 정하기

Vercel 프로젝트 이름이 운영 주소가 됩니다. 예: 이름이 `agentlab-louis`이면 주소는 `https://agentlab-louis.vercel.app`입니다.
백엔드 CORS 설정에 이 주소가 필요하므로 이름을 먼저 정합니다.

## 2. 백엔드 배포 (Cloud Run)

```bash
PROJECT=<GCP 프로젝트 ID> WEB_ORIGIN=https://agentlab-louis.vercel.app ./deploy/cloudrun.sh
```

스크립트는 다음을 차례로 수행합니다.

1. API 활성화
2. 캐시용 GCS 버킷 생성
3. 최소 권한 서비스 계정 생성 (버킷 쓰기 권한만 부여)
4. Cloud Build로 이미지 빌드
5. 서울 리전에 배포

배포가 끝나면 `https://agentlab-api-xxxx.a.run.app` 형태의 주소가 출력됩니다.

## 3. 프론트엔드 배포 (Vercel)

1. Vercel 대시보드에서 **Add New → Project**를 누르고 GitHub 저장소를 선택합니다.
2. **Project Name:** 1단계에서 정한 이름(`agentlab-louis`)을 입력합니다.
3. **Root Directory:** `frontend`를 지정합니다.
4. **Environment Variables:** `NEXT_PUBLIC_API_URL`에 2단계에서 출력된 Cloud Run 주소를 넣습니다.
5. **Deploy**를 누릅니다.

> `NEXT_PUBLIC_*` 값은 빌드할 때 코드에 박힙니다. 값을 바꾸면 **Redeploy**해야 반영됩니다.

## 4. 확인

- 사이트 우상단 배지가 **Runtime(초록)**이면 백엔드와 연결된 것입니다.
- 강의 페이지에서 ▶ 실행이 되는지, 플레이그라운드에서 패턴 실행이 되는지 확인합니다.

## 운영 설정 요약

| 항목 | 값 | 이유 |
| --- | --- | --- |
| 리전 | `asia-northeast3` (서울) | 국내 사용자 지연 최소화 |
| 인스턴스 | 2 vCPU / 4GiB, 동시 요청 8 | 실행 1회에 약 300~500MB 사용 |
| 최소/최대 인스턴스 | 0 / 3 | 요청이 없으면 0원. 최대 개수로 비용 상한을 둠 |
| 요청 타임아웃 | 300초 | 코드 실행 상한은 90초 |
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
