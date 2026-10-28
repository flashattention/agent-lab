---
title: "Retriever"
description: "BaseRetriever 인터페이스, VectorStoreRetriever, 커스텀 리트리버, 에이전트 도구로 쓰기"
order: 15
source: "https://docs.langchain.com/oss/python/integrations/retrievers"
tags: [retriever, rag, vectorstore, tools]
---

리트리버(Retriever)는 "문자열 질의 → `list[Document]`"를 반환하는 Runnable입니다. 벡터 스토어보다 넓은 개념으로, 키워드 검색(BM25), 웹 검색 API, SQL 조회도 리트리버가 될 수 있습니다. 가장 흔한 형태는 `vectorstore.as_retriever()`가 만드는 `VectorStoreRetriever`입니다.

## Import

```python
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
```

## 시그니처

```python
class BaseRetriever(RunnableSerializable[str, list[Document]], ABC):
    name: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def invoke(self, input: str, config: RunnableConfig | None = None, **kwargs) -> list[Document]
    async def ainvoke(self, input: str, config: RunnableConfig | None = None, **kwargs) -> list[Document]

    # 서브클래스가 구현
    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]
    async def _aget_relevant_documents(self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun) -> list[Document]

class VectorStoreRetriever(BaseRetriever):
    vectorstore: VectorStore
    search_type: str = "similarity"   # "similarity" | "similarity_score_threshold" | "mmr"
    search_kwargs: dict = {}
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `input` / `query` | `str` | 필수 | 검색 질의. |
| `config` | `RunnableConfig \| None` | `None` | 콜백, 태그, 메타데이터. |
| `**kwargs` | | | `invoke` 시 `search_kwargs`를 일시적으로 덮어쓸 수 있습니다(예: `k=2`). |
| `search_type` | `str` | `"similarity"` | (VectorStoreRetriever) 검색 방식. |
| `search_kwargs` | `dict` | `{}` | (VectorStoreRetriever) `k`, `filter`, `score_threshold`, `fetch_k`, `lambda_mult`. |

## 메서드와 반환값

| 메서드 | 반환 |
|---|---|
| `invoke` / `ainvoke` | `list[Document]` |
| `batch` / `abatch` | `list[list[Document]]` |
| `as_tool(name=..., description=...)` | 도구(`BaseTool`). 에이전트에서 검색 도구로 사용. |

## 예제

커스텀 리트리버:

```python
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class KeywordRetriever(BaseRetriever):
    """단어가 겹치는 문서를 점수순으로 반환하는 단순 키워드 리트리버."""

    docs: list[Document]
    k: int = 2

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        words = set(query.lower().split())
        scored = [(len(words & set(d.page_content.lower().split())), d) for d in self.docs]
        return [d for s, d in sorted(scored, key=lambda p: -p[0]) if s > 0][: self.k]


retriever = KeywordRetriever(docs=[
    Document("langgraph checkpointer saves state"),
    Document("qdrant is a vector database"),
    Document("langgraph store keeps long term memory"),
])
print([d.page_content for d in retriever.invoke("langgraph state")])
```

리트리버를 에이전트 도구로:

```python
import os
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

store = InMemoryVectorStore.from_documents(
    [Document("연차는 입사 1년 후 15일이 부여된다."), Document("재택근무는 주 2회 가능하다.")],
    OpenAIEmbeddings(model="text-embedding-3-small"),
)
retriever = store.as_retriever(search_kwargs={"k": 2})


@tool
def search_policy(query: str) -> str:
    """사내 규정 문서를 검색한다."""
    return "\n\n".join(d.page_content for d in retriever.invoke(query))


agent = create_agent(MODEL, tools=[search_policy], system_prompt="규정 질문은 search_policy로 찾아 답하라.")
out = agent.invoke({"messages": [{"role": "user", "content": "연차 규정 알려줘"}]}, {"recursion_limit": 10})
print(out["messages"][-1].text)
```

## 주의사항

> [!WARNING]
> `retriever.get_relevant_documents(query)`는 제거되었습니다. `retriever.invoke(query)`를 쓰세요.

> [!WARNING]
> v1의 `langchain` 패키지에는 `langchain.retrievers` 모듈(`EnsembleRetriever`, `MultiQueryRetriever`, `ContextualCompressionRetriever` 등)이 없습니다. 이들은 `langchain-classic`으로 옮겨졌습니다. 새 코드에서는 LangGraph 노드나 LCEL로 직접 조합하고, 하이브리드 검색은 DB 네이티브 기능(Qdrant/Weaviate/Elasticsearch 등)을 쓰세요.

> [!TIP]
> 도구 반환 문자열에 출처(`metadata["source"]`)를 함께 넣으면 모델이 인용을 붙이기 쉽습니다. 원본 `Document` 리스트는 `response_format="content_and_artifact"`로 artifact에 담아 두면 UI에서 활용할 수 있습니다.

## 관련 문서

- [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)
- [도구](/docs/langchain/04-tools)
- [Runnable과 LCEL](/docs/langchain/11-runnables-lcel)
- [벡터 DB 개념 (하이브리드 검색, 리랭킹)](/docs/vector-db/01-concepts)
