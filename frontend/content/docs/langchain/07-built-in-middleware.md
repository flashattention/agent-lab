---
title: "내장 미들웨어"
description: "langchain.agents.middleware의 내장 미들웨어 전체: 요약, HITL, 호출 제한, 재시도, 대체 모델, PII, 컨텍스트 편집 등"
order: 7
source: "https://docs.langchain.com/oss/python/langchain/middleware/built-in"
tags: [middleware, agent, hitl, summarization, retry, pii, limits]
---

미들웨어(Middleware)는 `create_agent`의 루프(모델 호출 ↔ 도구 실행) 사이에 끼어드는 확장 단위입니다. `create_agent(..., middleware=[...])`에 넘기며, `wrap_*` 훅은 **리스트의 첫 번째가 가장 바깥**을 감쌉니다. 아래는 langchain 1.4.7에 포함된 내장 미들웨어 전체입니다.

## Import

```python
from langchain.agents.middleware import (
    SummarizationMiddleware, HumanInTheLoopMiddleware, InterruptOnConfig,
    ModelCallLimitMiddleware, ToolCallLimitMiddleware,
    ModelRetryMiddleware, ToolRetryMiddleware, ToolErrorMiddleware, ModelFallbackMiddleware,
    PIIMiddleware, RedactionRule, ContextEditingMiddleware, ClearToolUsesEdit,
    TodoListMiddleware, LLMToolSelectorMiddleware, LLMToolEmulator, ProviderToolSearchMiddleware,
    ShellToolMiddleware, HostExecutionPolicy, DockerExecutionPolicy, CodexSandboxExecutionPolicy,
    FilesystemFileSearchMiddleware,
)
```

## 시그니처

요약 표 (각 클래스의 정확한 시그니처는 아래 섹션 참고):

| 미들웨어 | 용도 | 사용 훅 |
|---|---|---|
| `SummarizationMiddleware` | 기록이 길어지면 오래된 메시지를 요약으로 교체 | `before_model` |
| `HumanInTheLoopMiddleware` | 지정 도구 실행 전 사람 승인(interrupt) | `after_model` / `wrap_tool_call` |
| `ModelCallLimitMiddleware` | 스레드/실행당 모델 호출 수 제한 | `before_model`, `after_model` |
| `ToolCallLimitMiddleware` | 도구 호출 수 제한(전체 또는 도구별) | `after_model` |
| `ModelRetryMiddleware` | 모델 호출 실패 시 지수 백오프 재시도 | `wrap_model_call` |
| `ToolRetryMiddleware` | 도구 실행 실패 시 재시도 | `wrap_tool_call` |
| `ToolErrorMiddleware` | 선택한 도구 예외를 오류 `ToolMessage`로 변환 | `wrap_tool_call` |
| `ModelFallbackMiddleware` | 모델 실패 시 대체 모델 순차 시도 | `wrap_model_call` |
| `PIIMiddleware` | 이메일·카드번호 등 PII 탐지 후 차단/가림/마스킹/해시 | `before_model`, `after_model` |
| `ContextEditingMiddleware` | 토큰이 많아지면 오래된 도구 결과 삭제 | `wrap_model_call` |
| `TodoListMiddleware` | `write_todos` 도구와 `todos` 상태 제공 | `wrap_model_call` + 도구 |
| `LLMToolSelectorMiddleware` | 별도 LLM으로 관련 도구만 선별해 바인딩 | `wrap_model_call` |
| `LLMToolEmulator` | 도구를 실제 실행 대신 LLM으로 흉내(테스트용) | `wrap_tool_call` |
| `ProviderToolSearchMiddleware` | 제공자 서버 측 도구 검색으로 도구 스키마 지연 로딩 | `wrap_model_call` |
| `ShellToolMiddleware` | 지속 셸 세션 도구(`shell`) 제공 | 도구 + `before_agent`/`after_agent` |
| `FilesystemFileSearchMiddleware` | `glob_search`, `grep_search` 도구 제공 | 도구 |

## 파라미터

### SummarizationMiddleware

