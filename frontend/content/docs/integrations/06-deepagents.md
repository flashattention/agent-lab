---
title: "deepagents (create_deep_agent)"
description: "파일시스템·서브에이전트·요약 미들웨어가 기본 탑재된 장기 작업용 에이전트 하네스"
order: 6
source: "https://docs.langchain.com/oss/python/deepagents/overview"
tags: [deepagents, subagents, filesystem, harness]
---

`deepagents`는 `create_agent` 위에 장기·다단계 작업용 미들웨어 스택을 미리 조립한 **에이전트 하네스(Harness)**입니다. 가상 파일시스템 도구, `task` 도구를 통한 서브에이전트(Subagent) 위임, 대화 요약, 스킬(Skills)·메모리(AGENTS.md) 로딩을 기본 제공합니다. 반환값은 `create_agent`와 같은 `CompiledStateGraph`이므로 `invoke`/`stream`/체크포인터/interrupt를 그대로 씁니다. 설치 버전: `deepagents` 0.7.32.

## Import

```python
from deepagents import (
    create_deep_agent, SubAgent, CompiledSubAgent, AsyncSubAgent,
    FilesystemPermission, FilesystemMiddleware, SubAgentMiddleware, MemoryMiddleware,
)
from deepagents.backends import (
    StateBackend, FilesystemBackend, StoreBackend, CompositeBackend, LocalShellBackend,
)
from deepagents.backends.utils import create_file_data
```

## 시그니처

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ResponseFormat | type | dict[str, Any] | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str \| BaseChatModel \| None` | `None` | 모델. `None`(기본 `claude-sonnet-4-6`)은 0.5.3부터 deprecated이므로 **항상 명시** |
| `tools` | `Sequence` | `None` | 추가 도구. 내장 도구에 **더해짐**(내장 도구를 빼지 않음) |
| `system_prompt` | `str \| SystemMessage \| None` | `None` | 사용자 지시문. 하네스 프로필의 base/suffix 프롬프트 앞에 붙음 |
| `middleware` | `Sequence[AgentMiddleware]` | `()` | 기본 스택 뒤, 꼬리(tail) 스택 앞에 삽입 |
| `subagents` | `Sequence[SubAgent \| CompiledSubAgent \| AsyncSubAgent]` | `None` | 위임 대상. `general-purpose` 서브에이전트는 지정하지 않아도 자동 추가 |
| `skills` | `list[str] \| None` | `None` | 스킬 디렉터리 경로(POSIX, 백엔드 루트 기준). 예: `["/skills/project/"]` |
| `memory` | `list[str] \| None` | `None` | 시작 시 시스템 프롬프트에 넣을 메모리 파일. 예: `["/memory/AGENTS.md"]` |
| `permissions` | `list[FilesystemPermission] \| None` | `None` | 파일 도구 권한 규칙. 선언 순서대로 첫 일치 규칙 적용, 일치 없으면 허용 |
| `backend` | `BackendProtocol \| None` | `None` → `StateBackend` | 파일 저장소·실행 환경 |
| `interrupt_on` | `dict[str, bool \| InterruptOnConfig] \| None` | `None` | 도구별 HITL 승인. 체크포인터 필요 |
| `response_format` | 스키마/전략 | `None` | 구조화 최종 출력 |
| `state_schema` | `type[DeepAgentState] \| None` | `None` | 커스텀 상태. `DeepAgentState`의 하위 TypedDict여야 함 |
| `context_schema`, `checkpointer`, `store`, `debug`, `name`, `cache` | | | `create_agent`와 동일 |

### SubAgent (TypedDict)

| 키 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `name` | `str` | ✅ | `task` 도구에서 부르는 이름 |
| `description` | `str` | ✅ | 메인 에이전트가 위임 여부를 판단하는 설명 |
| `system_prompt` | `str` | | 서브에이전트 지시문 |
| `tools` | `Sequence` | | 생략 시 메인 에이전트 도구 상속 |
| `model` | `str \| BaseChatModel` | | 모델 재정의 |
| `middleware` | `list[AgentMiddleware]` | | 추가 미들웨어 |
| `interrupt_on` | `dict` | | 생략 시 상위 `interrupt_on` 상속 |
| `skills`, `permissions`, `response_format` | | | 서브에이전트 전용 설정 |
| `mode` | `"isolated" \| "fork"` | | 기본 isolated(작업 설명만 받음). `"fork"`는 부모 대화를 이어받음(실험적) |

`CompiledSubAgent`는 `{"name", "description", "runnable"}`로, 미리 컴파일된 그래프(상태에 `messages` 필수)를 넘깁니다. `AsyncSubAgent`는 `graph_id`(선택 `url`, `headers`)로 원격 LangGraph Server의 그래프를 백그라운드 작업으로 실행합니다.

### 백엔드(Backend)

| 클래스 | 시그니처 | 설명 |
|---|---|---|
| `StateBackend` | `StateBackend()` | 기본값. 파일을 그래프 상태 `files`에 저장(스레드 단위) |
| `FilesystemBackend` | `(root_dir=None, virtual_mode=True, max_file_size_mb=10)` | 실제 디스크. `virtual_mode=True`면 `root_dir` 밖 접근 차단 |
| `StoreBackend` | `(*, namespace: Callable[[Runtime], tuple[str, ...]], store=None)` | LangGraph Store에 저장(스레드 간 영속) |
| `CompositeBackend` | `(default, routes: dict[str, BackendProtocol], *, artifacts_root="/")` | 경로 접두사별로 백엔드 분기. 예: `/memories/` → Store |
| `LocalShellBackend` | `(root_dir=None, *, virtual_mode=True, timeout=120, max_output_bytes=100000, env=None, inherit_env=False)` | 로컬 셸 `execute` 지원. **샌드박스 아님** |

### FilesystemPermission

`FilesystemPermission(operations: list["read" | "write"], paths: list[str], mode: "allow" | "deny" | "interrupt" = "allow")`. `"interrupt"` 규칙이 있으면 `HumanInTheLoopMiddleware`가 자동 설치됩니다.

## 메서드와 반환값

- 내장 도구(0.7.32 실측): `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `execute`, `task`. `execute`는 백엔드가 `SandboxBackendProtocol`을 구현할 때만 실제로 명령을 실행합니다.
- 미들웨어 순서: `FilesystemMiddleware` → `SubAgentMiddleware` → `SummarizationMiddleware` → `PatchToolCallsMiddleware` → (`AsyncSubAgentMiddleware`) → **사용자 middleware** → 프로필 추가 미들웨어 → `SkillsMiddleware` → 프롬프트 캐싱 → `MemoryMiddleware` → `HumanInTheLoopMiddleware` → `UnsupportedContentMiddleware`.
- 결과 상태에는 `messages` 외에 `files`(`{경로: FileData}`) 등이 포함됩니다. `FileData`는 `{"content": str, "encoding": "utf-8" | "base64", "created_at", "modified_at"}`입니다.

