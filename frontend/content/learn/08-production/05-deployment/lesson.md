---
title: "배포: FastAPI 서빙, SSE, 동시성, LangGraph Server와 스케일링"
summary: "에이전트를 FastAPI로 직접 서빙(인증·스레드 격리·SSE 스트리밍·HITL 재개·동시성 제어)하고 TestClient로 검증합니다. langgraph.json과 Agent Server(LangGraph Server)/LangSmith Deployment, 프로덕션 체크포인터·스토어 구성, 수평 확장 전략까지 다룹니다."
duration: 55
level: 전문가
tags: [deployment, fastapi, sse, concurrency, langgraph-server, postgres, scaling]
requiresKey: false
objectives:
  - lifespan·의존성 주입·Pydantic 검증을 갖춘 FastAPI 에이전트 서버를 설계한다
  - SSE 스트리밍 엔드포인트와 interrupt/resume API를 구현하고 TestClient로 검증한다
  - 동시 실행 상한, 타임아웃, double-texting 방지로 과부하와 경쟁 상태를 제어한다
  - langgraph.json, Agent Server, PostgresSaver/Store를 이용한 프로덕션 배포 구성을 설명한다
---

# 배포

> **"노트북에서 돌아가는 에이전트는 데모다. 천 명이 동시에 써도 돌아가는 에이전트가 제품이다."**

지금까지 만든 에이전트는 파이썬 스크립트 안에서 `agent.invoke()`로 실행되었습니다. 실제 서비스에서는 웹 프론트엔드, 모바일 앱, 사내 시스템이 **네트워크를 통해** 에이전트를 호출합니다. 이 강의에서는 에이전트를 **HTTP API 서버**로 만들고, 배포·운영할 때 생기는 문제를 하나씩 해결합니다.

선택지는 크게 둘입니다.

| 방식 | 설명 | 적합한 경우 |
| --- | --- | --- |
| **직접 서빙 (FastAPI)** | API 계층을 직접 작성 | 기존 백엔드에 통합, 세밀한 제어, 플랫폼 비용 회피 |
| **Agent Server (LangGraph Server)** | `langgraph.json`만 쓰면 스레드·실행·스트리밍·큐·크론 API가 생김 | 빠른 출시, 장시간 실행·백그라운드 작업, LangSmith 연동 |

둘 중 무엇을 고르든 **풀어야 할 문제는 같습니다.** 그래서 먼저 FastAPI로 직접 만들며 원리를 익히고, 이어서 Agent Server가 그 문제를 어떻게 대신 풀어 주는지 봅니다.

## 1. 서버 아키텍처

```mermaid
flowchart LR
    Client["웹/모바일 클라이언트"] -- "HTTPS<br/>POST /threads/{id}/runs/stream" --> LB["로드밸런서<br/>(버퍼링 OFF)"]
    LB --> W1["API 워커 1<br/>FastAPI + 에이전트"]
    LB --> W2["API 워커 2"]
    LB --> W3["API 워커 N"]
    W1 & W2 & W3 --> PG[("Postgres<br/>체크포인터 + Store")]
    W1 & W2 & W3 --> LLM["LLM 제공자 API"]
    W1 & W2 & W3 -.-> LS["LangSmith<br/>트레이스"]
```

핵심 원칙은 **API 워커를 무상태(stateless)로** 두는 것입니다. 대화 상태는 워커의 메모리가 아니라 **체크포인터(Postgres)**에 둡니다. 그래야 어느 워커가 요청을 받아도 같은 대화를 이어갈 수 있고, 워커를 늘리거나 재시작해도 대화가 사라지지 않습니다. 5.1강에서 배운 `thread_id` + 체크포인터가 바로 이 구조를 가능하게 합니다.

## 2. FastAPI로 에이전트 서빙하기

이 강의 폴더의 `agent_service.py`가 서버 코드입니다. 주요 설계를 하나씩 보겠습니다.

