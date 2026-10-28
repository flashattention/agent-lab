---
title: "OpenAIEmbeddings"
description: "OpenAI 임베딩 모델 클래스: model, dimensions, 배치 크기, 토큰 길이 처리"
order: 2
source: "https://docs.langchain.com/oss/python/integrations/text_embedding/openai"
tags: [openai, embeddings, rag]
---

`OpenAIEmbeddings`는 OpenAI 임베딩 API를 LangChain `Embeddings` 인터페이스로 감싼 클래스입니다. 벡터 스토어, `InMemoryStore(index=...)`, 시맨틱 캐시 등 임베딩을 받는 곳에 그대로 넘깁니다. 이 프로젝트의 표준 설정은 `OpenAIEmbeddings(model="text-embedding-3-small")`입니다.

## Import

```python
from langchain_openai import OpenAIEmbeddings      # pip install langchain-openai
from langchain.embeddings import init_embeddings   # 문자열로 생성: init_embeddings("openai:text-embedding-3-small")
```

## 시그니처

```python
OpenAIEmbeddings(
    *,
    model: str = "text-embedding-ada-002",
    dimensions: int | None = None,
    api_key: SecretStr | None | Callable[[], str] | Callable[[], Awaitable[str]] = <env OPENAI_API_KEY>,
    base_url: str | None = <env>,
    organization: str | None = <env>,
    chunk_size: int = 1000,
    embedding_ctx_length: int = 8191,
    check_embedding_ctx_length: bool = True,
    tiktoken_enabled: bool = True,
    tiktoken_model_name: str | None = None,
    max_retries: int = 2,
    timeout: float | tuple[float, float] | Any | None = None,
    retry_min_seconds: int = 4,
    retry_max_seconds: int = 20,
    skip_empty: bool = False,
    show_progress_bar: bool = False,
    model_kwargs: dict[str, Any] = {},
    default_headers: Mapping[str, str] | None = None,
    http_client: Any | None = None,
    # ... deployment, api_version, openai_api_type, openai_proxy, allowed_special,
    #     disallowed_special, headers, default_query, http_async_client
)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str` | `"text-embedding-ada-002"` | 임베딩 모델. 기본값이 구형이므로 **항상 명시**하세요(`text-embedding-3-small`/`-large`) |
| `dimensions` | `int \| None` | `None` | 출력 차원 축소(`text-embedding-3-*`만 지원). `None`이면 모델 기본(small 1536, large 3072) |
| `api_key` | `SecretStr \| Callable` | `OPENAI_API_KEY` | API 키 |
| `base_url` | `str \| None` | 환경변수 | 프록시·호환 서버 주소 |
| `chunk_size` | `int` | `1000` | `embed_documents`에서 한 요청에 묶는 텍스트 수 |
| `embedding_ctx_length` | `int` | `8191` | 텍스트당 최대 토큰. 넘으면 잘라서 임베딩 후 가중 평균 |
| `check_embedding_ctx_length` | `bool` | `True` | 위 길이 검사/분할 수행 여부. OpenAI 호환 서버에서 토크나이저가 다르면 `False` |
| `tiktoken_enabled` | `bool` | `True` | 토큰 계산에 tiktoken 사용. `False`면 HuggingFace 토크나이저 사용 |
| `max_retries` | `int` | `2` | 실패 시 재시도 횟수 |
| `timeout` | `float \| tuple \| None` | `None` | 요청 타임아웃(초) |
| `skip_empty` | `bool` | `False` | 빈 문자열을 건너뛸지 여부(`False`면 오류) |
| `show_progress_bar` | `bool` | `False` | 대량 임베딩 시 진행 표시(tqdm 필요) |
| `model_kwargs` | `dict` | `{}` | 요청에 추가로 보낼 파라미터 |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `embed_documents(texts, chunk_size=None)` | `list[list[float]]` | 여러 문서를 배치로 임베딩 |
| `embed_query(text)` | `list[float]` | 질의 1개 임베딩 |
| `aembed_documents` / `aembed_query` | 같음 | 비동기 버전 |

## 예제

```python
from langchain_openai import OpenAIEmbeddings

emb = OpenAIEmbeddings(model="text-embedding-3-small")

docs = ["LangGraph는 상태 기반 그래프 런타임이다.", "Qdrant는 벡터 데이터베이스다."]
doc_vecs = emb.embed_documents(docs)
q_vec = emb.embed_query("그래프 런타임")
print(len(doc_vecs), "개 문서,", len(q_vec), "차원")
```

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

# 벡터 스토어에 바로 연결
store = InMemoryVectorStore(OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_texts(["사과는 빨갛다", "바나나는 노랗다"])
print(store.similarity_search("노란 과일", k=1)[0].page_content)
```

```python
from langchain_openai import OpenAIEmbeddings

# 차원 축소: 저장 비용 절감 (실제 API에서만 차원이 바뀜)
small = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256)
```

## 주의사항

> [!WARNING]
> 색인할 때와 검색할 때 **같은 모델·같은 `dimensions`**를 써야 합니다. 모델을 바꾸면 기존 벡터와 비교가 무의미해지므로 컬렉션 전체를 다시 임베딩해야 합니다. 벡터 DB 컬렉션의 차원 설정도 맞춰야 합니다.

> [!TIP]
> OpenAI 임베딩은 L2 정규화된 벡터를 반환하므로 코사인 유사도와 내적(dot product)이 같은 순위를 줍니다. 벡터 DB에서는 어느 쪽 거리 함수를 써도 됩니다. 자세한 내용은 [벡터 DB 개념](/docs/vector-db/01-concepts) 참고.

> [!NOTE]
> AgentLab Mock 모드에서는 `OpenAIEmbeddings`가 결정적 해시 기반 가짜 임베딩으로 바뀝니다. 의미적 순위는 기대하지 마세요.

## 관련 문서

- [임베딩 인터페이스](/docs/langchain/13-embeddings)
- [벡터 스토어 인터페이스](/docs/langchain/14-vector-store-interface)
- [Store (InMemoryStore index)](/docs/langgraph/10-store)
- [ChatOpenAI](/docs/integrations/01-openai-chat)
- [공식 문서: OpenAIEmbeddings](https://docs.langchain.com/oss/python/integrations/text_embedding/openai)