```python
SummarizationMiddleware(
    model: str | BaseChatModel,
    *,
    trigger: ContextSize | TriggerClause | list[ContextSize | TriggerClause] | None = None,
    keep: ContextSize = ("messages", 20),
    token_counter: TokenCounter = count_tokens_approximately,
    summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
    trim_tokens_to_summarize: int | None = 4000,
    summarizer: str | BaseChatModel | Runnable | Callable | None = None,
)
# ContextSize = ("fraction", float) | ("tokens", int) | ("messages", int)
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str \| BaseChatModel` | 필수 | 요약 모델. `summarizer`를 주면 프로필(최대 입력 토큰)·토큰 계산용으로만 쓰입니다. |
| `trigger` | 위 참고 | `None` | 요약 시작 조건. 튜플 하나, `TriggerClause` dict(`{"tokens": 4000, "messages": 10}` → AND), 리스트(OR). `None`이면 요약하지 않습니다. |
| `keep` | `ContextSize` | `("messages", 20)` | 요약 뒤 원문으로 남길 최근 분량. |
| `token_counter` | `Callable` | `count_tokens_approximately` | 토큰 계산 함수. |
| `summary_prompt` | `str` | 내장 프롬프트 | `{messages}` 자리표시자를 포함해야 합니다. |
| `trim_tokens_to_summarize` | `int \| None` | `4000` | 요약 모델에 보낼 메시지 최대 토큰. `None`이면 자르지 않습니다. |
| `summarizer` | 모델/Runnable/함수 | `None` | 요약 생성기를 교체. 함수면 메시지 리스트를 받아 요약 문자열을 반환. |

`max_tokens_before_summary`, `messages_to_keep`는 deprecated입니다(`trigger=("tokens", N)`, `keep=("messages", N)`로 대체).

### HumanInTheLoopMiddleware

```python
HumanInTheLoopMiddleware(
    interrupt_on: dict[str, bool | InterruptOnConfig],
    *,
    description_prefix: str = "Tool execution requires approval",
    edit_notice: str | None = "Note: a human reviewer replaced this tool call before it ran. ...",
    interrupt_mode: Literal["batched", "per_call"] = "batched",
)

class InterruptOnConfig(TypedDict):
    allowed_decisions: list[Literal["approve", "edit", "reject", "respond"]]
    description: NotRequired[str | Callable]   # 정적 문자열 또는 (tool_call, state, runtime) → str
    args_schema: NotRequired[dict]             # 현재 미사용
    when: NotRequired[Callable[[ToolCallRequest], bool]]  # False면 자동 승인
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `interrupt_on` | `dict[str, bool \| InterruptOnConfig]` | 필수 | 도구 이름 → `True`(네 가지 결정 모두 허용), `False`(자동 승인), 또는 설정. 없는 도구는 자동 승인. |
| `description_prefix` | `str` | `"Tool execution requires approval"` | 요청 설명 접두사. |
| `edit_notice` | `str \| None` | 안내 문구 | `edit` 결정으로 바뀐 호출 결과 앞에 붙는 문구. `None`이면 안 붙임. |
| `interrupt_mode` | `"batched" \| "per_call"` | `"batched"` | `batched`: 모델 한 턴의 모든 대상 호출을 interrupt 하나로 묶음(`{"decisions": [...]}`로 재개). `per_call`: 도구 호출마다 interrupt, interrupt ID별 단일 결정으로 재개. |

결정(Decision) 형식: `{"type": "approve"}`, `{"type": "edit", "edited_action": {"name": ..., "args": {...}}}`, `{"type": "reject", "message": "이유"}`, `{"type": "respond", "message": "도구 대신 사람이 준 답"}`.

### ModelCallLimitMiddleware / ToolCallLimitMiddleware

```python
ModelCallLimitMiddleware(*, thread_limit: int | None = None, run_limit: int | None = None,
                         exit_behavior: Literal["end", "error"] = "end")
ToolCallLimitMiddleware(*, tool_name: str | None = None, thread_limit: int | None = None,
                        run_limit: int | None = None,
                        exit_behavior: Literal["continue", "error", "end"] = "continue")
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `thread_limit` | `int \| None` | `None` | 스레드(체크포인터 thread_id) 전체 누적 한도. 체크포인터가 있어야 의미가 있습니다. |
| `run_limit` | `int \| None` | `None` | `invoke` 한 번당 한도. `ModelCallLimitMiddleware`는 `thread_limit`/`run_limit` 중 하나는 필수입니다(없으면 `ValueError`). |
| `tool_name` | `str \| None` | `None` | 특정 도구만 제한. `None`이면 모든 도구 합산. |
| `exit_behavior` (모델) | `"end" \| "error"` | `"end"` | `end`: 한도 초과 안내 AI 메시지를 넣고 종료. `error`: `ModelCallLimitExceededError`. |
| `exit_behavior` (도구) | `"continue" \| "error" \| "end"` | `"continue"` | `continue`: 초과 호출만 오류 ToolMessage로 막고 계속. `error`: `ToolCallLimitExceededError`. `end`: 즉시 종료. |

