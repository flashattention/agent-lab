---
title: "LangSmith (트레이싱·평가)"
description: "환경변수로 트레이싱 켜기, @traceable, tracing_context, 메타데이터/태그, Client와 evaluate로 오프라인 평가"
order: 4
source: "https://docs.langchain.com/langsmith/home"
tags: [langsmith, tracing, observability, evaluation]
---

LangSmith는 LLM 애플리케이션의 관측성(Observability)·평가(Evaluation) 플랫폼입니다. LangChain/LangGraph 코드는 **환경변수만 설정하면** 모든 모델 호출, 도구 호출, 그래프 노드가 트리 형태의 트레이스(Trace)로 기록됩니다. LangChain 밖의 일반 Python 함수는 `@traceable`로 감싸 같은 트리에 넣습니다. 설치 버전: `langsmith` 0.14.14.

## Import

```python
from langsmith import traceable, tracing_context, Client, evaluate, aevaluate
from langsmith.wrappers import wrap_openai   # 원시 openai SDK 클라이언트 트레이싱
```

## 시그니처

```python
traceable(
    run_type: Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"] = "chain",
    *,
    name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    tags: list[str] | None = None,
    client: Client | None = None,
    reduce_fn: Callable[[Sequence], dict | str] | None = None,
    project_name: str | None = None,
    process_inputs: Callable[[dict], dict] | None = None,
    process_outputs: Callable[..., dict] | None = None,
    process_chunk: Callable | None = None,
    enabled: bool | None = None,
    exceptions_to_handle: tuple[type[BaseException], ...] | None = None,
    dangerously_allow_filesystem: bool = False,
)

tracing_context(*, project_name=None, tags=None, metadata=None, parent=None,
                enabled: bool | Literal["local"] | None = None, client=None, replicas=None, ...)

Client(api_url: str | None = None, *, api_key: str | None = None, timeout_ms=None,
       hide_inputs=None, hide_outputs=None, hide_metadata=None, anonymizer=None,
       auto_batch_tracing: bool = True, ...)

evaluate(target, /, data=None, evaluators=None, summary_evaluators=None, metadata=None,
         experiment_prefix=None, description=None, max_concurrency=0, num_repetitions=1,
         client=None, blocking=True, experiment=None, upload_results=True,
         error_handling: Literal["log", "ignore"] = "log", ...) -> ExperimentResults
```

## 파라미터

### 환경변수

| 변수 | 예시 | 설명 |
|---|---|---|
| `LANGSMITH_TRACING` | `true` | 트레이싱 활성화(구 이름 `LANGCHAIN_TRACING_V2`도 인식) |
| `LANGSMITH_API_KEY` | `lsv2_...` | API 키 |
| `LANGSMITH_PROJECT` | `agentlab-dev` | 트레이스를 모을 프로젝트(없으면 `default`) |
| `LANGSMITH_ENDPOINT` | `https://eu.api.smith.langchain.com` | 기본 US 외 리전·셀프호스트 주소 |

### traceable

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `run_type` | `str` | `"chain"` | UI 표시·집계 기준. `"llm"`이면 토큰/비용 집계 대상 |
| `name` | `str \| None` | 함수명 | run 이름 |
| `metadata` / `tags` | `Mapping` / `list[str]` | `None` | 필터링·검색용 메타데이터와 태그 |
| `project_name` | `str \| None` | `None` | 이 run만 다른 프로젝트로 보냄 |
| `process_inputs` / `process_outputs` | `Callable` | `None` | 기록 전 입력/출력 가공(마스킹, 축약) |
| `reduce_fn` | `Callable` | `None` | 제너레이터 함수의 출력 청크를 하나로 합침 |
| `enabled` | `bool \| None` | `None` | 이 함수 트레이싱 강제 on/off |

### Client 개인정보 옵션

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `hide_inputs` / `hide_outputs` / `hide_metadata` | `bool \| Callable[[dict], dict]` | `None` | `True`면 전부 숨김, 함수면 가공 결과만 전송 |
| `anonymizer` | `Callable[[dict], dict]` | `None` | 모든 run 데이터에 적용할 익명화 함수 |

## 메서드와 반환값

