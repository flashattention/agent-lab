---
title: "LangGraph Server 배포 (langgraph.json · CLI · SDK)"
description: "langgraph.json 설정, langgraph-cli(dev/up/build), langgraph_sdk 클라이언트로 스레드·런 호출, RemoteGraph"
order: 5
source: "https://docs.langchain.com/langsmith/deployments"
tags: [deployment, langgraph-server, sdk, cli]
---

LangGraph Server(Agent Server)는 컴파일된 그래프를 **스레드(Thread)·런(Run)·어시스턴트(Assistant)** 개념의 HTTP API로 서비스하는 런타임입니다. 체크포인터·스토어·작업 큐·스트리밍·백그라운드 실행을 서버가 제공하므로, 배포할 그래프에는 체크포인터를 직접 넣지 않습니다. 로컬은 `langgraph dev`, 프로덕션은 LangSmith Deployment(클라우드/하이브리드/셀프호스트) 또는 `langgraph build`로 만든 Docker 이미지로 운영합니다.

| 구성 요소 | 패키지 | 설치 여부(AgentLab) |
|---|---|---|
| `langgraph_sdk` (Python 클라이언트) | `langgraph-sdk` 0.4.10 | 설치됨 |
| `langgraph` CLI (`dev`, `up`, `build`, `dockerfile`) | `langgraph-cli[inmem]` | **미설치** |
| 서버 런타임 | `langgraph-api` | **미설치** |

## Import

```python
from langgraph_sdk import get_client, get_sync_client   # pip install langgraph-sdk
from langgraph.pregel.remote import RemoteGraph          # 원격 그래프를 로컬 그래프처럼 사용
```

```bash
pip install -U "langgraph-cli[inmem]"   # 로컬 개발 서버
```

## 시그니처

```python
get_client(*, url: str | None = None, api_key: str | None = <env>, headers: Mapping[str, str] | None = None,
           timeout: TimeoutTypes | None = None) -> LangGraphClient          # async
get_sync_client(*, url=None, api_key=<env>, headers=None, timeout=None) -> SyncLangGraphClient

client.threads.create(*, metadata=None, thread_id=None, if_exists=None, graph_id=None, ttl=None, ...) -> Thread
client.runs.stream(thread_id: str | None, assistant_id: str, *, input=None, command=None,
                   stream_mode: StreamMode | Sequence[StreamMode] = "values", stream_subgraphs: bool = False,
                   config=None, context=None, interrupt_before=None, interrupt_after=None,
                   multitask_strategy=None, on_disconnect=None, if_not_exists=None, ...)
client.runs.wait(thread_id, assistant_id, *, input=None, command=None, config=None, context=None,
                 multitask_strategy=None, raise_error: bool = True, ...)
client.runs.create(thread_id, assistant_id, *, input=None, ..., webhook=None, after_seconds=None)  # 백그라운드 런
client.assistants.search(*, metadata=None, graph_id=None, name=None, limit=10, offset=0, ...)
```

