"""Document 객체와 RecursiveCharacterTextSplitter 기초.

- Document = page_content(본문) + metadata(출처, 날짜, 권한 등) + id
- RecursiveCharacterTextSplitter 는 "문단 → 줄 → 문장 → 단어" 순으로 자연스러운 경계에서 자른다.
- chunk_overlap 은 경계에 걸친 정보를 보존하고, add_start_index 는 원문 내 위치를 기록한다.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# 1) Document 만들기: 본문 + 메타데이터
# ---------------------------------------------------------------------------
policy_text = """제1조 (목적)
이 규정은 임직원의 휴가 사용에 관한 사항을 정한다.

제2조 (연차 휴가)
입사 1년 이상 직원은 연 15일의 연차를 받는다. 3년 이상 근속 시 2년마다 1일씩 가산한다.
연차는 반차(4시간) 단위로 나누어 쓸 수 있다. 반차는 오전 반차와 오후 반차로 구분한다.

제3조 (병가)
병가는 연 10일까지 유급으로 사용할 수 있다. 3일 이상 연속 사용 시 진단서를 제출한다.

제4조 (경조 휴가)
본인 결혼 5일, 자녀 결혼 1일, 배우자 출산 10일의 경조 휴가를 준다."""

doc = Document(
    page_content=policy_text,
    metadata={
        "source": "hr/vacation-policy.md",  # 출처: 답변에 인용(citation)할 때 필요
        "department": "HR",  # 필터 검색용
        "updated_at": "2026-03-01",  # 최신성 판단용
        "access": "all-employees",  # 권한 필터용 (보안!)
    },
)
print(f"원문 길이: {len(doc.page_content)}자, 메타데이터: {doc.metadata}")

# ---------------------------------------------------------------------------
# 2) 재귀 분할: separators 순서대로 시도하다가 chunk_size 를 넘으면 다음 구분자로 더 잘게
# ---------------------------------------------------------------------------
splitter = RecursiveCharacterTextSplitter(
    chunk_size=120,  # 청크 최대 길이 (기본 length_function=len → 글자 수)
    chunk_overlap=20,  # 이웃 청크와 겹치는 길이
    separators=["\n\n", "\n", ". ", " ", ""],  # 기본값과 거의 같음: 문단 → 줄 → 문장 → 단어 → 글자
    add_start_index=True,  # metadata["start_index"] 에 원문 내 시작 위치 기록
)
chunks = splitter.split_documents([doc])  # 메타데이터가 모든 청크에 복사된다

print("\n" + "=" * 60)
print(f"chunk_size=120, overlap=20 → {len(chunks)}개 청크")
print("=" * 60)
for i, c in enumerate(chunks):
    preview = c.page_content.replace("\n", " ⏎ ")
    print(f"[{i}] start={c.metadata['start_index']:>3} len={len(c.page_content):>3} | {preview}")

assert all(c.metadata["source"] == "hr/vacation-policy.md" for c in chunks)
print("\n✔ 모든 청크가 원본 메타데이터(source 등)를 물려받았습니다 → 출처 인용과 필터가 가능")

# ---------------------------------------------------------------------------
# 3) 청크 크기에 따른 변화 비교
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("청크 크기별 비교")
print("=" * 60)
for size, overlap in [(60, 0), (120, 20), (300, 30)]:
    s = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    parts = s.split_text(policy_text)
    avg = sum(map(len, parts)) / len(parts)
    print(f"  size={size:>3}, overlap={overlap:>2} → 청크 {len(parts):>2}개, 평균 {avg:5.1f}자")

# 너무 작은 청크의 문제: 문맥이 끊긴다
tiny = RecursiveCharacterTextSplitter(chunk_size=40, chunk_overlap=0).split_text(policy_text)
print("\n너무 작게 자르면 이런 청크가 생깁니다(무슨 휴가 이야기인지 알 수 없음):")
print("  →", next(t for t in tiny if t.startswith("연차는")))
