"""LangGraph 로 Agentic RAG 직접 만들기.

흐름: 검색 결정 → 검색 → 관련성 평가 → (관련 없음) 질의 재작성 → 다시 검색 … → 답변 생성

    START → generate_query_or_respond ─(도구 호출?)─ 예 → retrieve → grade ─ yes → generate_answer → END
                    ▲                  └ 아니오 → END                 └ no → rewrite_question ┐
                    └─────────────────────────────────────────────────────────────────────┘
재작성 루프에는 반드시 상한(MAX_REWRITES)을 둡니다.
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_REWRITES = 2  # 질의 재작성 최대 횟수 (무한 루프 방지 + 비용 상한)
MIN_SCORE = 0.15  # 이 점수 미만 문서는 버린다 (자기 데이터로 정할 것)

llm = init_chat_model(MODEL)

# ---------------------------------------------------------------------------
# 지식 베이스 + 검색 도구
# ---------------------------------------------------------------------------
store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(page_content="LangGraph 의 체크포인터는 그래프 상태를 스레드별로 저장해 대화 기억과 재개를 가능하게 한다.", metadata={"source": "docs/persistence.md"}),
        Document(page_content="LangGraph 의 interrupt 는 실행을 멈추고 사람의 승인을 기다리는 Human-in-the-loop 기능이다.", metadata={"source": "docs/hitl.md"}),
        Document(page_content="LangGraph 의 Send API 는 같은 노드를 여러 입력으로 병렬 실행하는 map-reduce 를 만든다.", metadata={"source": "docs/send.md"}),
    ]
)


@tool(response_format="content_and_artifact")
def search_langgraph_docs(query: str) -> tuple[str, list[Document]]:
    """LangGraph 공식 문서를 검색합니다. 체크포인터, interrupt, Send 등 LangGraph 기능 질문에 사용하세요.

    Args:
        query: 검색 질의
    """
    hits = [(d, s) for d, s in store.similarity_search_with_score(query, k=2) if s >= MIN_SCORE]
    docs = [d for d, _ in hits]
    if not docs:
        return "관련 문서를 찾지 못했습니다.", []
    return "\n\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs), docs


tools = [search_langgraph_docs]


# ---------------------------------------------------------------------------
# 상태: 메시지 + 재작성 횟수
# ---------------------------------------------------------------------------
class RAGState(MessagesState):
    rewrite_count: int


def original_question(state: RAGState) -> str:
    """가장 최근 사용자(Human) 메시지 = 현재 처리 중인 질문(재작성됐다면 재작성본)."""
    return next(m.text for m in reversed(state["messages"]) if m.type == "human")


# ---------------------------------------------------------------------------
# 노드 1: 검색할지 / 바로 답할지 결정
# ---------------------------------------------------------------------------
def generate_query_or_respond(state: RAGState) -> dict:
    response = llm.bind_tools(tools).invoke(state["messages"])
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# 조건 엣지: 검색 결과 관련성 평가 → 다음 노드 이름 반환
# ---------------------------------------------------------------------------
class GradeDocuments(BaseModel):
    """검색 문서의 관련성 판정."""

    binary_score: Literal["yes", "no"] = Field(description="문서가 질문과 관련 있으면 'yes', 아니면 'no'")


GRADE_PROMPT = (
    "당신은 검색 결과의 관련성을 평가하는 채점자입니다.\n"
    "문서: {context}\n\n질문: {question}\n"
    "문서에 질문과 관련된 키워드나 의미가 있으면 'yes', 아니면 'no' 로 답하세요."
)


def grade_documents(state: RAGState) -> Literal["generate_answer", "rewrite_question"]:
    last = state["messages"][-1]  # retrieve 노드가 만든 ToolMessage
    if state.get("rewrite_count", 0) >= MAX_REWRITES:
        print(f"   ↳ [grade] 재작성 상한({MAX_REWRITES}) 도달 → 있는 정보로 답변")
        return "generate_answer"
    if not getattr(last, "artifact", None):  # 결정적 가드: 문서가 0건이면 LLM 을 부를 필요도 없다
        print("   ↳ [grade] 검색 결과 0건 → 질의 재작성")
        return "rewrite_question"
    prompt = GRADE_PROMPT.format(context=last.content, question=original_question(state))
    verdict = llm.with_structured_output(GradeDocuments).invoke([HumanMessage(prompt)])
    print(f"   ↳ [grade] LLM 판정: {verdict.binary_score}")
    return "generate_answer" if verdict.binary_score == "yes" else "rewrite_question"


# ---------------------------------------------------------------------------
# 노드 3: 질의 재작성
# ---------------------------------------------------------------------------
REWRITE_PROMPT = (
    "다음 질문의 의도를 파악해, 문서 검색이 더 잘 되도록 핵심 키워드 중심의 질문 한 문장으로 다시 쓰세요.\n"
    "원래 질문: {question}"
)


def rewrite_question(state: RAGState) -> dict:
    question = original_question(state)
    better = llm.invoke([HumanMessage(REWRITE_PROMPT.format(question=question))])
    # 재작성된 질문을 새 Human 메시지로 넣으면, 다음 generate_query_or_respond 가 이것으로 검색한다
    return {"messages": [HumanMessage(better.text)], "rewrite_count": state.get("rewrite_count", 0) + 1}


# ---------------------------------------------------------------------------
# 노드 4: 최종 답변 생성
# ---------------------------------------------------------------------------
ANSWER_PROMPT = (
    "당신은 질의응답 도우미입니다. 아래 검색된 컨텍스트만 근거로 3문장 이내로 답하세요. "
    "컨텍스트에 답이 없으면 '문서에서 찾지 못했습니다'라고 답하세요.\n\n"
    "질문: {question}\n컨텍스트: {context}"
)


def generate_answer(state: RAGState) -> dict:
    context = state["messages"][-1].content
    first_question = next(m.text for m in state["messages"] if m.type == "human")
    answer = llm.invoke([HumanMessage(ANSWER_PROMPT.format(question=first_question, context=context))])
    return {"messages": [answer]}


# ---------------------------------------------------------------------------
# 그래프 조립
# ---------------------------------------------------------------------------
builder = StateGraph(RAGState)
builder.add_node(generate_query_or_respond)
builder.add_node("retrieve", ToolNode(tools))
builder.add_node(rewrite_question)
builder.add_node(generate_answer)

builder.add_edge(START, "generate_query_or_respond")
builder.add_conditional_edges("generate_query_or_respond", tools_condition, {"tools": "retrieve", END: END})
builder.add_conditional_edges("retrieve", grade_documents)
builder.add_edge("rewrite_question", "generate_query_or_respond")
builder.add_edge("generate_answer", END)
graph = builder.compile()

print(graph.get_graph().draw_mermaid())

for question in ["LangGraph 의 interrupt 는 무엇인가요?", "오늘 점심 메뉴 추천해 줘"]:
    print("\n" + "=" * 60)
    print(f"질문: {question}")
    print("=" * 60)
    # stream_mode 를 리스트로 주면 (모드, 데이터) 튜플이 온다.
    #  - "updates": 노드가 끝날 때마다 그 노드가 반환한 변경분
    #  - "values" : 매 단계 후 전체 상태 → 마지막 값이 최종 상태
    final: dict = {}
    for mode, chunk in graph.stream(
        {"messages": [HumanMessage(question)], "rewrite_count": 0},
        stream_mode=["updates", "values"],
        config={"recursion_limit": 20},  # 이중 안전장치
    ):
        if mode == "values":
            final = chunk
            continue
        for node, delta in chunk.items():
            msg = (delta or {}).get("messages", [None])[-1]
            if msg is None:
                summary = ""
            elif getattr(msg, "tool_calls", None):
                summary = f"도구호출 {[c['name'] for c in msg.tool_calls]}"
            else:
                summary = msg.text[:70].replace("\n", " ")
            print(f"▶ {node:26s} {summary}")
    print(f"최종 답변: {final['messages'][-1].text[:120]}")
    print(f"재작성 횟수: {final['rewrite_count']}")