### lifespan: 무거운 객체는 한 번만

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.checkpointer = InMemorySaver()        # 운영: AsyncPostgresSaver
    app.state.agent = build_agent(app.state.checkpointer)
    app.state.run_slots = asyncio.Semaphore(MAX_CONCURRENT_RUNS)
    app.state.thread_locks = defaultdict(asyncio.Lock)
    yield
    # shutdown: 커넥션 풀 정리
```

컴파일된 그래프(`create_agent`의 결과)는 **스레드 안전하고 재사용 가능**합니다. 요청마다 새로 만들면 느리고 낭비입니다. 앱이 시작할 때 한 번 만들고, 모든 요청이 공유합니다. 요청마다 달라지는 값(사용자, 스레드)은 `config`와 `context`로 넘깁니다.

### 인증과 테넌트 격리

```python
def current_user(x_api_key: str = Header(default="")) -> UserCtx:
    user = API_KEYS.get(x_api_key)
    if user is None:
        raise HTTPException(401)
    return UserCtx(user_id=user)

def run_config(user, thread_id):
    return {"configurable": {"thread_id": f"{user.user_id}:{thread_id}"}, ...}
```

두 가지가 중요합니다.

1. **사용자 정보는 인증 계층에서** 옵니다. 그 정보가 `context=user`로 에이전트에 전달되고, 도구는 `runtime.context.user_id`로 사용자를 압니다(8.3강의 권한 원칙).
2. **thread_id에 사용자를 섞습니다.** 클라이언트가 보낸 `thread_id`를 그대로 쓰면 bob이 alice의 `thread_id`를 추측해서 대화를 훔쳐볼 수 있습니다. 서버가 `"{user}:{thread}"`로 네임스페이스를 강제하거나, 스레드 소유자를 DB에 기록해 검사합니다.

▶ 오른쪽 IDE의 `examples/01_invoke_api.py`를 실행해 보세요. TestClient로 다음을 차례로 확인합니다.
- 401(인증 없음), 422(Pydantic 검증 실패)
- 같은 스레드로 대화 이어가기, 스레드 상태 조회
- bob이 alice의 스레드를 조회하면 404 — 테넌트 격리
- 환불 요청은 `interrupt` 정보를 담아 응답하고, 상태 조회에서 대기 중인 interrupt가 보임

> [!TIP]
> `fastapi.testclient.TestClient`는 소켓 없이 ASGI 앱을 직접 호출합니다. `with TestClient(app):` 블록에 들어가면 lifespan도 실행됩니다. **배포될 앱과 똑같은 코드**를 서버 없이 검증하는 API 통합 테스트의 표준 방법입니다. CI에서는 여기에 8.2강의 대본 모델을 주입해 결정적으로 테스트합니다.

### SSE 스트리밍과 HITL 재개

8.1강의 UI 이벤트 프로토콜을 HTTP로 내보냅니다. 이 강의 환경의 FastAPI(0.162)에는 SSE 지원이 내장되어 있습니다(구버전에서는 `sse-starlette` 패키지를 씁니다). `response_class=EventSourceResponse`를 지정하고 `ServerSentEvent`를 `yield`하면 됩니다.

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.post("/threads/{thread_id}/runs/stream", response_class=EventSourceResponse)
async def run_stream(thread_id: str, req: RunRequest, user=Depends(current_user)):
    async for part in app.state.agent.astream(..., stream_mode=["messages", "updates"], version="v2"):
        if part["type"] == "messages":
            chunk, meta = part["data"]
            if meta["langgraph_node"] == "model" and chunk.content:
                yield ServerSentEvent(event="token", data={"text": chunk.content}, id=str(seq))
        elif "__interrupt__" in part["data"]:
            ...  # event="interrupt"
    yield ServerSentEvent(event="end", data={...})
```

