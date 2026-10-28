"""정답: 검색 친화적인 청킹 파이프라인 만들기

사내 FAQ 마크다운을 받아 RAG 색인용 청크 리스트를 만드는 `build_chunks()`를 완성하세요.

요구사항
1. MarkdownHeaderTextSplitter 로 `##`(h2), `###`(h3) 헤더 기준 1차 분할
2. RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=10) 로 2차 분할
3. 각 청크 metadata 에 다음을 추가
   - "source": 함수 인자로 받은 source
   - "chunk_id": f"{source}#{순번}"  (순번은 0부터)
4. 각 청크 본문 앞에 맥락 헤더를 붙입니다: "[h2 > h3]\n" + 원래 본문
   (h3 가 없으면 "[h2]\n")

마지막 부분은 InMemoryVectorStore 에 색인하고 검색까지 해 봅니다.
"""

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

CHUNK_SIZE = 100

FAQ = """## 주문
### 주문 취소
결제 후 1시간 이내에는 마이페이지에서 직접 주문을 취소할 수 있습니다. 1시간이 지나면 고객센터로 연락해 주세요.
### 주문 변경
배송 준비 전까지 옵션과 주소를 변경할 수 있습니다.

## 환불
### 환불 기간
상품 수령 후 7일 이내에 환불을 신청할 수 있습니다. 단순 변심은 왕복 배송비 6,000원이 차감됩니다. 상품 하자는 배송비를 회사가 부담합니다.
### 환불 처리
환불 금액은 카드사 사정에 따라 3~5 영업일 후에 돌아옵니다.

## 배송
평균 2일이 걸리며 제주와 도서산간은 하루가 더 걸립니다.
"""


def build_chunks(markdown: str, source: str) -> list[Document]:
    # 1) 헤더 기준 1차 분할: 헤더는 메타데이터로 이동한다
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "h2"), ("###", "h3")])
    sections: list[Document] = header_splitter.split_text(markdown)

    # 2) 길이 기준 2차 분할: 메타데이터는 그대로 복사된다
    recursive = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=10)
    chunks: list[Document] = recursive.split_documents(sections)

    # 3, 4) 출처/식별자 메타데이터 + 맥락 헤더
    for i, c in enumerate(chunks):
        c.metadata["source"] = source
        c.metadata["chunk_id"] = f"{source}#{i}"
        path = " > ".join(c.metadata[k] for k in ("h2", "h3") if k in c.metadata)
        c.page_content = f"[{path}]\n{c.page_content}"

    return chunks


chunks = build_chunks(FAQ, source="faq.md")
for c in chunks:
    print(c.metadata.get("chunk_id"), "|", c.page_content.replace("\n", " ⏎ "))

store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(chunks)
top = store.similarity_search("환불 기간은 며칠인가요?", k=2)
print("\n검색 결과:", [d.metadata.get("chunk_id") for d in top])

# ---------------------------------------------------------------------------
# 자가 채점
# ---------------------------------------------------------------------------
assert len(chunks) >= 5, "헤더 + 길이 기준으로 최소 5개 청크가 나와야 합니다"
for i, c in enumerate(chunks):
    assert c.metadata.get("source") == "faq.md", "source 메타데이터가 필요합니다"
    assert c.metadata.get("chunk_id") == f"faq.md#{i}", "chunk_id 형식은 'faq.md#0' 입니다"
    assert "h2" in c.metadata, "헤더 메타데이터(h2)가 보존돼야 합니다"
    header, _, body = c.page_content.partition("\n")
    assert header.startswith("[") and header.endswith("]"), "본문 앞에 [h2 > h3] 맥락 헤더가 있어야 합니다"
    assert c.metadata["h2"] in header
    assert len(body) <= CHUNK_SIZE, "맥락 헤더를 뺀 본문은 CHUNK_SIZE 이하여야 합니다"
assert any(c.metadata.get("h3") is None and c.page_content.startswith("[배송]\n") for c in chunks), "h3 가 없으면 [h2] 형식"
assert any("환불" in d.metadata.get("h2", "") for d in top), "환불 질문에 환불 섹션 청크가 검색돼야 합니다"
print("✅ 모든 테스트 통과!")