### ModelRetryMiddleware / ToolRetryMiddleware

```python
ModelRetryMiddleware(*, max_retries: int = 2, retry_on: RetryOn = default_retry_on,
                     on_failure: OnFailure = "continue", backoff_factor: float = 2.0,
                     initial_delay: float = 1.0, max_delay: float = 60.0, jitter: bool = True)
ToolRetryMiddleware(*, max_retries: int = 2, tools: list[BaseTool | str] | None = None,
                    retry_on: RetryOn = default_retry_on, on_failure: OnFailure = "continue",
                    backoff_factor: float = 2.0, initial_delay: float = 1.0,
                    max_delay: float = 60.0, jitter: bool = True)
# RetryOn = tuple[type[Exception], ...] | Callable[[Exception], bool]
# OnFailure = Literal["error", "continue"] | Callable[[Exception], str]
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `max_retries` | `int` | `2` | 최초 시도 이후 추가 재시도 횟수. |
| `tools` | `list \| None` | `None` | (도구) 재시도 대상 도구. `None`이면 전체. |
| `retry_on` | 예외 튜플 또는 판별 함수 | `default_retry_on` | 기본값은 모든 `Exception`을 재시도하되, 제공자 오류가 재시도 불가로 표시되면 제외합니다. |
| `on_failure` | `"continue" \| "error" \| Callable` | `"continue"` | 재시도 소진 후: `continue`는 오류 메시지(AIMessage/ToolMessage)를 넣고 계속, `error`는 예외 전파, 함수면 반환 문자열을 메시지로 사용. |
| `backoff_factor` / `initial_delay` / `max_delay` / `jitter` | | `2.0` / `1.0` / `60.0` / `True` | 지연 = `initial_delay * backoff_factor**n` (최대 `max_delay`), 지터 ±25%. |

### ToolErrorMiddleware

```python
ToolErrorMiddleware(on_error: OnError | None = None, *, aon_error: AOnError | None = None,
                    tools: list[BaseTool | str] | None = None)
# OnError = Callable[[Exception, ToolCallRequest], str | list[ContentBlock] | None]
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `on_error` | `Callable \| None` | `None` | 내용을 반환하면 `ToolMessage(status="error")`로 변환, `None`을 반환하면 예외 전파(opt-in). |
| `aon_error` | `Callable \| None` | `None` | 비동기 경로용. 생략 시 `on_error` 사용. 둘 다 없으면 `ValueError`. |
| `tools` | `list \| None` | `None` | 대상 도구 제한. |

재시도는 하지 않습니다. 함께 쓰려면 `ToolRetryMiddleware(on_failure="error")`를 **안쪽**(리스트에서 뒤)에 둡니다.

### ModelFallbackMiddleware

```python
ModelFallbackMiddleware(first_model: str | BaseChatModel, *additional_models: str | BaseChatModel)
```

기본 모델이 실패하면 `first_model`, 그다음 `additional_models`를 순서대로 시도합니다.

### PIIMiddleware / RedactionRule

```python
PIIMiddleware(
    pii_type: Literal["email", "credit_card", "ip", "mac_address", "url"] | str,
    *,
    strategy: Literal["block", "redact", "mask", "hash"] = "redact",
    detector: Callable[[str], list[PIIMatch]] | str | None = None,
    apply_to_input: bool = True,
    apply_to_output: bool = False,
    apply_to_tool_results: bool = False,
)
RedactionRule(pii_type: str, strategy: RedactionStrategy = "redact", detector: Detector | str | None = None)
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `pii_type` | `str` | 필수 | 내장 탐지기: `email`, `credit_card`, `ip`, `mac_address`, `url`. 그 외 이름은 `detector` 필수. |
| `strategy` | `"block" \| "redact" \| "mask" \| "hash"` | `"redact"` | `block`은 `PIIDetectionError` 발생, `redact`는 `[REDACTED_EMAIL]` 형태, `mask`는 일부만 가림, `hash`는 해시값으로 치환. |
| `detector` | 함수 또는 정규식 문자열 | `None` | 커스텀 탐지기. |
| `apply_to_input` / `apply_to_output` / `apply_to_tool_results` | `bool` | `True` / `False` / `False` | 사용자 입력 / AI 출력 / 도구 결과 검사 여부. |

한 미들웨어는 PII 유형 하나만 다룹니다. 여러 유형은 인스턴스를 여러 개 넣습니다.

### ContextEditingMiddleware / ClearToolUsesEdit

```python
ContextEditingMiddleware(*, edits: Iterable[ContextEdit] | None = None,
                         token_count_method: Literal["approximate", "model"] = "approximate",
                         token_counter: TokenCounter | None = None)
