---
title: "create_agent"
description: "모델 + 도구 + 미들웨어로 도구 호출 루프 에이전트 그래프를 만드는 v1 표준 함수"
order: 6
source: "https://docs.langchain.com/oss/python/langchain/agents"
tags: [agent, create-agent, middleware, react]
---

`create_agent`는 LangChain v1의 표준 에이전트 생성 함수입니다. 모델 노드와 도구 노드를 오가는 루프(ReAct 패턴)를 LangGraph `StateGraph`로 만들고 컴파일한 `CompiledStateGraph`를 반환합니다. 따라서 `invoke`, `stream`, 체크포인터, `interrupt` 등 LangGraph 기능을 그대로 씁니다. 이전 `langgraph.prebuilt.create_react_agent`를 대체합니다.

## Import

```python
from langchain.agents import create_agent, AgentState
```

## 시그니처

```python
def create_agent(
    model: str | BaseChatModel,
    tools: Sequence[BaseTool | Callable[..., Any] | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    response_format: ResponseFormat | type | dict[str, Any] | None = None,
    state_schema: type[AgentState] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
    transformers: Sequence[TransformerFactory] | None = None,
) -> CompiledStateGraph[AgentState, ContextT, InputAgentState, OutputAgentState]
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str \| BaseChatModel` | 필수 | `"openai:gpt-5-mini"` 같은 문자열(내부에서 `init_chat_model`) 또는 모델 인스턴스. |
| `tools` | `Sequence[BaseTool \| Callable \| dict]` | `None` | 도구 목록. 비어 있으면 도구 루프 없이 모델 노드만 생깁니다. dict는 제공자 내장 도구(예: OpenAI 웹 검색). |
| `system_prompt` | `str \| SystemMessage \| None` | `None` | 매 모델 호출 앞에 붙는 시스템 메시지. 상태에 저장되지 않습니다. |
| `middleware` | `Sequence[AgentMiddleware]` | `()` | 훅으로 루프를 확장. 같은 인스턴스를 두 번 넣으면 `AssertionError`. |
| `response_format` | `ToolStrategy \| ProviderStrategy \| type \| dict \| None` | `None` | 구조화 최종 응답. 스키마만 넘기면 모델 지원 여부에 따라 Provider/Tool 전략을 자동 선택. 결과는 `result["structured_response"]`. |
| `state_schema` | `type[AgentState] \| None` | `None` | `AgentState`를 확장한 TypedDict. 커스텀 상태 필드 추가. |
| `context_schema` | `type \| None` | `None` | `invoke(..., context=...)`로 넘길 런타임 컨텍스트 타입(dataclass/TypedDict/Pydantic). |
| `checkpointer` | `Checkpointer \| None` | `None` | 스레드별 대화 기록 저장(단기 메모리). `config={"configurable": {"thread_id": ...}}` 필요. |
| `store` | `BaseStore \| None` | `None` | 스레드를 넘나드는 장기 메모리. |
| `interrupt_before` / `interrupt_after` | `list[str] \| None` | `None` | 지정 노드 전/후 정지(`"model"`, `"tools"`). HITL은 보통 `HumanInTheLoopMiddleware`를 씁니다. |
| `debug` | `bool` | `False` | 실행 단계 상세 로그. |
| `name` | `str \| None` | `None` | 그래프 이름. 서브그래프/멀티 에이전트에서 노드 이름으로 쓰입니다. |
| `cache` | `BaseCache \| None` | `None` | 그래프 노드 캐시. |
| `transformers` | `Sequence[TransformerFactory] \| None` | `None` | 스트림 변환기 팩토리. 순서는 `ToolCallTransformer` → 미들웨어의 `transformers` → 이 인자. |

## 메서드와 반환값

반환값은 `CompiledStateGraph`입니다. 주요 메서드는 [CompiledStateGraph 메서드](/docs/langgraph/15-compiled-graph)를 보세요.

| 상태 키(`AgentState`) | 설명 |
|---|---|
| `messages` | `Annotated[list[AnyMessage], add_messages]`. 입력에 필수. |
| `structured_response` | `response_format`을 지정한 경우의 파싱 결과(출력 전용). |
| `jump_to` | 미들웨어가 쓰는 내부(ephemeral) 필드. |

그래프 노드 이름: `model`, `tools`, 그리고 미들웨어 훅 노드(`<미들웨어이름>.before_model` 등).

## 예제

```python
import os
from langchain.agents import create_agent
from langchain.tools import tool

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


@tool
def get_weather(city: str) -> str:
    """도시의 날씨를 조회한다."""
    return f"{city}: 맑음, 21도"


agent = create_agent(MODEL, tools=[get_weather], system_prompt="너는 날씨 비서다. 짧게 답하라.")
result = agent.invoke(
    {"messages": [{"role": "user", "content": "서울 날씨 어때?"}]},
    config={"recursion_limit": 10},  # 루프 상한
)
for m in result["messages"]:
    m.pretty_print()
```

메모리·구조화 출력·스트리밍:

```python
import os
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.memory import InMemorySaver

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


class Answer(BaseModel):
    summary: str
    confidence: float


# 스키마만 넘기면(response_format=Answer) 모델에 맞는 전략을 자동 선택한다.
# 여기서는 도구 호출 기반 전략을 명시했다.
agent = create_agent(MODEL, tools=[], response_format=ToolStrategy(Answer), checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "t1"}, "recursion_limit": 10}

for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "LangGraph 요약해 줘"}]},
    config,
    stream_mode="updates",
):
    print(list(chunk.keys()))

state = agent.get_state(config)
print(state.values["structured_response"])
```

## 주의사항

> [!WARNING]
> `langgraph.prebuilt.create_react_agent`는 deprecated입니다. v1에서는 `create_agent`를 쓰고, 이전의 `prompt=` 인자는 `system_prompt=`, `pre_model_hook`/`post_model_hook`은 미들웨어(`before_model`/`after_model`)로 옮깁니다.

> [!WARNING]
> 모델이 계속 도구를 호출하면 루프가 끝나지 않습니다. `config={"recursion_limit": N}`을 주거나 `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware`로 상한을 두세요. 한계를 넘으면 `GraphRecursionError`가 납니다.

> [!WARNING]
> 체크포인터와 함께 `response_format`에 직접 정의한 Pydantic 클래스를 쓰면, 상태를 다시 읽을 때 "Deserializing unregistered type … from checkpoint" 경고가 납니다. 앞으로는 기본 차단될 예정이므로(`LANGGRAPH_STRICT_MSGPACK=true`로 미리 차단 가능) `InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=[("모듈", "클래스")]))`처럼 직렬화기(`langgraph.checkpoint.serde.jsonplus`)에 해당 타입을 등록하세요.

> [!TIP]
> 동적으로 모델·도구·프롬프트를 바꾸려면 `create_agent` 인자를 늘리기보다 `wrap_model_call`/`dynamic_prompt` 미들웨어에서 `request.override(...)`를 사용하세요.

## 관련 문서

- [내장 미들웨어](/docs/langchain/07-built-in-middleware)
- [커스텀 미들웨어](/docs/langchain/08-custom-middleware)
- [구조화 출력 전략](/docs/langchain/09-structured-output)
- [ToolRuntime](/docs/langchain/05-tool-runtime)
- [체크포인터](/docs/langgraph/09-checkpointers)
- [스트리밍](/docs/langgraph/11-streaming)
