"""Corrective RAG(CRAG) + Self-RAG 식 자기 점검을 LangGraph 로 구현하기.

CRAG : 검색 문서를 '하나씩' 평가 → 쓸만한 것만 남김 → 부족하면 질의를 바꿔 '외부 검색'으로 보강
Self-RAG 식 점검: 답변을 만든 뒤 "컨텍스트에 근거했는가(grounded)?"를 검사 → 아니면 재생성(상한 1회)

    START → retrieve → grade_each → (충분) → generate → check_grounded ─ ok → END
                                   └(부족) → transform_query → web_search ┘     └ 재생성(최대 1회)

외부 웹 검색은 실습 환경에서 네트워크를 쓰지 않도록 가짜 함수(fake_web_search)로 대체합니다.
(현업: Tavily, Bing, 사내 검색 API 등)
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
MIN_SCORE = 0.2  # 1차 결정적 필터
MAX_REGENERATE = 1

store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(page_content="AgentLab 프로 요금제는 월 2만 원이며 실행 횟수 제한이 없습니다.", metadata={"source": "pricing.md"}),
        Document(page_content="AgentLab 무료 요금제는 월 100회 실행까지 가능합니다.", metadata={"source": "pricing.md"}),
        Document(page_content="AgentLab 은 macOS 와 Windows 를 지원합니다.", metadata={"source": "install.md"}),
    ]
)


def fake_web_search(query: str) -> list[Document]:
    """네트워크 없이 동작하는 가짜 웹 검색. 실제로는 Tavily 등 검색 API 를 호출한다."""
    return [Document(page_content=f"(웹 검색 결과) '{query[:40]}' 관련 최신 공개 정보 요약", metadata={"source": "web"})]


class CRAGState(TypedDict):
    question: str
    search_query: str
    documents: list[Document]
    needs_web: bool
    answer: str
    regenerate_count: int


class DocGrade(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="문서가 질문에 답하는 데 도움이 되면 'yes'")


class Grounded(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="답변이 컨텍스트 사실에만 근거하면 'yes'")


def retrieve(state: CRAGState) -> dict:
    hits = store.similarity_search_with_score(state["question"], k=3)
    print(f"[retrieve] {len(hits)}건, 점수={[round(s, 2) for _, s in hits]}")
    # 1차: 점수 임계값으로 명백히 무관한 문서를 걸러낸다 (LLM 호출 절약)
    return {"documents": [d for d, s in hits if s >= MIN_SCORE]}


def grade_each(state: CRAGState) -> dict:
    """2차: 남은 문서를 하나씩 LLM 으로 평가. 관련 문서가 하나도 없으면 외부 검색 필요."""
    grader = llm.with_structured_output(DocGrade)
    kept = []
    for d in state["documents"]:
        prompt = f"질문: {state['question']}\n문서: {d.page_content}\n도움이 되면 'yes', 아니면 'no'."
        if grader.invoke([HumanMessage(prompt)]).binary_score == "yes":
            kept.append(d)
    print(f"[grade_each] 통과 {len(kept)}/{len(state['documents'])}")
    return {"documents": kept, "needs_web": len(kept) == 0}


def decide_after_grade(state: CRAGState) -> Literal["transform_query", "generate"]:
    return "transform_query" if state["needs_web"] else "generate"


def transform_query(state: CRAGState) -> dict:
    """웹 검색에 맞게 질의를 바꾼다(키워드화, 최신성 강조 등)."""
    q = llm.invoke([HumanMessage(f"웹 검색용 키워드 질의로 바꾸세요: {state['question']}")]).text
    print(f"[transform_query] → {q[:50]!r}...")
    return {"search_query": q}


def web_search(state: CRAGState) -> dict:
    web_docs = fake_web_search(state["search_query"])
    print(f"[web_search] {len(web_docs)}건 보강")
    return {"documents": state["documents"] + web_docs}


def generate(state: CRAGState) -> dict:
    context = "\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in state["documents"])
    prompt = f"컨텍스트만 근거로 답하고 출처를 표시하세요.\n질문: {state['question']}\n컨텍스트:\n{context}"
    answer = llm.invoke([HumanMessage(prompt)]).text
    print(f"[generate] (시도 {state.get('regenerate_count', 0) + 1}) {answer[:50]!r}...")
    return {"answer": answer, "regenerate_count": state.get("regenerate_count", 0) + 1}


def check_grounded(state: CRAGState) -> Literal["generate", "__end__"]:
    """Self-RAG 식 점검: 답변이 문서에 근거했는가? 아니면 재생성(상한 있음)."""
    if state["regenerate_count"] > MAX_REGENERATE:
        print("[check_grounded] 재생성 상한 도달 → 종료")
        return END
    context = "\n".join(d.page_content for d in state["documents"])
    verdict = llm.with_structured_output(Grounded).invoke(
        [HumanMessage(f"컨텍스트:\n{context}\n\n답변:\n{state['answer']}\n근거가 있으면 'yes', 지어냈으면 'no'.")]
    )
    print(f"[check_grounded] grounded={verdict.binary_score}")
    return END if verdict.binary_score == "yes" else "generate"


builder = StateGraph(CRAGState)
for fn in (retrieve, grade_each, transform_query, web_search, generate):
    builder.add_node(fn)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "grade_each")
builder.add_conditional_edges("grade_each", decide_after_grade)
builder.add_edge("transform_query", "web_search")
builder.add_edge("web_search", "generate")
builder.add_conditional_edges("generate", check_grounded)
graph = builder.compile()

for q in ["AgentLab 프로 요금제는 월 얼마인가요?", "다음 분기 신규 기능 출시 일정 알려줘"]:
    print("\n" + "=" * 60)
    print(f"질문: {q}")
    print("=" * 60)
    out = graph.invoke({"question": q, "search_query": "", "documents": [], "needs_web": False, "answer": "", "regenerate_count": 0}, {"recursion_limit": 15})
    print(f"→ 사용한 근거: {[d.metadata['source'] for d in out['documents']]}")
