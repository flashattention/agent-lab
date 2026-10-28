---
title: "텍스트 분할기"
description: "langchain_text_splitters: RecursiveCharacterTextSplitter, 토큰 기반 분할, Markdown 헤더 분할"
order: 12
source: "https://docs.langchain.com/oss/python/integrations/splitters"
tags: [rag, text-splitter, chunking, documents]
---

텍스트 분할기(Text Splitter)는 긴 문서를 임베딩·검색에 알맞은 청크(chunk)로 나눕니다. 별도 패키지 `langchain-text-splitters`(설치 버전 1.1.3)에 있습니다. 대부분의 경우 `RecursiveCharacterTextSplitter`로 시작합니다. 이 분할기는 `["\n\n", "\n", " ", ""]` 순서로 구분자를 시도하며 문단 → 줄 → 단어 단위로 점점 잘게 자릅니다.

## Import

```python
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter, CharacterTextSplitter, TokenTextSplitter,
    MarkdownHeaderTextSplitter, Language,
)
```

## 시그니처

```python
TextSplitter(chunk_size: int = 4000, chunk_overlap: int = 200,
             length_function: Callable[[str], int] = len,
             keep_separator: bool | Literal["start", "end"] = False,
             add_start_index: bool = False, strip_whitespace: bool = True)

RecursiveCharacterTextSplitter(separators: list[str] | None = None,
                               keep_separator: bool | Literal["start", "end"] = True,
                               is_separator_regex: bool = False, **kwargs)  # kwargs → TextSplitter
RecursiveCharacterTextSplitter.from_language(language: Language, **kwargs)
RecursiveCharacterTextSplitter.from_tiktoken_encoder(encoding_name: str = "gpt2", model_name: str | None = None,
                                                     allowed_special=None, disallowed_special="all", **kwargs)

CharacterTextSplitter(separator: str = "\n\n", is_separator_regex: bool = False, **kwargs)
TokenTextSplitter(encoding_name: str = "gpt2", model_name: str | None = None, ..., **kwargs)
MarkdownHeaderTextSplitter(headers_to_split_on: list[tuple[str, str]], return_each_line: bool = False,
                           strip_headers: bool = True, custom_header_patterns: dict[str, int] | None = None)
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `chunk_size` | `int` | `4000` | 청크 최대 길이(`length_function` 단위). |
| `chunk_overlap` | `int` | `200` | 인접 청크가 겹치는 길이. `chunk_size`보다 작아야 합니다. |
| `length_function` | `Callable[[str], int]` | `len` | 길이 계산 함수(기본 문자 수). 토큰 단위는 `from_tiktoken_encoder` 사용. |
| `keep_separator` | `bool \| "start" \| "end"` | `False`(Recursive는 `True`) | 구분자를 청크에 남길지, 앞/뒤 어디에 붙일지. |
| `add_start_index` | `bool` | `False` | `metadata["start_index"]`에 원문 내 시작 위치 기록. |
| `strip_whitespace` | `bool` | `True` | 청크 앞뒤 공백 제거. |
| `separators` | `list[str] \| None` | `None` → `["\n\n", "\n", " ", ""]` | (Recursive) 시도할 구분자 순서. |
| `is_separator_regex` | `bool` | `False` | 구분자를 정규식으로 해석. |
| `language` | `Language` | | (`from_language`) `Language.PYTHON`, `Language.MARKDOWN`, `Language.JS` 등 언어별 구분자. |
| `encoding_name` / `model_name` | `str` | `"gpt2"` / `None` | tiktoken 인코딩. OpenAI 최신 모델은 `encoding_name="o200k_base"` 또는 `model_name` 지정. |
| `headers_to_split_on` | `list[tuple[str, str]]` | 필수 | (Markdown) `[("#", "h1"), ("##", "h2")]` → 헤더 값을 메타데이터 키에 저장. |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `split_text(text)` | `list[str]` | 문자열 분할. |
| `create_documents(texts, metadatas=None)` | `list[Document]` | 문자열 리스트 → 청크 `Document`(메타데이터 복사). |
| `split_documents(documents)` | `list[Document]` | `Document` 리스트 분할(메타데이터 유지). |
| `MarkdownHeaderTextSplitter.split_text(text)` | `list[Document]` | 헤더 구조를 메타데이터로 가진 문서. 길이 제한은 없으므로 이후 Recursive로 한 번 더 나눕니다. |

## 예제

```python
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

text = "LangGraph는 상태 그래프 런타임이다.\n\n" * 5 + "체크포인터는 상태를 저장한다. " * 20
splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=40, add_start_index=True)

chunks = splitter.split_documents([Document(page_content=text, metadata={"source": "guide.md"})])
for c in chunks[:3]:
    print(len(c.page_content), c.metadata)
```

토큰 기준 분할과 Markdown 헤더 분할:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

md = "# 설치\npip install langgraph\n## 요구 사항\nPython 3.10+\n# 사용법\nStateGraph를 만든다."
by_header = MarkdownHeaderTextSplitter([("#", "h1"), ("##", "h2")]).split_text(md)
for d in by_header:
    print(d.metadata, "|", d.page_content)

token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="o200k_base", chunk_size=50, chunk_overlap=10
)
print(len(token_splitter.split_text("토큰 단위로 자르기 " * 50)))
```

## 주의사항

> [!WARNING]
> `chunk_size`는 기본적으로 **문자 수**입니다. 임베딩 모델의 토큰 한도(예: 8191 토큰)를 넘지 않게 하려면 토큰 기반 분할(`from_tiktoken_encoder`)을 쓰세요. 한국어는 문자 수 대비 토큰 수가 영어보다 많습니다.

> [!WARNING]
> 하나의 구분자 조각이 `chunk_size`보다 길면 경고와 함께 더 긴 청크가 나올 수 있습니다(`CharacterTextSplitter`). 재귀 분할기는 더 작은 구분자로 내려가 이 문제를 줄입니다.

> [!TIP]
> 검색 품질은 청크 크기에 크게 좌우됩니다. 일반 문서는 500~1,000자, overlap 10~20%에서 시작해 평가 데이터로 조정하세요.

## 관련 문서

- [문서 로더](/docs/langchain/16-document-loaders)
- [임베딩](/docs/langchain/13-embeddings)
- [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)
- [벡터 DB 개념](/docs/vector-db/01-concepts)
