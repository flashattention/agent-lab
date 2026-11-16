// 상태 정의, 설정, 도구, 리트리버 파일.
import type { Ctx } from "./context.ts";
import { py } from "./context.ts";

export function stateFile(c: Ctx): string {
  const fields: string[] = [];
  const extraImports = new Set<string>();
  if (c.hasRetriever) fields.push("    context: str  # Retriever 가 채우는 검색 문맥");
  if (c.hasMap) fields.push("    item: str  # Send 로 각 워커에 전달되는 개별 항목");
  if (c.hasResults) {
    extraImports.add("import operator");
    extraImports.add("from typing import Annotated");
    fields.push("    results: Annotated[list[str], operator.add]  # 병렬 워커 결과 누적 (리듀서)");
  }
  for (const n of c.g.nodes) {
    if (n.kind === "evaluator") {
      fields.push(`    ${n.data.name}_count: int  # 평가 반복 횟수`);
      fields.push(`    ${n.data.name}_verdict: str  # "pass" | "retry"`);
    }
    if (n.kind === "supervisor") fields.push(`    ${n.data.name}_turns: int  # 위임 횟수 (루프 상한용)`);
    if (n.kind === "human") fields.push(`    ${n.data.name}_decision: str  # "approve" | "reject"`);
  }
  return `"""그래프 상태(State) 정의.

MessagesState 는 \`messages: Annotated[list[AnyMessage], add_messages]\` 를 포함한다.
add_messages 리듀서 덕분에 노드가 반환한 메시지는 덮어쓰지 않고 '추가'된다.
"""

${[...extraImports].sort().join("\n")}${extraImports.size ? "\n\n" : ""}from langgraph.graph import MessagesState


class State(MessagesState, total=False):
    """에이전트 전체가 공유하는 상태."""

${fields.length ? fields.join("\n") : "    pass"}
`;
}

export function configFile(): string {
  return `"""공통 설정: 모델 ID 는 환경변수에서 읽는다 (12-factor)."""

import os

from langchain.chat_models import init_chat_model

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def get_llm(model: str | None = None):
    """채팅 모델 인스턴스. model 을 주면 그 모델(노드별 지정), 아니면 LAB_MODEL.

    GPT-5 계열은 temperature 를 지원하지 않으므로 지정하지 않는다.
    """
    return init_chat_model(model or MODEL)
`;
}

export function toolsFile(c: Ctx): string {
  return `"""에이전트가 사용할 도구(Tool) 정의.

@tool 데코레이터는 함수 시그니처와 docstring 으로 JSON 스키마를 만들어 LLM 에 전달한다.
docstring 은 LLM 이 도구를 '언제' 쓸지 판단하는 근거이므로 구체적으로 쓴다.
"""

from langchain.tools import tool


${c.usedTools.map((t) => c.tools[t].code).join("\n\n\n")}


TOOLS = {${c.usedTools.map((t) => `${py(t)}: ${t}`).join(", ")}}
`;
}

export function retrieverFile(): string {
  return `"""데모용 벡터 스토어 & 리트리버.

운영에서는 InMemoryVectorStore 대신 pgvector / Qdrant / Pinecone 등을 사용한다.
"""

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

DOCS = [
    Document(page_content="LangGraph 는 상태(State), 노드(Node), 엣지(Edge)로 에이전트 워크플로를 그래프로 표현한다.", metadata={"source": "langgraph"}),
    Document(page_content="체크포인터(Checkpointer)는 매 스텝의 상태를 저장해 대화 메모리, 장애 복구, Human-in-the-loop 를 가능하게 한다.", metadata={"source": "persistence"}),
    Document(page_content="RAG 는 질문과 관련된 문서를 검색해 LLM 의 컨텍스트에 넣어 환각을 줄이는 기법이다.", metadata={"source": "rag"}),
    Document(page_content="환불은 결제 후 14일 이내 가능하며 영업일 기준 3~5일이 소요된다.", metadata={"source": "faq"}),
    Document(page_content="서울의 가을 여행지로는 경복궁, 북촌 한옥마을, 남산 서울타워, 한강 공원이 인기가 많다.", metadata={"source": "travel"}),
]

_store = InMemoryVectorStore(OpenAIEmbeddings(model="text-embedding-3-small"))
_store.add_documents(DOCS)


def get_retriever(k: int = 3):
    """유사도 검색 리트리버."""
    return _store.as_retriever(search_kwargs={"k": k})
`;
}