```mermaid
sequenceDiagram
    participant FE as 프론트엔드
    participant API as FastAPI
    participant G as 에이전트 그래프
    participant DB as 체크포인터
    FE->>API: POST /threads/s2/runs/stream {"A-7 환불"}
    API->>G: astream(...)
    G->>DB: 체크포인트 저장 (interrupt 직전)
    API-->>FE: event: interrupt (승인 요청)
    API-->>FE: event: end
    Note over FE: 상담원이 '승인' 클릭
    FE->>API: POST /threads/s2/resume {"decision":"approve"}
    API->>G: astream(Command(resume=...))
    G->>DB: 체크포인트 불러와 재개
    API-->>FE: event: tool (issue_refund 결과)
    API-->>FE: event: token ... token
    API-->>FE: event: end
```

▶ `examples/02_sse_streaming_and_resume.py`를 실행해 보세요. 클라이언트가 SSE 바이트를 줄 단위로 읽어 이벤트로 파싱하는 과정까지 보여 줍니다. 브라우저에서는 요청이 `POST`이므로 `EventSource` 대신 `fetch()` + `ReadableStream`으로 읽거나, `@microsoft/fetch-event-source` 같은 라이브러리를 씁니다.

interrupt가 걸린 실행과 재개는 **서로 다른 HTTP 요청**입니다. 그 사이에 몇 분, 며칠이 지나도 됩니다. 상태가 체크포인터에 있기 때문입니다. 첫 요청은 워커 1이, 재개 요청은 워커 3이 처리해도 문제없습니다.

## 3. 비동기와 동시성

### 왜 async인가

에이전트 요청의 시간은 대부분 **기다리는 시간**입니다. LLM 응답을 기다리고(수 초), 외부 API를 기다립니다. CPU는 거의 놀고 있습니다. `async def` 엔드포인트와 `ainvoke`/`astream`, async 도구를 쓰면, 한 요청이 I/O를 기다리는 동안 이벤트 루프가 다른 요청을 처리합니다.

▶ `examples/03_concurrency.py`를 실행해 보세요. 0.2초짜리 async 도구를 쓰는 요청 5개를 순차로 보내면 약 1초가 걸립니다. 동시에 보내면 약 0.2초에 끝납니다.

> [!WARNING]
> async 엔드포인트 안에서 **동기 블로킹 호출**(`requests.get`, `time.sleep`, 동기 DB 드라이버, `agent.invoke`)을 하면 이벤트 루프 전체가 멈춥니다. 그동안 그 워커의 다른 모든 요청이 기다립니다. 동기 라이브러리를 꼭 써야 한다면 `await asyncio.to_thread(fn)`으로 스레드풀에 넘기세요. LangChain의 동기 `@tool` 함수는 `ainvoke` 경로에서 자동으로 스레드풀에서 실행됩니다.

### 과부하를 다루는 세 가지 장치

예제 2~4번이 각각 보여 줍니다.

**① 같은 스레드 동시 실행 방지 (409)**
사용자가 답을 기다리다 메시지를 또 보내는 상황(double-texting)은 흔합니다. 같은 `thread_id`로 두 실행이 동시에 돌면 체크포인트가 꼬이고 메시지 순서가 엉킵니다. 스레드별 락으로 두 번째 요청을 거절합니다. 실무에서는 정책을 고릅니다. **거절**(reject), **새 요청으로 기존 실행 중단**(interrupt), **기존 실행 되돌리고 새로 시작**(rollback), **줄 세우기**(enqueue)입니다. Agent Server는 이것을 `multitask_strategy` 옵션으로 제공합니다.

> [!NOTE]
> 예제의 `asyncio.Lock`은 **워커 프로세스 하나 안에서만** 동작합니다. 워커가 여러 개면 Redis 락이나 DB 행 잠금(`SELECT ... FOR UPDATE`)처럼 프로세스 간에 공유되는 락이 필요합니다.

**② 동시 실행 상한 (503 + Retry-After)**
LLM 제공자에는 분당 토큰·요청 한도(TPM/RPM)가 있고, 워커에는 메모리 한계가 있습니다. 한도를 넘는 요청을 받아 두면 모두 느려지다가 한꺼번에 실패합니다. 상한을 넘으면 **즉시** 503을 돌려주고(fail fast), 클라이언트가 `Retry-After` 후 재시도하게 합니다.

