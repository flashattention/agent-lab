---
title: "문서 로더 개요"
description: "Document, BaseLoader, Blob/BaseBlobParser 인터페이스와 커스텀 로더 작성"
order: 16
source: "https://docs.langchain.com/oss/python/integrations/document_loaders"
tags: [document-loaders, document, rag, ingestion]
---

문서 로더(Document Loader)는 파일·웹·DB 같은 원천에서 데이터를 읽어 `Document(page_content, metadata)` 리스트로 바꿉니다. 인터페이스는 `langchain_core.document_loaders`에 있고, 구체 로더(PDF, HTML, Notion 등) 대부분은 `langchain-community`나 파트너 패키지에 있습니다.

이 프로젝트의 강의 코드는 `langchain_community`를 쓰지 않으므로, 로더는 아래 인터페이스로 직접 작성하거나 파일 파싱 라이브러리(예: `pypdf`, `beautifulsoup4`)를 감싸서 씁니다.

## Import

```python
from langchain_core.documents import Document
from langchain_core.document_loaders import BaseLoader, BaseBlobParser, Blob, BlobLoader, LangSmithLoader
```

## 시그니처

```python
class Document(BaseMedia):
    def __init__(self, page_content: str, *, id: str | None = None, metadata: dict = {}) -> None

class BaseLoader(ABC):
    def lazy_load(self) -> Iterator[Document]          # 서브클래스가 구현
    async def alazy_load(self) -> AsyncIterator[Document]
    def load(self) -> list[Document]                   # = list(self.lazy_load())
    async def aload(self) -> list[Document]
    def load_and_split(self, text_splitter: TextSplitter | None = None) -> list[Document]

class Blob(BaseMedia):
    # Blob.from_path(path, *, encoding="utf-8", mime_type=None, guess_type=True, metadata=None)
    # Blob.from_data(data, *, encoding="utf-8", mime_type=None, path=None, metadata=None)
    data: bytes | str | None; mimetype: str | None; encoding: str = "utf-8"; path: str | PurePath | None
    def as_string(self) -> str; def as_bytes(self) -> bytes

class BaseBlobParser(ABC):
    def lazy_parse(self, blob: Blob) -> Iterator[Document]   # 서브클래스가 구현
    def parse(self, blob: Blob) -> list[Document]
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `page_content` | `str` | 필수 | 문서 본문 텍스트. |
| `metadata` | `dict` | `{}` | 출처(`source`), 페이지 번호, 작성일 등. 검색 필터와 인용에 사용. |
| `id` | `str \| None` | `None` | 문서 ID. 벡터 스토어 upsert 키로 쓰입니다. |
| `text_splitter` | `TextSplitter \| None` | `None` | (`load_and_split`) 기본은 `RecursiveCharacterTextSplitter()`. |
| `data` / `path` | `bytes \| str` / 경로 | `None` | (`Blob`) 원시 데이터 또는 파일 경로(지연 로드). |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `lazy_load()` | `Iterator[Document]` | 메모리를 아끼는 스트리밍 로드. 대용량은 이것을 사용. |
| `load()` | `list[Document]` | 전부 메모리로 로드. |
| `load_and_split()` | `list[Document]` | 로드 후 분할. 소스 docstring에서 사실상 deprecated로 표시되어 있으므로 `splitter.split_documents(loader.load())`처럼 분리하세요. |
| `BaseBlobParser.parse(blob)` | `list[Document]` | 바이트 → 문서 변환(로딩과 파싱 분리). |

주요 외부 로더(참고, 별도 패키지):

| 원천 | 패키지/클래스 |
|---|---|
| PDF, Word, HTML 등 범용 | `langchain-unstructured`의 `UnstructuredLoader` |
| PDF | `langchain-community`의 `PyPDFLoader`, 또는 `pypdf` 직접 사용 |
| 웹 페이지 | `langchain-community`의 `WebBaseLoader`, 또는 `httpx` + `beautifulsoup4` |
| LangSmith 데이터셋 | `langchain_core.document_loaders.LangSmithLoader` |

## 예제

커스텀 로더(디렉터리의 `.md` 파일):

```python
import tempfile
from collections.abc import Iterator
from pathlib import Path
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


class MarkdownDirLoader(BaseLoader):
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def lazy_load(self) -> Iterator[Document]:
        for path in sorted(self.root.rglob("*.md")):
            yield Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": str(path.relative_to(self.root))},
                id=str(path.relative_to(self.root)),  # 재색인 시 upsert 키
            )


with tempfile.TemporaryDirectory() as d:
    Path(d, "a.md").write_text("# 휴가 규정\n연차 15일", encoding="utf-8")
    Path(d, "b.md").write_text("# 재택 규정\n주 2회", encoding="utf-8")
    for doc in MarkdownDirLoader(d).lazy_load():
        print(doc.id, doc.metadata, doc.page_content.splitlines()[0])
```

Blob 파서:

```python
from collections.abc import Iterator
from langchain_core.document_loaders import BaseBlobParser, Blob
from langchain_core.documents import Document


class LineParser(BaseBlobParser):
    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        for i, line in enumerate(blob.as_string().splitlines()):
            if line.strip():
                yield Document(line, metadata={"line": i, "source": blob.source})


blob = Blob.from_data("첫 줄\n\n둘째 줄", path="memo.txt")
print(LineParser().parse(blob))
```

## 주의사항

> [!WARNING]
> `langchain_community`는 유지보수 주기가 느리고 의존성이 무거워 이 프로젝트의 실행 예제에서는 금지되어 있습니다. 운영 코드에서도 로더 하나를 위해 전체를 설치하기보다 파트너 패키지나 파싱 라이브러리를 직접 감싸는 편이 안전합니다.

> [!WARNING]
> 웹·PDF 등 외부 문서는 **신뢰할 수 없는 입력**입니다. 문서 안의 "이전 지시를 무시하라" 같은 문장이 프롬프트 인젝션이 될 수 있으므로, 검색 결과를 시스템 프롬프트가 아닌 데이터로 취급하세요.

> [!TIP]
> `metadata["source"]`와 안정적인 `id`를 반드시 채우세요. 인용, 필터링, 재색인 시 중복 제거가 모두 이 값에 의존합니다.

## 관련 문서

- [텍스트 분할기](/docs/langchain/12-text-splitters)
- [VectorStore 인터페이스](/docs/langchain/14-vector-store-interface)
- [Retriever](/docs/langchain/15-retrievers)