### langgraph.json

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/agent/graph.py:graph"
  },
  "env": ".env",
  "python_version": "3.13"
}
```

## 파라미터

### langgraph.json 주요 키

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `dependencies` | `list[str]` | (필수) | 설치할 패키지 경로/이름. `"."`은 현재 프로젝트(pyproject.toml) |
| `graphs` | `dict[str, str]` | (필수) | 그래프 ID → `"파일경로:변수명"`. 변수는 컴파일된 그래프 또는 그래프를 반환하는 함수 |
| `env` | `str \| dict` | 없음 | `.env` 파일 경로 또는 환경변수 dict |
| `python_version` | `str` | CLI 기본값 | 이미지의 Python 버전 |
| `store` | `dict` | 없음 | 스토어 설정(예: `{"index": {"embed": "openai:text-embedding-3-small", "dims": 1536}}`, TTL) |
| `checkpointer` | `dict` | 없음 | 체크포인트 TTL 등 |
| `auth` | `dict` | 없음 | 커스텀 인증 핸들러 경로 |
| `http` | `dict` | 없음 | 커스텀 FastAPI/Starlette 앱 마운트, CORS 등 |

### runs.stream / runs.wait 주요 인자

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `thread_id` | `str \| None` | (필수, 위치) | `None`이면 상태 없는 일회성 런 |
| `assistant_id` | `str` | (필수, 위치) | 그래프 ID(`langgraph.json`의 키) 또는 어시스턴트 UUID |
| `input` | `dict \| None` | `None` | 그래프 입력 |
| `command` | `dict \| None` | `None` | interrupt 재개 등. 예: `{"resume": "승인"}` |
| `stream_mode` | `str \| list` | `"values"` | `"values"`, `"updates"`, `"messages"`, `"messages-tuple"`, `"custom"`, `"events"`, `"tasks"`, `"checkpoints"`, `"debug"` |
| `context` | `dict \| None` | `None` | 그래프 `context_schema`로 전달할 런타임 컨텍스트 |
| `multitask_strategy` | `str \| None` | `None` | 같은 스레드에 런이 진행 중일 때: `"reject"`, `"interrupt"`, `"rollback"`, `"enqueue"` |
| `on_disconnect` | `str \| None` | `None` | 클라이언트 연결이 끊기면 `"cancel"` 또는 `"continue"` |
| `if_not_exists` | `str \| None` | `None` | 스레드가 없을 때 `"create"` 또는 `"reject"` |

## 메서드와 반환값

| 클라이언트 | 대표 메서드 |
|---|---|
| `client.assistants` | `search`, `get`, `create`, `update`, `get_graph`, `get_schemas` |
| `client.threads` | `create`, `get`, `search`, `get_state`, `update_state`, `get_history`, `delete` |
| `client.runs` | `stream`, `wait`, `create`, `join`, `join_stream`, `cancel`, `list` |
| `client.store` | `put_item`, `get_item`, `search_items`, `delete_item`, `list_namespaces` |

- `runs.stream`은 `StreamPart(event, data, id)`를 비동기로 yield합니다. `event`는 스트림 모드 이름(`"values"`, `"messages/partial"` 등)입니다.
- `api_key`를 생략하면 `LANGGRAPH_API_KEY` → `LANGSMITH_API_KEY` → `LANGCHAIN_API_KEY` 순서로 환경변수에서 읽습니다. `None`을 명시하면 읽지 않습니다.
- `url=None`이면 같은 서버 프로세스 안(인프로세스 ASGI)으로 연결을 시도합니다. 외부에서 호출할 때는 반드시 URL을 넘기세요.

## 예제

```bash
# 프로젝트 루트(langgraph.json 위치)에서
langgraph dev            # 인메모리 개발 서버, 기본 http://127.0.0.1:2024 + Studio 연결
langgraph build -t my-agent   # 프로덕션 Docker 이미지 빌드
```

```python
# src/agent/graph.py — 배포용 그래프: 체크포인터를 넣지 않는다 (서버가 제공)
import os

from langchain.agents import create_agent

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
graph = create_agent(MODEL, tools=[], system_prompt="친절한 상담원")
```

```python
import asyncio

from langgraph_sdk import get_client


async def main() -> None:
    client = get_client(url="http://127.0.0.1:2024")
    thread = await client.threads.create()
    async for part in client.runs.stream(
        thread["thread_id"],
        "agent",  # langgraph.json의 graphs 키
        input={"messages": [{"role": "user", "content": "안녕"}]},
        stream_mode="updates",
    ):
        print(part.event, part.data)

    state = await client.threads.get_state(thread["thread_id"])
    print(state["values"]["messages"][-1]["content"])


asyncio.run(main())
```

## 주의사항

> [!WARNING]
> 배포용 그래프에 `InMemorySaver` 같은 체크포인터를 컴파일해 넣지 마세요. 서버가 Postgres 기반 체크포인터를 주입하므로 무시되거나 충돌합니다. 스토어도 마찬가지로 서버 설정(`langgraph.json`의 `store`)을 사용합니다.

> [!WARNING]
> `langgraph dev`는 인메모리 개발 서버입니다. 재시작하면 스레드가 사라지고 동시성·내구성 보장이 없으므로 프로덕션에는 `langgraph up`/`build` 이미지나 LangSmith Deployment를 사용하세요.

> [!TIP]
> `RemoteGraph(assistant_id, url=...)`(assistant_id는 그래프 ID 또는 어시스턴트 UUID)를 쓰면 배포된 그래프를 로컬 `CompiledStateGraph`처럼 `invoke`/`stream`하고, 다른 그래프의 서브그래프 노드로도 넣을 수 있습니다.

> [!NOTE]
> `langgraph-cli`와 `langgraph-api`는 AgentLab 샌드박스에 설치되어 있지 않으므로 위 CLI·서버 예제는 로컬 PC에서 실행하세요. 설정 키의 전체 목록은 공식 문서의 configuration file 레퍼런스를 확인하세요.

## 관련 문서

- [CompiledStateGraph 메서드](/docs/langgraph/15-compiled-graph)
- [스트리밍 모드](/docs/langgraph/11-streaming)
- [체크포인터](/docs/langgraph/09-checkpointers)
- [Store](/docs/langgraph/10-store)
- [LangSmith](/docs/integrations/04-langsmith)
- [공식 문서: Application structure / langgraph.json](https://docs.langchain.com/langsmith/application-structure)
- [공식 문서: CLI](https://docs.langchain.com/langsmith/cli)
