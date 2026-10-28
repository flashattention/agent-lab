---
title: "Runnable과 LCEL"
description: "Runnable 인터페이스, | 파이프, RunnableLambda/Parallel/Passthrough/assign, with_config"
order: 11
source: "https://reference.langchain.com/python/langchain_core/runnables/"
tags: [runnable, lcel, pipe, parallel, passthrough]
---

Runnable은 LangChain의 공통 실행 인터페이스입니다. 모델, 프롬프트, 리트리버, 도구, 컴파일된 LangGraph 그래프가 모두 Runnable이므로 `invoke`/`stream`/`batch`(및 `a*`)를 똑같이 지원합니다. LCEL(LangChain Expression Language)은 `|` 연산자로 Runnable을 이어 `RunnableSequence`를 만드는 문법입니다.

복잡한 분기·루프·상태가 필요하면 LCEL 대신 [LangGraph StateGraph](/docs/langgraph/01-state-graph)를 쓰는 것이 v1의 권장 방식입니다. LCEL은 짧은 선형 파이프라인(프롬프트 → 모델 → 파서, RAG 전처리)에 적합합니다.

## Import

```python
from langchain_core.runnables import (
    Runnable, RunnableLambda, RunnableParallel, RunnablePassthrough, RunnableBranch, RunnableConfig, chain,
)
from langchain_core.output_parsers import StrOutputParser
```

## 시그니처

```python
RunnableLambda(func: Callable, afunc: Callable | None = None, name: str | None = None)
RunnableParallel(steps__: Mapping[str, Runnable | Callable] | None = None, *, name: str | None = None, **kwargs)
RunnablePassthrough(func: Callable | None = None, afunc: Callable | None = None, *,
                    input_type: type | None = None, name: str | None = None)
RunnablePassthrough.assign(**kwargs: Runnable | Callable | Mapping) -> RunnableAssign
RunnableBranch(*branches: tuple[condition, runnable], default: Runnable)

Runnable.pipe(self, *others: Runnable | Callable, name: str | None = None) -> RunnableSerializable
Runnable.with_config(self, config: RunnableConfig | None = None, **kwargs) -> Runnable
Runnable.as_tool(self, args_schema: type[BaseModel] | None = None, *, name: str | None = None,
                 description: str | None = None, arg_types: dict[str, type] | None = None) -> BaseTool

@chain  # 함수를 Runnable로
def my_step(x): ...
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `func` | `Callable` | 필수 | (RunnableLambda) 입력 1개를 받는 함수. `config: RunnableConfig`를 두 번째 인자로 받을 수 있습니다. 제너레이터면 스트리밍. |
| `afunc` | `Callable \| None` | `None` | 비동기 구현. |
| `steps__` / `**kwargs` | `Mapping[str, Runnable \| Callable]` | | (RunnableParallel) 같은 입력을 각 키의 Runnable에 병렬로 넘기고 결과를 dict로 모읍니다. |
| `input_type` | `type \| None` | `None` | (RunnablePassthrough) 입력 스키마 힌트. |
| `config` | `RunnableConfig` | | `tags`, `metadata`, `callbacks`, `run_name`, `max_concurrency`, `recursion_limit`, `configurable`. |

## 메서드와 반환값

| 메서드 | 설명 |
|---|---|
| `a \| b`, `a.pipe(b, c)` | `RunnableSequence`. dict 리터럴은 자동으로 `RunnableParallel`, 함수는 `RunnableLambda`로 변환됩니다. |
| `invoke` / `ainvoke` / `batch` / `abatch` / `stream` / `astream` | 공통 실행 메서드. |
| `stream_events(input, version="v2")` / `astream_events` | 중간 단계 이벤트 스트림. |
| `assign(**kwargs)` | 입력 dict에 키를 추가한 dict를 출력(`RunnablePassthrough.assign`과 동일, 모든 Runnable에서 사용 가능). |
| `pick(keys)` | 출력 dict에서 키만 고르기. |
| `with_config(...)` | 기본 config를 묶은 Runnable. |
| `with_retry(...)` / `with_fallbacks(...)` | [채팅 모델 메서드](/docs/langchain/02-chat-model-methods) 참고. |
| `bind(**kwargs)` | 호출 인자를 고정. |
| `as_tool(...)` | Runnable을 도구로 변환. |
| `get_graph().draw_mermaid()` | 구조 시각화. |

## 예제

```python
import os
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)

docs = {"langgraph": "LangGraph는 상태 기반 그래프 런타임이다.", "qdrant": "Qdrant는 벡터 DB다."}


def retrieve(q: str) -> str:
    return "\n".join(v for k, v in docs.items() if k in q.lower()) or "관련 문서 없음"


prompt = ChatPromptTemplate.from_template("문맥:\n{context}\n\n질문: {question}")

rag_chain = (
    RunnableParallel(context=RunnableLambda(retrieve), question=RunnablePassthrough())
    | prompt
    | llm
    | StrOutputParser()
).with_config(run_name="mini_rag", tags=["docs-example"])

print(rag_chain.invoke("LangGraph가 뭐야?"))
```

`assign`과 `batch`:

```python
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

enrich = RunnablePassthrough.assign(
    length=lambda d: len(d["text"]),
    upper=RunnableLambda(lambda d: d["text"].upper()),
)
print(enrich.batch([{"text": "agent"}, {"text": "graph"}], config={"max_concurrency": 2}))
```

## 주의사항

> [!WARNING]
> `langchain.chains`(`LLMChain`, `RetrievalQA` 등)는 v1에서 제거/레거시(`langchain-classic`)입니다. LCEL이나 LangGraph로 작성하세요.

> [!WARNING]
> `RunnableLambda` 안에서 다른 Runnable을 호출할 때 `config`를 전달하지 않으면 콜백·트레이싱이 끊깁니다. 함수 시그니처에 `config: RunnableConfig`를 받아 `inner.invoke(x, config)`로 넘기세요.

> [!TIP]
> 분기는 `RunnableBranch`보다 "Runnable을 반환하는 `RunnableLambda`"가 읽기 쉽습니다. 반환된 Runnable은 같은 입력으로 자동 실행됩니다.

## 관련 문서

- [프롬프트 템플릿](/docs/langchain/10-prompt-templates)
- [채팅 모델 메서드](/docs/langchain/02-chat-model-methods)
- [Retriever](/docs/langchain/15-retrievers)
- [StateGraph](/docs/langgraph/01-state-graph)