## 예제

```python
import os

from deepagents import create_deep_agent
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def search_docs(query: str) -> str:
    """사내 문서를 검색한다."""
    return f"'{query}' 검색 결과: LangGraph는 상태 기반 그래프 런타임이다."


agent = create_deep_agent(
    model=MODEL,
    tools=[search_docs],
    system_prompt="너는 리서치 어시스턴트다. 결과는 /report.md 파일에 정리한다.",
    subagents=[
        {
            "name": "critic",
            "description": "보고서 초안을 검토하고 개선점을 제안한다.",
            "system_prompt": "너는 꼼꼼한 리뷰어다.",
        }
    ],
)
result = agent.invoke(
    {"messages": [{"role": "user", "content": "LangGraph 문서 검색해서 요약해 줘"}]},
    {"recursion_limit": 25},
)
print(result["messages"][-1].content)
```

```python
import os

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.utils import create_file_data
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

agent = create_deep_agent(
    model=MODEL,
    system_prompt="너는 문서 편집 어시스턴트다.",
    permissions=[FilesystemPermission(operations=["write"], paths=["/policies/**"], mode="deny")],
    checkpointer=InMemorySaver(),
)

# 기본 StateBackend: 파일은 그래프 상태의 "files" 키에 산다
result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "/notes.md 파일을 read 해서 요약해 줘"}],
        "files": {"/notes.md": create_file_data("# 회의록\n- 배포는 금요일")},
    },
    {"configurable": {"thread_id": "d1"}, "recursion_limit": 25},
)
print("파일:", list(result["files"]))
```

```python
import os

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain.chat_models import init_chat_model
from langgraph.store.memory import InMemoryStore

# /memories/ 아래만 Store에 저장해 스레드를 넘어 유지
backend = CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(namespace=lambda rt: ("memories",))},
)
# OpenAI 모델은 기본으로 Responses API를 쓴다. Chat Completions를 원하면 모델 객체로 넘긴다
llm = init_chat_model(os.getenv("LAB_MODEL", "openai:gpt-5-mini"), use_responses_api=False)
agent = create_deep_agent(model=llm, backend=backend, store=InMemoryStore())
```

## 주의사항

> [!WARNING]
> 0.7.x 기본 스택에는 `write_todos`(TodoListMiddleware)가 **없습니다**. 이전 버전 문서·예제처럼 계획 도구를 기대한다면 `middleware=[TodoListMiddleware()]`(`langchain.agents.middleware`)를 직접 추가하세요.

> [!WARNING]
> `LocalShellBackend`와 `FilesystemBackend(virtual_mode=False)`는 호스트에서 실제로 명령·파일 작업을 수행합니다. 신뢰할 수 없는 입력을 다루는 에이전트에는 원격 샌드박스 백엔드와 `interrupt_on`/`permissions`를 함께 쓰세요.

> [!TIP]
> 서브에이전트는 기본적으로 격리(isolated)되어 작업 설명만 받고 최종 결과만 돌려줍니다. 메인 컨텍스트가 길어지는 것을 막는 것이 핵심 용도이므로, 검색·분석처럼 중간 출력이 많은 작업을 위임하세요.

> [!NOTE]
> `openai:` 모델 문자열을 넘기면 deepagents는 Responses API를 기본으로 씁니다. Chat Completions 호환 서버를 쓰려면 `init_chat_model(..., use_responses_api=False)`로 만든 모델 객체를 넘기세요.

## 관련 문서

- [create_agent](/docs/langchain/06-create-agent)
- [내장 미들웨어](/docs/langchain/07-built-in-middleware)
- [Store](/docs/langgraph/10-store)
- [interrupt와 HITL](/docs/langgraph/08-interrupt)
- [langgraph-supervisor](/docs/integrations/07-supervisor)
- [공식 문서: Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)