ClearToolUsesEdit(trigger: int = 100000, clear_at_least: int = 0, keep: int = 3,
                  clear_tool_inputs: bool = False, exclude_tools: Sequence[str] = (),
                  placeholder: str = "[cleared]")
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `edits` | `Iterable[ContextEdit] \| None` | `None` → `[ClearToolUsesEdit()]` | 적용할 편집 목록. |
| `token_count_method` | `"approximate" \| "model"` | `"approximate"` | 근사 계산 또는 모델의 토큰 계산 사용. |
| `trigger` | `int` | `100000` | 이 토큰 수를 넘으면 편집. |
| `clear_at_least` | `int` | `0` | 최소로 확보할 토큰 수. |
| `keep` | `int` | `3` | 지우지 않고 남길 최근 도구 결과 수. |
| `clear_tool_inputs` | `bool` | `False` | AI 메시지의 도구 호출 인자도 지울지. |
| `exclude_tools` | `Sequence[str]` | `()` | 지우지 않을 도구. |
| `placeholder` | `str` | `"[cleared]"` | 지운 자리에 넣을 텍스트. |

상태는 바꾸지 않고 **모델에 보내는 요청만** 편집합니다.

### TodoListMiddleware

```python
TodoListMiddleware(*, system_prompt: str = WRITE_TODOS_SYSTEM_PROMPT,
                   tool_description: str = WRITE_TODOS_TOOL_DESCRIPTION)
```

`write_todos` 도구와 `todos: list[{"content", "status"}]` 상태(`pending`/`in_progress`/`completed`)를 추가합니다.

### LLMToolSelectorMiddleware

```python
LLMToolSelectorMiddleware(*, model: str | BaseChatModel | None = None,
                          system_prompt: str = "Your goal is to select the most relevant tools ...",
                          max_tools: int | None = None, always_include: list[str] | None = None,
                          max_retries: int = 1,
                          on_parsing_failure: Literal["error", "none", "all"] | list[str] | Callable = "error")
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str \| BaseChatModel \| None` | `None` | 선택용 모델. `None`이면 에이전트 모델. |
| `max_tools` | `int \| None` | `None` | 최대 선택 수. |
| `always_include` | `list[str] \| None` | `None` | 항상 포함할 도구(`max_tools`에 포함되지 않음). |
| `max_retries` | `int` | `1` | 선택 응답 파싱 실패 시 재시도. |
| `on_parsing_failure` | | `"error"` | 재시도 소진 후: `error`(ValueError), `none`(도구 없음), `all`(전체), 도구 이름 리스트, 함수. |

### LLMToolEmulator

```python
LLMToolEmulator(*, tools: list[str | BaseTool] | None = None, model: str | BaseChatModel | None = None)
```

`tools=None`이면 **모든** 도구를, `[]`이면 아무것도 흉내 내지 않습니다. `model` 기본값은 `"anthropic:claude-sonnet-4-5-20250929"`이므로 OpenAI만 쓰는 환경에서는 반드시 지정하세요.

### ProviderToolSearchMiddleware

```python
ProviderToolSearchMiddleware(*, searchable_tools: list[str | BaseTool] | None = None)
```

지정 도구에 `extras["defer_loading"]=True`를 붙이고 제공자의 서버 측 도구 검색 도구를 주입합니다. 현재 Anthropic과 OpenAI만 지원하며, 지원하지 않는 제공자에서 도구가 지연되면 `ValueError`가 납니다.

### ShellToolMiddleware

```python
ShellToolMiddleware(workspace_root: str | Path | None = None, *,
                    startup_commands: tuple[str, ...] | list[str] | str | None = None,
                    shutdown_commands: tuple[str, ...] | list[str] | str | None = None,
                    execution_policy: BaseExecutionPolicy | None = None,
                    redaction_rules: tuple[RedactionRule, ...] | list[RedactionRule] | None = None,
                    tool_description: str | None = None, tool_name: str = "shell",
                    shell_command: Sequence[str] | str | None = None,
                    env: Mapping[str, Any] | None = None)
```

`execution_policy`: `HostExecutionPolicy(command_timeout=30.0, max_output_lines=100, cpu_time_seconds=None, memory_bytes=None, ...)`, `DockerExecutionPolicy(image="python:3.12-alpine3.19", network_enabled=False, read_only_rootfs=False, ...)`, `CodexSandboxExecutionPolicy(binary="codex", platform="auto", ...)`.

