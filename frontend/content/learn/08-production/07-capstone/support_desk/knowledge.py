"""RAG: 정책 문서를 벡터 스토어에 색인하고 검색 도구로 노출한다 (6강 참고).

운영에서는 Qdrant / pgvector 등에 미리 색인해 두고, 여기서는 시작 시 인메모리로 만든다.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from .config import SETTINGS
from .data import POLICY_DOCS


@lru_cache(maxsize=1)
def get_vector_store() -> InMemoryVectorStore:
    """정책 문서 색인 (프로세스당 1회)."""
    store = InMemoryVectorStore(OpenAIEmbeddings(model=SETTINGS.embedding_model))
    store.add_documents([
        Document(page_content=d["text"], metadata={"doc_id": d["id"], "title": d["title"]}) for d in POLICY_DOCS
    ])
    return store


def search_policies(query: str, k: int | None = None) -> list[Document]:
    return get_vector_store().similarity_search(query, k=k or SETTINGS.retrieval_k)


def format_docs(docs: list[Document]) -> str:
    """출처(doc_id)를 붙여 모델이 인용할 수 있게 한다. 외부 데이터임을 경계로 표시(8.3 spotlighting)."""
    body = "\n".join(f"[{d.metadata['doc_id']}] {d.page_content}" for d in docs)
    return f"<policy_documents>\n{body}\n</policy_documents>"