**③ 실행 타임아웃 (504)**
`async with asyncio.timeout(RUN_TIMEOUT_S):`로 실행 시간을 제한합니다. 타임아웃이 나면 진행 중이던 그래프 실행이 취소됩니다. 그래도 마지막 체크포인트까지의 진행은 남아 있어서 나중에 이어서 실행할 수 있습니다(5.5강 durable execution). 노드 단위 타임아웃은 `add_node(..., timeout=...)`으로 설정합니다.

## 4. 프로덕션 체크포인터와 스토어

`InMemorySaver`는 프로세스가 재시작되면 모든 대화를 잃고, 워커끼리 공유되지도 않습니다. 운영에서는 Postgres를 씁니다. 아래 코드는 네트워크 DB가 필요하므로 참고용입니다.

```python
# pip install langgraph-checkpoint-postgres "psycopg[binary,pool]"
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

DB_URI = os.environ["DATABASE_URL"]   # postgresql://user:pass@host:5432/agent?sslmode=require

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with (
        AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
        AsyncPostgresStore.from_conn_string(DB_URI) as store,
    ):
        await checkpointer.setup()      # 테이블 생성/마이그레이션 (배포 파이프라인에서 1회 실행 권장)
        await store.setup()
        app.state.agent = build_agent(checkpointer=checkpointer, store=store)
        yield
```

운영 팁은 다음과 같습니다.
- **커넥션 풀** 크기 = 워커 수 × 워커당 동시 실행 수를 감당하도록 잡습니다. PgBouncer를 앞에 두는 경우가 많습니다.
- 체크포인트는 계속 쌓입니다. **보존 정책**(예: 90일 지난 스레드 삭제, 오래된 체크포인트 정리)을 정하세요.
- 내구성 모드(`durability="async"|"sync"|"exit"`, 5.1강)로 쓰기 빈도와 안전성의 균형을 맞춥니다.
- 장기 메모리 Store(5.4강)의 시맨틱 검색은 pgvector 인덱스를 씁니다.

## 5. Agent Server (LangGraph Server)와 LangSmith Deployment

지금까지 직접 만든 기능(스레드 API, 스트리밍, interrupt/resume, 동시성 정책, 영속성)을 **플랫폼이 표준으로 제공**하는 것이 Agent Server입니다. 예전에는 LangGraph Server / LangGraph Platform이라고 불렀고, 지금은 LangSmith의 배포 기능(LangSmith Deployment)으로 통합되었습니다.

### langgraph.json

배포 단위를 설명하는 설정 파일입니다.

```json
{
  "dependencies": ["."],
  "graphs": {
    "support": "./src/support/graph.py:graph",
    "research": "./src/research/agent.py:make_agent"
  },
  "env": ".env",
  "python_version": "3.13",
  "auth": { "path": "./src/support/auth.py:auth" },
  "http": { "app": "./src/support/webapp.py:app" },
  "store": {
    "index": { "embed": "openai:text-embedding-3-small", "dims": 1536, "fields": ["$"] }
  }
}
```

- `graphs`: 공개할 그래프. **컴파일된 그래프 객체**나 그래프를 만드는 **팩토리 함수**를 가리킵니다. 체크포인터는 지정하지 않습니다. 플랫폼이 Postgres 체크포인터를 자동으로 붙입니다.
- `auth`: `langgraph_sdk.Auth`로 작성한 커스텀 인증·인가 핸들러. 리소스(스레드, 실행)에 소유자 메타데이터를 붙이고 필터링해서 테넌트 격리를 구현합니다.
- `http.app`: 기존 FastAPI/Starlette 앱을 붙여 커스텀 라우트(웹훅, 관리 API)를 추가합니다.
- `store.index`: 장기 메모리 Store의 시맨틱 검색 설정.