### FilesystemFileSearchMiddleware

```python
FilesystemFileSearchMiddleware(*, root_path: str, use_ripgrep: bool = True, max_file_size_mb: int = 10)
```

`root_path` 아래에서 `glob_search(pattern, path="/")`, `grep_search(...)` 도구를 제공합니다. ripgrep이 없으면 Python 구현으로 대체합니다.

## 메서드와 반환값

미들웨어는 `create_agent`에 넘기는 설정 객체이므로 직접 호출하는 메서드는 없습니다. 각 인스턴스의 `.name`(기본: 클래스 이름)이 그래프 노드 이름(`ModelCallLimitMiddleware.before_model` 등)이 됩니다. 같은 클래스를 여러 개 쓰는 경우(예: PII 여러 유형)에는 내부적으로 이름이 구분됩니다.

## 예제

호출 제한 + 재시도 + PII 가림:

```python
import os
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware, ToolCallLimitMiddleware, ToolRetryMiddleware, PIIMiddleware,
)
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def lookup_order(order_id: str) -> str:
    """주문 번호로 주문 상태를 조회한다."""
    return f"{order_id}: 배송 중"


agent = create_agent(
    MODEL,
    tools=[lookup_order],
    middleware=[
        PIIMiddleware("email", strategy="redact"),
        ModelCallLimitMiddleware(run_limit=5),
        ToolCallLimitMiddleware(tool_name="lookup_order", run_limit=2),
        ToolRetryMiddleware(max_retries=1, initial_delay=0.1),
    ],
)
result = agent.invoke({"messages": [{"role": "user", "content": "a@b.com 고객 주문 A-1 조회해 줘"}]})
print(result["messages"][0].content)  # 이메일이 가려진 사용자 메시지
print(result["messages"][-1].text)
```

사람 승인(HITL)과 재개:

```python
import os
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def send_email(to: str, body: str) -> str:
    """이메일을 보낸다."""
    return f"{to}에게 전송 완료"


agent = create_agent(
    MODEL,
    tools=[send_email],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": {"allowed_decisions": ["approve", "reject"]}})],
    checkpointer=InMemorySaver(),  # interrupt에는 체크포인터 필수
)
config = {"configurable": {"thread_id": "hitl-1"}}

out = agent.invoke({"messages": [{"role": "user", "content": "팀에 회의 메일 보내 줘"}]}, config)
req = out["__interrupt__"][0].value          # HITLRequest
print([a["name"] for a in req["action_requests"]])

out = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config)
print(out["messages"][-1].text)
```

요약:

```python
import os
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

agent = create_agent(
    MODEL,
    middleware=[SummarizationMiddleware(model=MODEL, trigger=("messages", 6), keep=("messages", 2))],
)
history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"메시지 {i}"} for i in range(8)]
result = agent.invoke({"messages": history})
print(len(result["messages"]), result["messages"][0].content[:60])
```

## 주의사항

> [!WARNING]
> `HumanInTheLoopMiddleware`, `thread_limit` 등 상태를 이어 가는 기능은 체크포인터와 `thread_id`가 있어야 동작합니다. 체크포인터 없이 interrupt가 발생하면 재개할 수 없습니다.

> [!WARNING]
> 순서가 중요합니다. `wrap_model_call`/`wrap_tool_call`은 리스트 앞쪽이 바깥입니다. 예: `[ModelFallbackMiddleware(...), ModelRetryMiddleware()]`는 "재시도를 다 해도 실패하면 대체 모델", 반대 순서는 "모델마다 대체 후 전체 재시도"가 됩니다. `per_call` HITL은 재시도/오류 처리 미들웨어보다 **앞에** 두세요.

> [!WARNING]
> `LLMToolEmulator`의 기본 모델은 Anthropic입니다. `langchain-anthropic`이 없거나 키가 없으면 실패하므로 `model=`을 명시하세요.

> [!TIP]
> `SummarizationMiddleware`의 `trigger`를 생략하면 요약이 일어나지 않습니다. 운영에서는 `("fraction", 0.8)`처럼 모델 컨텍스트 비율로 잡으면 모델을 바꿔도 안전합니다(모델 프로필이 필요).

## 관련 문서

- [create_agent](/docs/langchain/06-create-agent)
- [커스텀 미들웨어](/docs/langchain/08-custom-middleware)
- [interrupt와 HITL](/docs/langgraph/08-interrupt)
- [체크포인터](/docs/langgraph/09-checkpointers)
- [deepagents](/docs/integrations/06-deepagents)
