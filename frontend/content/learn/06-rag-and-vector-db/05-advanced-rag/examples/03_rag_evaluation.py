"""RAG 평가: 검색 지표(결정적) + 생성 지표(LLM-as-judge).

검색(Retrieval) 지표 — 정답 문서 id 가 라벨링된 평가셋으로 계산, LLM 불필요
  - Hit Rate@k  : top-k 안에 정답 문서가 하나라도 있나?
  - Recall@k    : 정답 문서들 중 몇 %를 top-k 안에 찾았나? (context recall)
  - MRR         : 첫 정답 문서가 몇 위에 나왔나의 역수 평균 (빨리 나올수록 좋음)
생성(Generation) 지표 — LLM 판정자(judge)로 채점
  - Faithfulness: 답변의 주장들이 컨텍스트에 근거하나? (환각 측정)
  - Correctness : 답변이 기준 정답(reference)과 일치하나?

두 검색 설정(k=1 vs k=3, MMR)을 같은 평가셋으로 비교합니다.
"""

import os

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)

store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(id="leave-annual", page_content="연차는 입사 1년 이상 직원에게 연 15일 부여됩니다."),
        Document(id="leave-half", page_content="반차는 4시간 단위로 사용할 수 있습니다."),
        Document(id="leave-sick", page_content="병가는 연 10일까지 유급이며 3일 이상이면 진단서가 필요합니다."),
        Document(id="remote", page_content="재택 근무는 주 2회까지 가능하며 팀장 승인이 필요합니다."),
        Document(id="edu", page_content="교육비는 연 200만 원, 도서비는 월 5만 원까지 지원합니다."),
        Document(id="device", page_content="노트북은 3년마다 교체하며 모니터는 2대까지 지원합니다."),
    ]
)

# 평가셋: 질문, 정답 문서 id 들(여러 개일 수 있음), 기준 답변
DATASET = [
    {"q": "연차는 며칠인가요?", "relevant": {"leave-annual"}, "reference": "연 15일"},
    {"q": "반차는 몇 시간 단위인가요?", "relevant": {"leave-half"}, "reference": "4시간"},
    {"q": "병가 쓸 때 진단서가 필요한가요?", "relevant": {"leave-sick"}, "reference": "3일 이상이면 필요"},
    {"q": "재택 근무 가능 횟수는?", "relevant": {"remote"}, "reference": "주 2회"},
    {"q": "휴가 종류별 일수를 알려줘 (연차, 병가)", "relevant": {"leave-annual", "leave-sick"}, "reference": "연차 15일, 병가 10일"},
    {"q": "교육비와 도서비 지원 금액은?", "relevant": {"edu"}, "reference": "교육비 연 200만 원, 도서비 월 5만 원"},
]


# ---------------------------------------------------------------------------
# 검색 지표
# ---------------------------------------------------------------------------
def hit_at_k(retrieved: list[str], relevant: set[str]) -> float:
    return float(any(r in relevant for r in retrieved))


def recall_at_k(retrieved: list[str], relevant: set[str]) -> float:
    return len(set(retrieved) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, r in enumerate(retrieved, start=1):
        if r in relevant:
            return 1.0 / rank
    return 0.0


def evaluate_retriever(name: str, search) -> dict:
    rows = [(search(ex["q"]), ex["relevant"]) for ex in DATASET]
    n = len(rows)
    report = {
        "name": name,
        "hit": sum(hit_at_k(r, rel) for r, rel in rows) / n,
        "recall": sum(recall_at_k(r, rel) for r, rel in rows) / n,
        "mrr": sum(reciprocal_rank(r, rel) for r, rel in rows) / n,
    }
    return report


configs = {
    "similarity k=1": lambda q: [d.id for d in store.similarity_search(q, k=1)],
    "similarity k=3": lambda q: [d.id for d in store.similarity_search(q, k=3)],
    "mmr k=3": lambda q: [d.id for d in store.max_marginal_relevance_search(q, k=3, fetch_k=6)],
}
print("=" * 60)
print("1) 검색 지표 (결정적 — CI 에서 회귀 테스트로 돌리기 좋음)")
print("=" * 60)
print(f"{'설정':18s} {'Hit@k':>7} {'Recall@k':>9} {'MRR':>6}")
for name, fn in configs.items():
    r = evaluate_retriever(name, fn)
    print(f"{r['name']:18s} {r['hit']:7.2f} {r['recall']:9.2f} {r['mrr']:6.2f}")
print("→ k=1 은 정답 문서가 2개인 질문에서 Recall 이 깎입니다. k 를 늘리면 Recall↑, 컨텍스트 비용↑.")


# ---------------------------------------------------------------------------
# 생성 지표: LLM-as-judge
# ---------------------------------------------------------------------------
class JudgeResult(BaseModel):
    """채점 결과. 근거(reasoning)를 먼저 쓰게 하면 판정 품질이 올라간다."""

    reasoning: str = Field(description="판정 근거를 한두 문장으로")
    faithfulness_score: int = Field(description="1~10. 답변의 모든 주장이 컨텍스트에 근거하면 10", ge=1, le=10)
    correctness_score: int = Field(description="1~10. 기준 정답과 의미가 일치하면 10", ge=1, le=10)


judge = llm.with_structured_output(JudgeResult)
JUDGE_PROMPT = """당신은 엄격한 RAG 평가자입니다.
[질문] {q}
[검색 컨텍스트] {ctx}
[답변] {answer}
[기준 정답] {reference}
faithfulness: 답변의 주장이 컨텍스트에 있는가(없는 내용을 지어내면 감점)
correctness : 답변이 기준 정답과 일치하는가"""

print("\n" + "=" * 60)
print("2) 생성 지표 (LLM-as-judge, 처음 3문항)")
print("=" * 60)
scores = []
for ex in DATASET[:3]:
    docs = store.similarity_search(ex["q"], k=2)
    ctx = "\n".join(d.page_content for d in docs)
    answer = llm.invoke([HumanMessage(f"컨텍스트만 근거로 답하세요.\n{ctx}\n질문: {ex['q']}")]).text
    result = judge.invoke([HumanMessage(JUDGE_PROMPT.format(q=ex["q"], ctx=ctx, answer=answer, reference=ex["reference"]))])
    scores.append(result)
    print(f"  Q: {ex['q']:24s} faithfulness={result.faithfulness_score:>2} correctness={result.correctness_score:>2}")

avg_f = sum(s.faithfulness_score for s in scores) / len(scores)
avg_c = sum(s.correctness_score for s in scores) / len(scores)
print(f"  평균 faithfulness={avg_f:.1f}, correctness={avg_c:.1f}  (Mock 판정자는 항상 8점을 줍니다)")