### 로컬 개발과 빌드

```bash
pip install -U "langgraph-cli[inmem]"
langgraph dev                      # 핫 리로드 개발 서버 (인메모리) + LangGraph Studio 연결
langgraph build -t support-agent:1.4.0   # 프로덕션 Docker 이미지 빌드
langgraph up                       # Postgres/Redis 포함 로컬 전체 스택 실행
```

### SDK로 호출하기

```python
from langgraph_sdk import get_client

client = get_client(url="https://support-agent.example.com", api_key=os.environ["LANGSMITH_API_KEY"])
thread = await client.threads.create(metadata={"user_id": "u-42"})

async for chunk in client.runs.stream(
    thread["thread_id"], "support",
    input={"messages": [{"role": "user", "content": "A-7 환불해줘"}]},
    stream_mode=["messages-tuple", "updates"],
    multitask_strategy="reject",           # double-texting 정책
):
    print(chunk.event, chunk.data)

# 백그라운드 실행: 응답을 기다리지 않고 run 을 만들고, 나중에 join 해서 결과를 받는다
run = await client.runs.create(thread["thread_id"], "support", input={...})
result = await client.runs.join(thread["thread_id"], run["run_id"])
```

Agent Server가 추가로 주는 것들은 다음과 같습니다.
- **태스크 큐**: 실행이 API 워커가 아니라 큐 워커에서 돌아갑니다. 몇 시간짜리 작업도 HTTP 연결과 무관하게 계속 실행됩니다.
- **재연결(join stream)**: 끊긴 클라이언트가 진행 중인 실행에 다시 붙습니다.
- **크론(cron)**: 주기적 실행 (매일 아침 리포트 에이전트 등)
- **Assistants**: 같은 그래프를 설정(프롬프트, 모델)만 바꿔 여러 버전으로 운영
- **LangGraph Studio**: 그래프 시각화, 상태 편집, 타임 트래블 디버깅

배포 형태는 **완전 관리형(Cloud)**, **하이브리드**(컨트롤 플레인은 LangChain, 데이터 플레인은 우리 클라우드), **셀프 호스팅**(Kubernetes에 직접 설치)이 있습니다. 데이터 주권과 규제 요건에 따라 고릅니다.

## 6. 컨테이너와 스케일링

직접 서빙한다면 컨테이너 이미지를 만듭니다.

```dockerfile
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# uv 로 잠금 파일 기준 설치 (재현 가능한 빌드)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN useradd --create-home --uid 10001 app && chown -R app /app
# non-root 사용자로 실행
USER app

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uv", "run", "uvicorn", "support.agent_service:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--timeout-graceful-shutdown", "30"]
```

> [!NOTE]
> 실제 이미지에서는 `uv` 이미지 태그도 `latest`가 아닌 특정 버전으로 고정하세요. 재현 가능한 빌드의 기본입니다.

스케일링 체크리스트는 다음과 같습니다.

| 항목 | 권장 |
| --- | --- |
| 수평 확장 | 무상태 워커 + 공유 Postgres. HPA 기준은 CPU보다 **동시 실행 수/대기열 길이**가 정확 |
| 워커 수 | 에이전트는 I/O 위주 → 워커당 동시 실행을 늘리고 프로세스는 적게 (`--workers`는 코어 수 이하) |
| 장시간 실행 | HTTP 요청 안에서 수 분 이상 돌리지 말 것 → 백그라운드 큐(Agent Server, Celery, Arq) + 상태 조회/스트림 재연결 |
| 그레이스풀 종료 | SIGTERM → 새 요청 거부 → 진행 중 실행 마무리(또는 체크포인트 후 중단) → 종료. K8s `terminationGracePeriodSeconds`를 SSE 최대 길이에 맞춤 |
| 프로브 | liveness는 가볍게(`/healthz`), readiness는 DB 연결까지 확인 |
| LLM 한도 | 제공자 TPM/RPM이 진짜 병목인 경우가 많음 → 서버 전체 토큰 버킷, 우선순위 큐, 다중 리전/다중 키 |
| 배포 전략 | 프롬프트·모델 변경은 **카나리**(트래픽 5%)로 내보내고 8.2강의 온라인 평가 지표를 비교 |

