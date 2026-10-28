"""구조 인식 분할(마크다운 헤더)과 토큰 기반 분할.

1. MarkdownHeaderTextSplitter: 문서 구조(#, ##, ###)를 따라 자르고, 헤더를 메타데이터로 보존
2. 2단계 분할: 헤더로 1차 분할 → 여전히 큰 섹션은 Recursive 로 2차 분할
3. 토큰 기반 분할: LLM/임베딩 모델의 한도는 '글자'가 아니라 '토큰'이므로 토큰으로 길이를 잰다
4. 청크에 '맥락 헤더'를 붙여 검색 품질을 높이는 기법(contextual chunk header)
"""

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

markdown = """# AgentLab 사용자 가이드

## 설치
### macOS
터미널에서 `brew install agentlab`을 실행합니다. Apple Silicon과 Intel 모두 지원합니다.
### Windows
설치 파일을 내려받아 실행합니다. 관리자 권한이 필요할 수 있습니다.

## 요금제
### 무료
월 100회 실행까지 무료입니다. 커뮤니티 지원만 제공합니다.
### 프로
월 2만 원이며 실행 횟수 제한이 없습니다. 이메일 지원을 24시간 이내에 제공합니다. 팀 기능과 SSO, 감사 로그, 전용 실행 환경, 우선 처리 큐를 포함합니다. 연간 결제 시 2개월 무료 혜택이 있습니다.
"""

# ---------------------------------------------------------------------------
# 1) 헤더 기준 분할
# ---------------------------------------------------------------------------
header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,  # 본문에서 헤더 줄은 지우고 메타데이터로만 보관
)
sections = header_splitter.split_text(markdown)
print("=" * 60)
print(f"1) 헤더 기준 분할 → {len(sections)}개 섹션")
print("=" * 60)
for s in sections:
    print(f"  {s.metadata} | {s.page_content[:40]}...")

# ---------------------------------------------------------------------------
# 2) 큰 섹션만 한 번 더 자르기 (메타데이터는 유지된다)
# ---------------------------------------------------------------------------
recursive = RecursiveCharacterTextSplitter(chunk_size=80, chunk_overlap=10)
chunks = recursive.split_documents(sections)
print("\n" + "=" * 60)
print(f"2) 2단계 분할(최대 80자) → {len(chunks)}개 청크")
print("=" * 60)
for c in chunks:
    print(f"  [{c.metadata.get('h2', '-')}/{c.metadata.get('h3', '-')}] {c.page_content}")

# ---------------------------------------------------------------------------
# 3) 맥락 헤더 붙이기: "연간 결제 시 2개월 무료" 청크만 보면 무슨 요금제 이야기인지 모른다!
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("3) 맥락 헤더를 본문 앞에 붙여 임베딩하기")
print("=" * 60)
for c in chunks:
    path = " > ".join(c.metadata[k] for k in ("h1", "h2", "h3") if k in c.metadata)
    c.page_content = f"[{path}]\n{c.page_content}"
print(chunks[-1].page_content)
print("→ 이제 '프로 요금제 할인' 같은 질문이 이 청크와 단어('프로', '요금제')를 공유하게 됩니다.")

# ---------------------------------------------------------------------------
# 4) 토큰 기반 분할 (tiktoken 인코딩 파일을 받을 수 없으면 근사치로 대체)
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("4) 토큰 기반 분할")
print("=" * 60)
try:
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")  # GPT-4o/GPT-5 계열이 쓰는 인코딩

    def count_tokens(text: str) -> int:
        return len(enc.encode(text))

    method = "tiktoken(o200k_base)"
except Exception as exc:  # 오프라인 환경 등
    def count_tokens(text: str) -> int:
        # 한국어는 대략 1~2글자당 1토큰. 학습용 근사치일 뿐 실제 값과 다릅니다.
        return max(1, len(text) * 2 // 3)

    method = f"근사치(tiktoken 사용 불가: {type(exc).__name__})"

sample = "연차는 반차 단위로 나누어 쓸 수 있습니다. Annual leave can be split into half days."
print(f"  측정 방법: {method}")
print(f"  글자 수 {len(sample)} vs 토큰 수 {count_tokens(sample)}")

token_splitter = RecursiveCharacterTextSplitter(
    chunk_size=40,  # 이제 단위는 '토큰'
    chunk_overlap=5,
    length_function=count_tokens,  # 길이 측정 함수를 교체하는 것이 핵심
)
token_chunks = token_splitter.split_text(markdown)
print(f"  최대 40토큰으로 분할 → {len(token_chunks)}개, 각 토큰 수: {[count_tokens(t) for t in token_chunks]}")
