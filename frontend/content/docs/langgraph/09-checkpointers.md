---
title: "체크포인터 (Checkpointers)"
description: "InMemorySaver, SqliteSaver, AsyncSqliteSaver, PostgresSaver로 스레드별 상태를 영속화"
order: 9
source: "https://docs.langchain.com/oss/python/langgraph/persistence"
tags: [checkpointer, persistence, memory, sqlite, postgres, thread]
---

체크포인터(Checkpointer)는 매 슈퍼스텝의 상태 스냅샷(checkpoint)을 **스레드(thread)** 단위로 저장합니다. 체크포인터가 있어야 다음이 가능합니다.

- 대화 기억(같은 `thread_id`로 이어서 호출)
- [`interrupt`](/docs/langgraph/08-interrupt) / Human-in-the-loop
- 타임 트래블(`get_state_history`, 과거 `checkpoint_id`에서 재실행)
- 장애 복구(실패한 스텝부터 재개)

`compile(checkpointer=...)`(또는 `create_agent(checkpointer=...)`)로 붙이고, 호출마다 `config={"configurable": {"thread_id": "..."}}`를 넘깁니다.

| 구현 | 패키지 | 용도 |
|---|---|---|
| `InMemorySaver` | `langgraph-checkpoint` (기본 포함) | 개발/테스트. 프로세스 종료 시 소멸 |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | 로컬 앱, 단일 프로세스 |
| `AsyncSqliteSaver` | `langgraph-checkpoint-sqlite` (+`aiosqlite`) | async 그래프용 SQLite |
| `PostgresSaver` / `AsyncPostgresSaver` | `langgraph-checkpoint-postgres` | 프로덕션 |

## Import

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
# pip install langgraph-checkpoint-postgres  (이 환경에는 미설치)
from langgraph.checkpoint.postgres import PostgresSaver
```

## 시그니처

```python
InMemorySaver(*, serde: SerializerProtocol | None = None, factory: type[defaultdict] = defaultdict)

SqliteSaver(conn: sqlite3.Connection, *, serde: SerializerProtocol | None = None)
SqliteSaver.from_conn_string(conn_string: str) -> ContextManager[SqliteSaver]

AsyncSqliteSaver(conn: aiosqlite.Connection, *, serde: SerializerProtocol | None = None)
AsyncSqliteSaver.from_conn_string(conn_string: str) -> AsyncContextManager[AsyncSqliteSaver]

# langgraph-checkpoint-postgres
PostgresSaver.from_conn_string(conn_string: str) -> ContextManager[PostgresSaver]
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `serde` | `SerializerProtocol \| None` | `None` | 직렬화기. 기본은 `JsonPlusSerializer`. 암호화가 필요하면 `EncryptedSerializer` |
| `factory` | `type[defaultdict]` | `defaultdict` | (InMemorySaver) 내부 저장소 팩토리 |
| `conn` | `sqlite3.Connection` / `aiosqlite.Connection` | (필수) | 열린 DB 연결. 직접 만들 때 `check_same_thread=False` 권장 |
| `conn_string` | `str` | (필수) | `":memory:"`, 파일 경로, 또는 Postgres URI |

실행 config(`configurable`) 키:

| 키 | 설명 |
|---|---|
| `thread_id` | 대화/세션 식별자. **필수** |
| `checkpoint_id` | 특정 체크포인트에서 이어 실행(타임 트래블·포크) |
| `checkpoint_ns` | 서브그래프 네임스페이스(보통 직접 지정하지 않음) |

## 메서드와 반환값

보통은 그래프 메서드(`get_state`, `get_state_history`)로 접근하지만, 체크포인터를 직접 다룰 수도 있습니다.

