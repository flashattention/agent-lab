---
title: "임베딩 (Embeddings)"
description: "Embeddings 인터페이스(embed_documents/embed_query)와 init_embeddings, 테스트용 가짜 임베딩"
order: 13
source: "https://docs.langchain.com/oss/python/integrations/text_embedding"
tags: [embeddings, rag, vector, openai]
---

임베딩(Embedding)은 텍스트를 고정 길이 벡터로 바꿉니다. LangChain의 모든 임베딩 클래스는 `Embeddings` 추상 클래스를 구현하므로 벡터 스토어에 그대로 꽂아 쓸 수 있습니다. 문서용(`embed_documents`)과 질의용(`embed_query`) 메서드가 분리되어 있어, 문서/질의에 다른 프롬프트를 쓰는 모델도 같은 인터페이스로 다룹니다.

## Import

```python
from langchain.embeddings import Embeddings, init_embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import DeterministicFakeEmbedding  # 테스트용
```

## 시그니처

```python
class Embeddings(ABC):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def aembed_query(self, text: str) -> list[float]: ...

def init_embeddings(model: str, *, provider: str | None = None, **kwargs) -> Embeddings

DeterministicFakeEmbedding(*, size: int)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model` | `str` | 필수 | (`init_embeddings`) `"openai:text-embedding-3-small"`처럼 `provider:model` 형식. |
| `provider` | `str \| None` | `None` | 접두사 대신 제공자 지정. |
| `**kwargs` | | | 제공자 클래스 생성자 인자(예: OpenAI `dimensions`, `chunk_size`). |
| `size` | `int` | 필수 | (`DeterministicFakeEmbedding`) 벡터 차원. 같은 텍스트 → 같은 벡터(해시 기반). |

OpenAI 임베딩의 세부 파라미터는 [OpenAI Embeddings](/docs/integrations/02-openai-embeddings)를 보세요.

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `embed_documents(texts)` | `list[list[float]]` | 여러 문서를 한 번에(배치) 임베딩. |
| `embed_query(text)` | `list[float]` | 검색 질의 하나를 임베딩. |
| `aembed_documents` / `aembed_query` | 코루틴 | 비동기 버전. 기본 구현은 스레드 실행. |

## 예제

```python
import math
from langchain_openai import OpenAIEmbeddings

emb = OpenAIEmbeddings(model="text-embedding-3-small")

docs = ["LangGraph는 상태 그래프 런타임이다.", "Qdrant는 벡터 데이터베이스다.", "김치찌개 끓이는 법"]
doc_vecs = emb.embed_documents(docs)
q_vec = emb.embed_query("벡터 DB 추천")


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


print("차원:", len(q_vec))
for d, v in sorted(zip(docs, doc_vecs), key=lambda p: -cosine(q_vec, p[1])):
    print(round(cosine(q_vec, v), 3), d)
```

커스텀 임베딩 구현(인터페이스 확인용):

```python
from langchain.embeddings import Embeddings


class CharCountEmbeddings(Embeddings):
    """글자 빈도로 만드는 장난감 임베딩."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(text.count(ch)) for ch in "가나다라마바사abc"]


print(CharCountEmbeddings().embed_query("가나다 abc"))
```

## 주의사항

> [!WARNING]
> 색인할 때와 검색할 때 **같은 모델·같은 차원**을 써야 합니다. 모델을 바꾸면 전체 재색인이 필요합니다. 컬렉션 메타데이터에 모델 이름과 차원을 기록해 두세요.

> [!WARNING]
> `embed_documents`에 수만 건을 한 번에 넣으면 요청 크기·속도 제한에 걸릴 수 있습니다. `OpenAIEmbeddings(chunk_size=...)`로 배치 크기를 조절하거나 직접 나눠 호출하세요.

> [!TIP]
> 동일 텍스트를 반복 임베딩하는 비용을 줄이려면 해시 키로 결과를 캐시하세요. 테스트에서는 네트워크 없이 `DeterministicFakeEmbedding(size=...)`을 쓰면 결과가 결정적입니다.

## 관련 문서

- [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)
- [텍스트 분할기](/docs/langchain/12-text-splitters)
- [OpenAI Embeddings](/docs/integrations/02-openai-embeddings)
- [벡터 DB 개념 (거리 함수)](/docs/vector-db/01-concepts)
