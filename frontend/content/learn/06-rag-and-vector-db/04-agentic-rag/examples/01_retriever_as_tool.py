"""Retriever 를 '도구(Tool)'로 만들어 create_agent 에 쥐여 주기 + 2단계 RAG 와 비교.

A) 2단계 RAG(Two-step): 매 질문마다 무조건 검색 → 컨텍스트를 프롬프트에 주입 → 답변 (LLM 호출 1회)
   - @dynamic_prompt 미들웨어로 구현
B) Agentic RAG: 검색을 도구로 주고, '검색할지/무엇으로 검색할지'를 모델이 결정 (LLM 호출 2회 이상)

Mock 모드에서는 도구가 있으면 항상 도구를 호출합니다. 실제 모델은 인사말 같은 질문에는 검색 없이 답합니다.
"""

import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")

# ---------------------------------------------------------------------------
# 지식 베이스 준비 (실제로는 02강의 청킹 파이프라인 결과를 넣습니다)
# ---------------------------------------------------------------------------
store = InMemoryVectorStore(embedding=OpenAIEmbeddings(model="text-embedding-3-small"))
store.add_documents(
    [
        Document(page_content="연차는 입사 1년 이상 직원에게 연 15일 부여됩니다.", metadata={"source": "hr/leave.md"}),
        Document(page_content="반차는 4시간 단위이며 오전 반차와 오후 반차가 있습니다.", metadata={"source": "hr/leave.md"}),
        Document(page_content="재택 근무는 주 2회까지 가능하며 팀장 승인이 필요합니다.", metadata={"source": "hr/remote.md"}),
        Document(page_content="교육비는 연 200만 원까지 지원합니다.", metadata={"source": "hr/benefit.md"}),
    ]
)


def format_docs(docs: list[Document]) -> str:
    """LLM 에 넘길 컨텍스트 문자열. 출처를 함께 넣어 인용(citation)을 유도한다."""
    return "\n\n".join(f"[출처: {d.metadata['source']}]\n{d.page_content}" for d in docs)


# ---------------------------------------------------------------------------
# B) 검색 도구: content_and_artifact → LLM 에는 문자열, 코드에는 원본 Document 리스트
# ---------------------------------------------------------------------------
@tool(response_format="content_and_artifact")
def search_hr_docs(query: str) -> tuple[str, list[Document]]:
    """사내 인사(HR) 규정 문서를 검색합니다. 연차, 반차, 재택 근무, 복지, 교육비 질문에 사용하세요.

    Args:
        query: 검색할 질문 또는 키워드
    """
    docs = store.similarity_search(query, k=2)
    return format_docs(docs), docs


@tool
def get_today() -> str:
    """오늘 날짜를 알려줍니다. 날짜나 요일 질문에만 사용하세요."""
    return "2026-10-28 (수)"


agentic = create_agent(
    MODEL,
    tools=[search_hr_docs, get_today],
    system_prompt=(
        "당신은 사내 HR 도우미입니다. 회사 규정 질문은 반드시 search_hr_docs 로 근거를 찾은 뒤 답하고, "
        "답변 끝에 [출처: ...] 를 붙이세요. 검색 결과에 없는 내용은 모른다고 답하세요."
    ),
)

print("=" * 60)
print("B) Agentic RAG — 모델이 도구 사용을 결정")
print("=" * 60)
result = agentic.invoke({"messages": [{"role": "user", "content": "반차는 몇 시간 단위로 쓸 수 있나요?"}]})
for m in result["messages"]:
    m.pretty_print()

# artifact 로 원본 Document 를 꺼내 UI 의 '근거 보기'에 쓸 수 있다
tool_msgs = [m for m in result["messages"] if m.type == "tool" and m.name == "search_hr_docs"]
if tool_msgs:
    print("\n근거 문서(artifact):", [d.metadata["source"] for d in tool_msgs[0].artifact])


# ---------------------------------------------------------------------------
# A) 2단계 RAG: 도구 없이, 모델 호출 직전에 항상 검색해서 시스템 프롬프트에 넣는다
# ---------------------------------------------------------------------------
@dynamic_prompt
def inject_context(request: ModelRequest) -> str:
    """마지막 사용자 메시지로 검색해 컨텍스트를 시스템 프롬프트에 주입한다."""
    last_user = next(m for m in reversed(request.state["messages"]) if m.type == "human")
    docs = store.similarity_search(last_user.text, k=2)
    return (
        "아래 컨텍스트만 근거로 한국어로 답하세요. 없으면 모른다고 답하세요.\n\n"
        f"<context>\n{format_docs(docs)}\n</context>"
    )


two_step = create_agent(MODEL, tools=[], middleware=[inject_context])

print("\n" + "=" * 60)
print("A) 2단계 RAG — 항상 검색, LLM 호출 1회")
print("=" * 60)
out = two_step.invoke({"messages": [{"role": "user", "content": "재택 근무는 일주일에 몇 번 가능한가요?"}]})
out["messages"][-1].pretty_print()
print(f"\n메시지 수 비교 → Agentic: {len(result['messages'])}개, 2단계: {len(out['messages'])}개")
