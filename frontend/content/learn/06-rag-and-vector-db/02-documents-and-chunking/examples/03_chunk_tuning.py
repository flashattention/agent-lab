"""청크 크기/오버랩을 '감'이 아니라 '측정'으로 고르기.

작은 평가셋(질문 → 정답이 들어 있어야 하는 핵심 문구)을 만들고,
여러 (chunk_size, chunk_overlap) 조합마다
  색인 → 검색(top-k) → "정답 문구가 검색 결과에 들어 있나?"(Hit Rate)
를 계산합니다. 같은 평가 틀로 임베딩 모델, k, 분할 전략도 비교할 수 있습니다.
"""

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

handbook = """회사 소개
AgentLab은 2024년에 설립된 AI 교육 회사입니다. 본사는 서울 성수동에 있습니다.

근무 제도
코어 타임은 오전 11시부터 오후 4시까지입니다. 그 외 시간은 자율 출퇴근입니다.
재택 근무는 주 2회까지 가능하며 팀장 승인이 필요합니다.

장비 지원
입사 시 노트북을 지급하며 3년마다 교체합니다. 모니터는 최대 2대까지 신청할 수 있습니다.

교육 지원
연간 200만 원의 교육비를 지원합니다. 도서 구입비는 월 5만 원까지 별도로 지원합니다.
컨퍼런스 참가비는 교육비에서 차감되며 발표자로 참가하면 전액 지원합니다.

보안 수칙
회사 노트북에는 반드시 디스크 암호화를 켭니다. 고객 데이터는 개인 기기에 저장할 수 없습니다.
비밀번호는 90일마다 변경하고 2단계 인증을 사용합니다."""

# 평가셋: (질문, 검색 결과에 반드시 포함돼야 하는 정답 문구)
eval_set = [
    ("재택 근무는 일주일에 몇 번 가능한가요?", "주 2회"),
    ("교육비는 얼마나 지원되나요?", "200만 원"),
    ("도서 구입비 지원 한도는?", "월 5만 원"),
    ("코어 타임이 언제인가요?", "오전 11시"),
    ("비밀번호 변경 주기는?", "90일"),
    ("노트북 교체 주기는?", "3년마다"),
]


def hit_rate(chunk_size: int, chunk_overlap: int, k: int = 2) -> tuple[float, int]:
    """주어진 분할 설정으로 색인하고 평가셋 Hit Rate@k 를 계산한다."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents([Document(page_content=handbook, metadata={"source": "handbook"})])
    store = InMemoryVectorStore(embedding=embeddings)  # 설정마다 새 저장소(독립 실험)
    store.add_documents(chunks)
    hits = 0
    for question, answer in eval_set:
        results = store.similarity_search(question, k=k)
        hits += any(answer in r.page_content for r in results)
    return hits / len(eval_set), len(chunks)


print(f"{'chunk_size':>10} {'overlap':>8} {'청크 수':>6} {'HitRate@2':>10}")
print("-" * 40)
results = []
for size, overlap in [(30, 0), (60, 10), (120, 20), (250, 30), (600, 50)]:
    hr, n = hit_rate(size, overlap)
    results.append((hr, size, overlap))
    print(f"{size:>10} {overlap:>8} {n:>7} {hr:>10.0%}")

best = max(results, key=lambda r: (r[0], -r[1]))  # 동점이면 더 작은 청크(=더 적은 토큰 비용)
print(f"\n이 데이터에서의 최적 후보: chunk_size={best[1]}, overlap={best[2]} (HitRate {best[0]:.0%})")
print("주의: 청크가 크면 Hit Rate는 오르기 쉽지만, LLM에 넣는 토큰(비용·지연)과 잡음도 늘어납니다.")
print("      Hit Rate와 '평균 컨텍스트 길이'를 함께 보고 결정하세요.")
