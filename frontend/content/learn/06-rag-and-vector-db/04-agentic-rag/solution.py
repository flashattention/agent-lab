"""정답: 재작성 상한이 있는 Agentic RAG 그래프 완성하기

사내 IT 헬프데스크 문서를 검색하는 Agentic RAG 그래프입니다. 노드는 모두 준비돼 있습니다.
여러분은 '라우팅 함수'와 '엣지 연결'을 완성합니다.

과제
1. `route_after_retrieval(state)` 를 완성하세요. 반환값은 "generate_answer" 또는 "rewrite_question".
   - (a) state["rewrite_count"] 가 MAX_REWRITES 이상이면 무조건 "generate_answer"  ← 무한 루프 방지
   - (b) 마지막 메시지(ToolMessage)의 artifact 가 비어 있으면 "rewrite_question"  ← LLM 호출 절약
   - (c) 그 외에는 grade_with_llm(state) 결과가 "yes" 면 "generate_answer", 아니면 "rewrite_question"
2. 그래프 엣지를 연결하세요.
   - START → "agent"
   - "agent" 에서 tools_condition 으로 분기: {"tools": "retrieve", END: END}
   - "retrieve" 에서 route_after_retrieval 로 분기
   - "rewrite_question" → "agent"
   - "generate_answer" → END
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_REWRITES = 2
llm = init_chat_model(MODEL)

store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(page_content="VPN 접속이 안 되면 OTP 시간을 동기화하고 VPN 클라이언트를 재시작하세요.", metadata={"source": "it/vpn.md"}),
        Document(page_content="노트북 분실 시 즉시 보안팀에 신고하고 원격 잠금을 요청하세요.", metadata={"source": "it/lost.md"}),
        Document(page_content="프린터 드라이버는 사내 포털 소프트웨어 센터에서 설치합니다.", metadata={"source": "it/printer.md"}),
    ]
)


@tool(response_format="content_and_artifact")
def search_it_docs(query: str) -> tuple[str, list[Document]]:
    """사내 IT 헬프데스크 문서를 검색합니다. VPN, 노트북, 프린터 등 IT 문제에 사용하세요.

    Args:
        query: 검색 질의
    """
    docs = [d for d, s in store.similarity_search_with_score(query, k=2) if s >= 0.2]
    if not docs:
        return "관련 문서를 찾지 못했습니다.", []
    return "\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs), docs


class State(MessagesState):
    rewrite_count: int


class Grade(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="관련 있으면 'yes', 없으면 'no'")


def grade_with_llm(state: State) -> str:
    """(제공됨) LLM 으로 검색 결과 관련성을 판정해 'yes'/'no' 를 반환."""
    question = next(m.text for m in reversed(state["messages"]) if m.type == "human")
    prompt = f"문서: {state['messages'][-1].content}\n질문: {question}\n관련 있으면 'yes', 아니면 'no'."
    return llm.with_structured_output(Grade).invoke([HumanMessage(prompt)]).binary_score


def agent(state: State) -> dict:
    return {"messages": [llm.bind_tools([search_it_docs]).invoke(state["messages"])]}


def rewrite_question(state: State) -> dict:
    question = next(m.text for m in reversed(state["messages"]) if m.type == "human")
    better = llm.invoke([HumanMessage(f"검색이 잘 되도록 IT 키워드 중심으로 다시 쓰세요: {question}")])
    return {"messages": [HumanMessage(better.text)], "rewrite_count": state.get("rewrite_count", 0) + 1}


def generate_answer(state: State) -> dict:
    question = next(m.text for m in state["messages"] if m.type == "human")
    context = state["messages"][-1].content
    return {"messages": [llm.invoke([HumanMessage(f"컨텍스트만 근거로 답하세요.\n질문: {question}\n컨텍스트: {context}")])]}


def route_after_retrieval(state: State) -> Literal["generate_answer", "rewrite_question"]:
    if state.get("rewrite_count", 0) >= MAX_REWRITES:  # (a) 상한 도달 → 있는 정보로 답변
        return "generate_answer"
    if not getattr(state["messages"][-1], "artifact", None):  # (b) 0건이면 LLM 호출 없이 재작성
        return "rewrite_question"
    return "generate_answer" if grade_with_llm(state) == "yes" else "rewrite_question"  # (c)


builder = StateGraph(State)
builder.add_node("agent", agent)
builder.add_node("retrieve", ToolNode([search_it_docs]))
builder.add_node("rewrite_question", rewrite_question)
builder.add_node("generate_answer", generate_answer)

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition, {"tools": "retrieve", END: END})
builder.add_conditional_edges("retrieve", route_after_retrieval)
builder.add_edge("rewrite_question", "agent")
builder.add_edge("generate_answer", END)

graph = builder.compile()

# ---------------------------------------------------------------------------
# 자가 채점
# ---------------------------------------------------------------------------
config = {"recursion_limit": 25}
ok = graph.invoke({"messages": [HumanMessage("VPN 접속이 안 돼요. OTP 는 맞게 입력했어요.")], "rewrite_count": 0}, config)
print("관련 질문 → 재작성:", ok["rewrite_count"], "| 답:", ok["messages"][-1].text[:60])
assert any(m.type == "tool" for m in ok["messages"]), "검색 도구가 실행돼야 합니다"
assert isinstance(ok["messages"][-1], AIMessage), "마지막은 AI 답변이어야 합니다"
assert ok["rewrite_count"] == 0, "관련 문서가 바로 나오면 재작성하지 않아야 합니다"

off = graph.invoke({"messages": [HumanMessage("주말 등산 코스 추천")], "rewrite_count": 0}, config)
print("무관한 질문 → 재작성:", off["rewrite_count"], "| 답:", off["messages"][-1].text[:60])
assert 1 <= off["rewrite_count"] <= MAX_REWRITES, "관련 문서가 없으면 재작성하되 상한을 넘으면 안 됩니다"
assert isinstance(off["messages"][-1], AIMessage), "상한에 도달해도 최종 답변으로 끝나야 합니다"

assert route_after_retrieval({"messages": [AIMessage("x")], "rewrite_count": MAX_REWRITES}) == "generate_answer"
print("✅ 모든 테스트 통과!")