## 7. 실습 안내

`exercise.py`에서 미니 에이전트 API를 완성합니다.

1. `lifespan`에서 에이전트와 체크포인터 생성
2. `POST /chat/{thread_id}`: 인증 + 사용자별 스레드 격리 + 대화 턴 수 반환
3. `POST /chat/{thread_id}/stream`: 토큰 SSE 스트리밍

자가 채점은 `TestClient`로 401, 대화 지속, 사용자 격리, SSE 이벤트 형식을 확인합니다. 서버를 띄우지 않으므로 IDE에서 바로 실행됩니다.

## 8. 현업에서는

**비용**: 운영 비용의 대부분은 서버가 아니라 **LLM 토큰**입니다. 그래도 서버 쪽에서 할 수 있는 일이 많습니다. 끊긴 SSE 연결의 실행을 취소하지 않으면, 아무도 보지 않는 답변에 토큰을 씁니다. 같은 질문의 중복 요청은 409나 캐시로 막습니다(8.6강).

**지연**: 사용자 체감 지연 = 네트워크 + 큐 대기 + TTFT. 큐 대기는 동시성 상한과 워커 수로, TTFT는 모델 선택과 프롬프트 길이로 관리합니다. p95를 대시보드에 올리고 SLO를 정하세요(예: TTFT p95 < 2초).

**관측성**: 요청마다 `request_id`를 만들어 응답 헤더, 애플리케이션 로그, LangSmith 트레이스 metadata에 **같은 값**으로 남깁니다. 고객 문의 → 로그 → 트레이스를 한 번에 따라갈 수 있습니다.

**장애**: LLM 제공자 장애는 반드시 옵니다. 폴백 모델(8.6강), 서킷 브레이커, "지금은 상담원 연결로 안내" 같은 우아한 저하(graceful degradation) 경로를 준비하세요. 체크포인터 DB 장애는 전체 장애이므로 Postgres 고가용성(관리형 DB, 읽기 복제본, 백업·복구 리허설)이 필수입니다.

**보안**: API 키·DB 비밀번호는 이미지에 굽지 않고 시크릿 매니저에서 주입합니다. 입력 크기 제한(`max_length`), 사용자별 레이트 리밋, CORS 허용 도메인 제한, 컨테이너 non-root 실행을 기본으로 합니다.

**테스트**: 이 강의처럼 `TestClient` + 대본 모델로 API 계약(상태 코드, 이벤트 형식)을 CI에서 검증합니다. 프론트엔드 팀과 SSE 이벤트 스키마를 **버전 관리되는 계약**으로 합의해 두면, 백엔드 그래프를 바꿔도 화면이 깨지지 않습니다.

## 9. 정리

- 컴파일된 에이전트는 lifespan에서 한 번 만들고, 사용자·스레드는 `config`/`context`로 요청마다 넘깁니다.
- 인증은 서버가, 스레드 격리는 `thread_id` 네임스페이스로 강제합니다.
- FastAPI 내장 SSE(`EventSourceResponse` + `ServerSentEvent`)로 스트리밍하고, interrupt/resume은 별도 요청으로 처리합니다. 그 사이의 상태는 체크포인터가 지킵니다.
- async + 동시성 상한(503) + 타임아웃(504) + 스레드 락(409)으로 과부하와 경쟁 상태를 제어합니다.
- 운영 영속성은 Postgres 체크포인터/스토어, 빠른 출시와 장시간 실행은 Agent Server(`langgraph.json`)가 답입니다.
- 다음 강의(8.6)에서는 같은 품질을 **더 싸고 빠르게** 만드는 비용·성능 최적화를 다룹니다.
