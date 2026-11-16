# AgentLab API — 사용자 코드를 실행하는 샌드박스 서버
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    AGENTLAB_CACHE_DB=/data/refine_cache.sqlite

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && rm -rf /root/.cache

# tiktoken 인코딩을 이미지에 미리 받아 둔다 (런타임 네트워크 의존 제거)
RUN mkdir -p $TIKTOKEN_CACHE_DIR && \
    /app/.venv/bin/python -c "import tiktoken; [tiktoken.get_encoding(e) for e in ('o200k_base','cl100k_base')]"

COPY app ./app
COPY sandbox ./sandbox
# 샌드박스 보안 정책을 -I(격리 모드) 자식 파이썬에도 걸기 위한 .pth (AGENTLAB_SANDBOX=1 일 때만 동작)
RUN /app/.venv/bin/python -c "import app.runner"

# 비root 사용자로 실행. /data 만 쓰기 가능(캐시 DB), 코드 실행은 /tmp 아래 임시 디렉터리에서 이루어진다.
RUN useradd --create-home --uid 10001 runner && mkdir -p /data && chown runner /data && chmod -R a-w /app /opt/tiktoken
USER runner

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    AGENTLAB_MAX_CONCURRENCY=4 \
    AGENTLAB_MEM_LIMIT_MB=1024 \
    AGENTLAB_MAX_TIMEOUT=90

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/health')"
# Cloud Run 은 PORT 환경변수(기본 8080)를 주입한다. 워커당 동시 실행 = AGENTLAB_MAX_CONCURRENCY
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips '*'"]
