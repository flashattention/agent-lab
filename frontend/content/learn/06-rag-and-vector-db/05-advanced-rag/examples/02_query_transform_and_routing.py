"""질의 변환(Query Transformation)과 Adaptive RAG 라우팅.

1. Adaptive RAG: 질문 유형에 따라 경로를 고른다 (vectorstore / web_search / direct)
2. 쿼리 분해(Decomposition) / 멀티 쿼리: 복합 질문 → 하위 질문 여러 개 → 각각 검색 → RRF 로 합치기
3. HyDE(Hypothetical Document Embeddings): '가상의 답변 문서'를 만들어 그것으로 검색

Mock 모드에서는 구조화 출력이 더미 값으로 채워집니다. 흐름과 코드 구조에 집중하세요.
"""

import os
from typing import Literal

import numpy as np
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

store = InMemoryVectorStore(embedding=embeddings)
store.add_documents(
    [
        Document(id="py-gil", page_content="파이썬은 GIL 때문에 CPU 바운드 작업에서 멀티스레드 병렬성이 제한된다."),
        Document(id="py-async", page_content="파이썬 asyncio 는 I/O 바운드 작업을 단일 스레드에서 동시에 처리한다."),
        Document(id="go-goroutine", page_content="Go 의 고루틴은 가벼운 스레드로, 채널을 통해 통신하며 멀티코어를 활용한다."),
        Document(id="go-gc", page_content="Go 는 낮은 지연을 목표로 하는 동시성 가비지 컬렉터를 사용한다."),
        Document(id="rust-own", page_content="Rust 는 소유권 시스템으로 데이터 경합을 컴파일 시점에 막는다."),
    ]
)

# ===========================================================================
# 1) Adaptive RAG 라우터
# ===========================================================================
class Route(BaseModel):
    """질문을 처리할 경로."""

    datasource: Literal["vectorstore", "web_search", "direct"] = Field(
        description="사내 기술 문서로 답할 수 있으면 vectorstore, 최신 뉴스/외부 정보면 web_search, 인사·잡담이면 direct"
    )


ROUTER_SYSTEM = (
    "당신은 질문 라우터입니다. vectorstore 에는 프로그래밍 언어의 동시성(파이썬, Go, Rust) 문서가 있습니다. "
    "그 주제면 vectorstore, 최신 소식이면 web_search, 인사나 잡담이면 direct 를 고르세요."
)
router = llm.with_structured_output(Route)

print("=" * 60)
print("1) Adaptive RAG 라우팅")
print("=" * 60)
for q in ["파이썬과 Go 의 동시성 모델 차이는?", "오늘 발표된 Go 최신 버전 뉴스 알려줘", "안녕! 반가워"]:
    route = router.invoke([SystemMessage(ROUTER_SYSTEM), HumanMessage(q)])
    print(f"  {q:32s} → {route.datasource}")
print("  (실제 모델은 질문마다 다른 경로를 고릅니다. 경로마다 다른 파이프라인으로 보내면 Adaptive RAG)")


# ===========================================================================
# 2) 쿼리 분해 + RRF
# ===========================================================================
class SubQuestions(BaseModel):
    """복합 질문을 검색 가능한 하위 질문으로 분해한 결과."""

    sub_questions: list[str] = Field(description="각각 독립적으로 검색 가능한 하위 질문 2~4개", min_length=2)


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


complex_q = "파이썬과 Go 의 동시성 모델 차이는?"
decomposed = llm.with_structured_output(SubQuestions).invoke(
    [HumanMessage(f"다음 질문을 검색용 하위 질문으로 분해하세요: {complex_q}")]
)
# Mock 은 하위 질문을 원문 복사로 채우므로, 실제 모델이 냈을 법한 예시로 보완해 흐름을 보여준다
subs = list(dict.fromkeys(decomposed.sub_questions + ["파이썬 동시성 GIL asyncio", "Go 고루틴 채널 동시성"]))

print("\n" + "=" * 60)
print("2) 쿼리 분해 → 하위 질문별 검색 → RRF")
print("=" * 60)
rankings = []
for sq in subs:
    ids = [d.id for d in store.similarity_search(sq, k=3)]
    rankings.append(ids)
    print(f"  하위 질문: {sq[:30]:30s} → {ids}")
single = [d.id for d in store.similarity_search(complex_q, k=3)]
fused = [i for i, _ in rrf(rankings)[:4]]
print(f"  단일 검색 top-3 : {single}")
print(f"  분해+RRF top-4  : {fused}  ← 파이썬과 Go 양쪽 문서가 고르게 들어오는지 확인")

# ===========================================================================
# 3) HyDE: 가상의 답변을 만들어 그 임베딩으로 검색
# ===========================================================================
print("\n" + "=" * 60)
print("3) HyDE")
print("=" * 60)
question = "Go 는 메모리 관리를 어떻게 하나요?"
hypothetical = llm.invoke(
    [HumanMessage(f"다음 질문에 대한 기술 문서의 한 문단을 그럴듯하게 작성하세요(사실 확인 불필요): {question}")]
).text
print(f"  가상 문서: {hypothetical[:70]!r}...")

# 질문 벡터와 가상 문서 벡터를 평균 내 쓰는 변형도 흔하다(원 질문 의도 보존)
q_vec = np.array(embeddings.embed_query(question))
h_vec = np.array(embeddings.embed_query(hypothetical))
combo = (q_vec + h_vec) / 2
combo = combo / (np.linalg.norm(combo) or 1.0)
hyde_docs = store.similarity_search_by_vector(combo.tolist(), k=2)
print(f"  질문 직접 검색: {[d.id for d in store.similarity_search(question, k=2)]}")
print(f"  HyDE 검색     : {[d.id for d in hyde_docs]}")
print("  → 질문(짧고 의문형)보다 '답변처럼 생긴 글'이 문서 벡터와 더 비슷한 경우가 많다는 아이디어입니다.")