| 메서드 | 반환 | 설명 |
|---|---|---|
| `get_tuple(config)` | `CheckpointTuple \| None` | 최신(또는 지정 id) 체크포인트 |
| `list(config, *, filter=None, before=None, limit=None)` | `Iterator[CheckpointTuple]` | 체크포인트 목록(최신순) |
| `put(...)`, `put_writes(...)` | | 그래프가 내부적으로 호출 |
| `delete_thread(thread_id)` | `None` | 스레드의 모든 체크포인트 삭제 |
| `setup()` | `None` | (Sqlite/Postgres) 테이블 생성. Postgres는 최초 1회 **직접 호출 필수** |
| `aget_tuple`, `alist`, `adelete_thread` ... | | 비동기 버전 |

## 예제

### InMemorySaver로 대화 기억

```python
from typing import Annotated, TypedDict
import operator

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START


class State(TypedDict):
    notes: Annotated[list[str], operator.add]


builder = StateGraph(State)
builder.add_node("remember", lambda s: {"notes": [f"turn{len(s['notes']) + 1}"]})
builder.add_edge(START, "remember")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

cfg = {"configurable": {"thread_id": "user-1"}}
graph.invoke({"notes": []}, cfg)
print(graph.invoke({"notes": []}, cfg))                                       # 같은 스레드: 누적
print(graph.invoke({"notes": []}, {"configurable": {"thread_id": "user-2"}}))  # 다른 스레드: 독립

print(len(list(checkpointer.list(cfg))))  # user-1 스레드의 체크포인트 수
checkpointer.delete_thread("user-1")
print(graph.get_state(cfg).values)        # {} : 삭제됨
```

### SqliteSaver (파일 영속화)

```python
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START


class State(TypedDict):
    count: int


builder = StateGraph(State)
builder.add_node("inc", lambda s: {"count": s.get("count", 0) + 1})
builder.add_edge(START, "inc")

# ":memory:" 대신 "checkpoints.db"를 쓰면 프로세스를 재시작해도 유지된다
with SqliteSaver.from_conn_string(":memory:") as saver:
    graph = builder.compile(checkpointer=saver)
    cfg = {"configurable": {"thread_id": "t1"}}
    graph.invoke({"count": 0}, cfg)
    print(graph.get_state(cfg).values)  # {'count': 1}
```

### AsyncSqliteSaver / PostgresSaver (프로덕션)

```python
import asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


async def main(builder):
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as saver:
        graph = builder.compile(checkpointer=saver)
        await graph.ainvoke({"count": 0}, {"configurable": {"thread_id": "t1"}})


# Postgres (langgraph-checkpoint-postgres 설치 필요, 실행 예제 아님)
# from langgraph.checkpoint.postgres import PostgresSaver
# DB_URI = "postgresql://user:pass@localhost:5432/app?sslmode=disable"
# with PostgresSaver.from_conn_string(DB_URI) as saver:
#     saver.setup()          # 최초 1회 테이블 생성
#     graph = builder.compile(checkpointer=saver)
```

## 주의사항

> [!WARNING]
> 체크포인터를 붙였는데 `thread_id`를 빼면 `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id ...`가 발생합니다.

> [!WARNING]
> `InMemorySaver`는 프로세스 메모리에만 저장됩니다. 멀티 워커/재시작 환경에서는 대화가 사라지니 프로덕션에서는 Postgres 계열을 쓰세요. async 그래프(`ainvoke`, `astream`)에는 `SqliteSaver` 대신 `AsyncSqliteSaver`를 써야 합니다.

> [!TIP]
> LangGraph Server(배포 환경)는 체크포인터를 자동으로 제공합니다. 배포용 그래프에는 체크포인터를 직접 붙이지 마세요([LangGraph Server](/docs/integrations/05-langgraph-server)).

> [!TIP]
> 체크포인트 저장 시점은 [durability 모드](/docs/langgraph/19-durability)로 조절합니다.

## 관련 문서

- [CompiledStateGraph: get_state / get_state_history / update_state](/docs/langgraph/15-compiled-graph)
- [Store (장기 기억)](/docs/langgraph/10-store)
- [interrupt](/docs/langgraph/08-interrupt)
- [durability 모드](/docs/langgraph/19-durability)
- [서브그래프의 체크포인터](/docs/langgraph/14-subgraphs)
