#!/usr/bin/env bash
# AgentLab API → Google Cloud Run 배포
#
# 사용법:
#   PROJECT=my-gcp-project WEB_ORIGIN=https://agentlab.vercel.app ./deploy/cloudrun.sh
#
# 선택 환경변수:
#   REGION      (기본 asia-northeast3 = 서울)
#   SERVICE     (기본 agentlab-api)
#   BUCKET      (기본 <PROJECT>-agentlab-cache) — 검증된 고도화 코드 캐시
#   MAX_INSTANCES (기본 3) — 비용 상한 역할
set -euo pipefail

PROJECT="${PROJECT:?PROJECT 환경변수에 GCP 프로젝트 ID를 지정하세요}"
WEB_ORIGIN="${WEB_ORIGIN:?WEB_ORIGIN 에 프론트엔드 주소(https://xxx.vercel.app)를 지정하세요}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-agentlab-api}"
BUCKET="${BUCKET:-${PROJECT}-agentlab-cache}"
MAX_INSTANCES="${MAX_INSTANCES:-3}"
SA_NAME="agentlab-api"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
# Vercel 프리뷰 주소(<프로젝트>-<해시>-<팀>.vercel.app)까지 허용
PROJECT_HOST="$(echo "$WEB_ORIGIN" | sed -E 's#https?://([^.]+)\.vercel\.app.*#\1#')"
ORIGIN_REGEX="https://${PROJECT_HOST}(-[a-z0-9-]+)?\\.vercel\\.app"

cd "$(dirname "$0")/.."

echo "▶ 프로젝트 설정: $PROJECT ($REGION)"
gcloud config set project "$PROJECT" >/dev/null

echo "▶ 필요한 API 활성화"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

echo "▶ 캐시 버킷: gs://$BUCKET"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
fi

echo "▶ 전용 서비스 계정 (버킷 쓰기 권한만 부여 — 최소 권한)"
if ! gcloud iam service-accounts describe "$SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="AgentLab API (sandbox runner)"
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SA" --role="roles/storage.objectAdmin" >/dev/null

echo "▶ 빌드 & 배포 (Cloud Build 가 backend/Dockerfile 로 이미지를 만든다)"
gcloud run deploy "$SERVICE" \
  --source backend \
  --region "$REGION" \
  --service-account "$SA" \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --cpu 2 --memory 4Gi \
  --concurrency 8 \
  --min-instances 0 --max-instances "$MAX_INSTANCES" \
  --timeout 300 \
  --cpu-boost \
  --set-env-vars "^@^AGENTLAB_CACHE_BUCKET=${BUCKET}@AGENTLAB_CORS_ORIGINS=${WEB_ORIGIN}@AGENTLAB_CORS_ORIGIN_REGEX=${ORIGIN_REGEX}@WEB_CONCURRENCY=2@AGENTLAB_MAX_CONCURRENCY=4"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo
echo "✅ 배포 완료: $URL"
curl -fsS "$URL/api/health" && echo
echo
echo "다음 단계: Vercel 프로젝트 환경변수 NEXT_PUBLIC_API_URL=$URL 로 설정 후 프론트엔드를 재배포하세요."
