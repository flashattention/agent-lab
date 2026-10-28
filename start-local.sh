#!/usr/bin/env bash
# 로컬에서 AgentLab 실행: 백엔드(:8000) + 프론트엔드(:3000). Ctrl+C 로 둘 다 종료.
set -euo pipefail
cd "$(dirname "$0")"

(cd backend && uv sync -q && uv run uvicorn app.main:app --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd frontend
[ -d node_modules ] || npm install
echo "▶ http://localhost:3000 을 브라우저로 여세요"
npm run dev -- --port 3000
