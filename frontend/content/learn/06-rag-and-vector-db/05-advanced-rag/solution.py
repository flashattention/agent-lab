"""정답: RAG 검색 회귀 테스트(품질 게이트) 만들기

청킹이나 임베딩 모델, k 값을 바꿀 때마다 검색 품질이 떨어지지 않았는지 자동으로 확인하는
'품질 게이트'를 만듭니다. CI 에서 돌리는 RAG 회귀 테스트의 축소판입니다.

과제
1. `recall_at_k(retrieved, relevant)`: 정답 문서 중 retrieved 에 포함된 비율 (0.0~1.0)
2. `reciprocal_rank(retrieved, relevant)`: 첫 정답 문서 순위의 역수 (없으면 0.0)
3. `evaluate(search, dataset)`: 평가셋 전체에 대한 평균 {"recall": ..., "mrr": ...} 딕셔너리 반환
   - search 는 질문(str)을 받아 문서 id 리스트를 반환하는 함수
4. `passes_gate(report, thresholds)`: report 의 모든 지표가 thresholds 이상이면 True
"""

from typing import Callable

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(id="vpn", page_content="VPN 접속이 안 되면 OTP 시간을 동기화하세요."),
        Document(id="printer", page_content="프린터 드라이버는 소프트웨어 센터에서 설치합니다."),
        Document(id="laptop-lost", page_content="노트북 분실 시 보안팀에 즉시 신고하세요."),
        Document(id="laptop-swap", page_content="노트북 교체는 3년 주기이며 IT 포털에서 신청합니다."),
        Document(id="password", page_content="비밀번호는 90일마다 변경해야 합니다."),
    ]
)

DATASET = [
    {"q": "VPN 접속이 안 돼요", "relevant": {"vpn"}},
    {"q": "프린터 드라이버 설치 방법", "relevant": {"printer"}},
    {"q": "노트북 분실 신고와 교체 신청", "relevant": {"laptop-lost", "laptop-swap"}},
    {"q": "비밀번호 변경 주기", "relevant": {"password"}},
]


def recall_at_k(retrieved: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def evaluate(search: Callable[[str], list[str]], dataset: list[dict]) -> dict[str, float]:
    recalls, rrs = [], []
    for ex in dataset:
        retrieved = search(ex["q"])
        recalls.append(recall_at_k(retrieved, ex["relevant"]))
        rrs.append(reciprocal_rank(retrieved, ex["relevant"]))
    n = len(dataset)
    return {"recall": sum(recalls) / n, "mrr": sum(rrs) / n}


def passes_gate(report: dict[str, float], thresholds: dict[str, float]) -> bool:
    return all(report.get(metric, 0.0) >= minimum for metric, minimum in thresholds.items())


def search_k1(q: str) -> list[str]:
    return [d.id for d in store.similarity_search(q, k=1)]


def search_k3(q: str) -> list[str]:
    return [d.id for d in store.similarity_search(q, k=3)]


report_k1 = evaluate(search_k1, DATASET)
report_k3 = evaluate(search_k3, DATASET)
print("k=1:", report_k1)
print("k=3:", report_k3)

GATE = {"recall": 0.9, "mrr": 0.7}
print("k=1 게이트 통과:", passes_gate(report_k1, GATE))
print("k=3 게이트 통과:", passes_gate(report_k3, GATE))

# ---------------------------------------------------------------------------
# 자가 채점
# ---------------------------------------------------------------------------
assert recall_at_k(["a", "b"], {"a", "c"}) == 0.5
assert recall_at_k([], {"a"}) == 0.0
assert reciprocal_rank(["x", "a", "b"], {"a", "b"}) == 0.5, "첫 정답이 2위 → 1/2"
assert reciprocal_rank(["x", "y"], {"a"}) == 0.0
fake = evaluate(lambda q: ["vpn", "printer"], DATASET[:2])
assert fake == {"recall": 1.0, "mrr": 0.75}, "평균 recall=1.0, mrr=(1 + 1/2)/2=0.75"
assert passes_gate({"recall": 0.95, "mrr": 0.8}, GATE) is True
assert passes_gate({"recall": 0.95, "mrr": 0.5}, GATE) is False
assert set(report_k1) == {"recall", "mrr"} and set(report_k3) == {"recall", "mrr"}
assert report_k3["recall"] >= report_k1["recall"], "k 를 늘리면 recall 은 줄지 않는다"
assert report_k1["recall"] < 1.0, "정답이 2개인 질문이 있으므로 k=1 의 recall 은 1.0 이 될 수 없다"
print("✅ 모든 테스트 통과!")