- LangChain Runnable 호출 시 `config`의 `run_name`, `tags`, `metadata`가 트레이스에 그대로 기록됩니다. 예: `agent.invoke(inputs, {"run_name": "support_agent", "tags": ["prod"], "metadata": {"user_id": "u-1"}})`
- `Client.create_dataset(name, *, description=None, ...)` → `Dataset`, `Client.create_examples(*, dataset_name=None, dataset_id=None, examples=[{"inputs": ..., "outputs": ...}])`로 평가 데이터셋을 만듭니다.
- `Client.create_feedback(run_id, key, *, score=None, value=None, comment=None, ...)`로 사용자 피드백(👍/👎 등)을 run에 붙입니다.
- `Client.list_runs(*, project_name=None, run_type=None, filter=None, is_root=None, error=None, limit=None, ...)`로 run을 조회합니다.
- `evaluate(target, data=데이터셋이름, evaluators=[...])` → `ExperimentResults`. evaluator는 `(inputs, outputs, reference_outputs) -> bool | float | dict` 형태의 함수입니다.

## 예제

```python
# .env 또는 셸에서 설정하면 코드 변경 없이 트레이싱된다
# export LANGSMITH_TRACING=true
# export LANGSMITH_API_KEY=lsv2_...
# export LANGSMITH_PROJECT=agentlab-dev
import os

from langchain.chat_models import init_chat_model
from langsmith import traceable

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@traceable(run_type="retriever", name="fake_retriever")
def retrieve(query: str) -> list[str]:
    return [f"{query} 관련 문서 1", f"{query} 관련 문서 2"]


@traceable(name="rag_pipeline", tags=["rag"], metadata={"version": "v1"})
def rag(question: str) -> str:
    docs = retrieve(question)
    # LangChain 호출은 자동으로 rag_pipeline의 하위 run이 된다
    msg = llm.invoke(
        f"문서: {docs}\n질문: {question}",
        config={"tags": ["answer"], "metadata": {"user_id": "u-1"}, "run_name": "answer_llm"},
    )
    return msg.content


print(rag("LangGraph 체크포인터"))
```

```python
from langsmith import Client, evaluate

client = Client()  # LANGSMITH_API_KEY 필요
ds = client.create_dataset("agentlab-qa", description="QA 회귀 테스트")
client.create_examples(
    dataset_id=ds.id,
    examples=[{"inputs": {"question": "2+2?"}, "outputs": {"answer": "4"}}],
)


def target(inputs: dict) -> dict:
    return {"answer": "4"}  # 실제로는 에이전트 호출


def exact_match(outputs: dict, reference_outputs: dict) -> bool:
    return outputs["answer"] == reference_outputs["answer"]


results = evaluate(target, data="agentlab-qa", evaluators=[exact_match],
                   experiment_prefix="baseline", max_concurrency=4)
```

```python
from langsmith import tracing_context

# 특정 구간만 트레이싱 끄기 (민감 데이터 처리 등)
with tracing_context(enabled=False):
    ...
```

## 주의사항

> [!WARNING]
> 트레이스에는 프롬프트·도구 입출력이 **원문 그대로** 저장됩니다. 개인정보·비밀값이 오가는 서비스는 `Client(hide_inputs=..., hide_outputs=..., anonymizer=...)`로 마스킹하세요. 노드 단위로 기록만 바꾸는 LangGraph `TracePolicy`는 비밀값 마스킹 용도가 아니라고 소스에 명시되어 있습니다.

> [!WARNING]
> 트레이스는 백그라운드 스레드가 일괄 전송합니다. 짧게 끝나는 스크립트·서버리스 함수에서는 종료 전에 `Client().flush()`(또는 사용 중인 client의 `flush()`)를 호출하지 않으면 마지막 트레이스가 유실될 수 있습니다.

> [!TIP]
> `metadata`에 `user_id`, `thread_id`, 앱 버전을 넣어 두면 LangSmith에서 사용자별·버전별 필터링과 대시보드 집계가 쉬워집니다. LangGraph는 `thread_id`를 자동으로 메타데이터에 넣어 스레드(Threads) 뷰로 묶어 줍니다.

## 관련 문서

- [Runnable과 LCEL (config)](/docs/langchain/11-runnables-lcel)
- [RetryPolicy / CachePolicy / TimeoutPolicy](/docs/langgraph/16-policies)
- [LangGraph Server 배포](/docs/integrations/05-langgraph-server)
- [공식 문서: LangSmith Observability](https://docs.langchain.com/langsmith/observability)
- [공식 문서: LangSmith Evaluation](https://docs.langchain.com/langsmith/evaluation)
