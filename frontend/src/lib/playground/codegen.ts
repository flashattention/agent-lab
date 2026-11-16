// 비주얼 그래프 → LangGraph 1.x / LangChain 1.x 파이썬 프로젝트 (결정적 템플릿 생성기)
import type { GEdge, GNode, Graph, GraphSettings, SubGraph } from "./types.ts";
import { PROVIDER_PACKAGES, providerOf, toolCatalog, type ToolDef } from "./catalog.ts";
import { allNodes, walkGraphs } from "./subgraph.ts";

export const GENERATOR_VERSION = "2026.11-1";

const VIRTUAL = new Set(["start", "end", "router", "map"]);
const py = (s: string) => JSON.stringify(s ?? "");
const indent = (s: string, n = 4) =>
  s
    .split("\n")
    .map((l) => (l.trim() ? " ".repeat(n) + l : ""))
    .join("\n");
const pascal = (s: string) => s.replace(/(^|_)([a-z0-9])/g, (_, __, c: string) => c.toUpperCase());

type Ctx = {
  g: SubGraph & { settings: GraphSettings };
  pkg: string; // 이 그래프의 파이썬 패키지 (agent, agent.subagents.researcher, ...)
  dir: string; // 파일 경로 접두사 (agent, agent/subagents/researcher, ...)
  isRoot: boolean;
  memory: "inherit" | "persistent";
  graphName: string;
  byId: Map<string, GNode>;
  out: Map<string, GEdge[]>;
  inc: Map<string, GEdge[]>;
  real: GNode[];
  hasRetriever: boolean;
  hasMap: boolean;
  hasResults: boolean;
  usedTools: string[];
  tools: Record<string, ToolDef>; // 기본 + 커스텀 도구
  envPrefix: string; // 노드별 모델 환경 변수 접두사 (서브그래프 경로)
};

function context(g: SubGraph & { settings: GraphSettings }, pkg = "agent", graphName = "agent", memory: Ctx["memory"] = "inherit"): Ctx {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const out = new Map<string, GEdge[]>();
  const inc = new Map<string, GEdge[]>();
  for (const n of g.nodes) {
    out.set(n.id, []);
    inc.set(n.id, []);
  }
  for (const e of g.edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) continue;
    out.get(e.source)!.push(e);
    inc.get(e.target)!.push(e);
  }
  const real = g.nodes.filter((n) => !VIRTUAL.has(n.kind));
  // 도구 정의(agent/tools.py)는 모든 서브그래프가 공유하므로 전체 트리에서 모은다
  const tools = toolCatalog(g.settings);
  const usedTools = [...new Set(allNodes(g).filter((n) => n.kind === "tools" || n.kind === "agent").flatMap((n) => n.data.tools ?? []))].filter((t) => tools[t]);
  const hasMap = g.nodes.some((n) => n.kind === "map");
  return {
    g,
    pkg,
    dir: pkg.replace(/\./g, "/"),
    isRoot: pkg === "agent",
    memory,
    graphName,
    byId,
    out,
    inc,
    real,
    hasRetriever: g.nodes.some((n) => n.kind === "retriever"),
    hasMap,
    hasResults: hasMap || g.nodes.some((n) => n.kind === "reduce"),
    usedTools,
    tools,
    envPrefix: pkg === "agent" ? "" : pkg.replace(/^agent\./, "").replace(/(^|\.)subagents\./g, "$1").replace(/\./g, "__").toUpperCase() + "__",
  };
}

/** 노드별 모델: LAB_MODEL__<경로_노드> 환경 변수 > 캔버스 지정값 > LAB_MODEL */
const modelEnv = (c: Ctx, n: GNode) => `LAB_MODEL__${c.envPrefix}${n.data.name.toUpperCase()}`;
const llmExpr = (c: Ctx, n: GNode) => (n.data.model?.trim() ? `get_llm(os.getenv(${py(modelEnv(c, n))}, ${py(n.data.model.trim())}))` : "get_llm()");
const agentModelExpr = (c: Ctx, n: GNode) => (n.data.model?.trim() ? `os.getenv(${py(modelEnv(c, n))}, ${py(n.data.model.trim())})` : "MODEL");
/** 파일이 os.getenv 를 쓰면 docstring 뒤에 import os 를 넣는다 */
const withOs = (src: string) => (/\bos\.getenv\(/.test(src) && !/^import os$/m.test(src) ? src.replace(/^("""[\s\S]*?"""\n\n)/, "$1import os\n\n") : src);

/** 노드 id → 파이썬 대상 표현식 (END 또는 "name") */
const target = (c: Ctx, id: string) => {
  const n = c.byId.get(id);
  if (!n || n.kind === "end") return "END";
  return py(n.data.name);
};
const targetKey = (c: Ctx, id: string) => {
  const n = c.byId.get(id);
  return !n || n.kind === "end" ? "__end__" : n.data.name;
};

/** LLM 노드 뒤 tools_condition 라우터가 가리키는 Tools 노드들의 도구 */
function boundTools(c: Ctx, n: GNode): string[] {
  const tools = new Set<string>();
  for (const e of c.out.get(n.id) ?? []) {
    const r = c.byId.get(e.target);
    if (r?.kind !== "router" || r.data.strategy !== "tools_condition") continue;
    for (const e2 of c.out.get(r.id) ?? []) {
      const t = c.byId.get(e2.target);
      if (t?.kind === "tools") (t.data.tools ?? []).forEach((x) => c.tools[x] && tools.add(x));
    }
  }
  return [...tools];
}

const isMapWorker = (c: Ctx, n: GNode) => (c.inc.get(n.id) ?? []).some((e) => c.byId.get(e.source)?.kind === "map");
const supervisorOf = (c: Ctx, n: GNode) =>
  (c.inc.get(n.id) ?? []).map((e) => c.byId.get(e.source)).find((s) => s?.kind === "supervisor" && (c.out.get(n.id) ?? []).some((x) => x.target === s.id));

/* ======================================================================== files */

function stateFile(c: Ctx): string {
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

function configFile(): string {
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

function toolsFile(c: Ctx): string {
  return `"""에이전트가 사용할 도구(Tool) 정의.

@tool 데코레이터는 함수 시그니처와 docstring 으로 JSON 스키마를 만들어 LLM 에 전달한다.
docstring 은 LLM 이 도구를 '언제' 쓸지 판단하는 근거이므로 구체적으로 쓴다.
"""

from langchain.tools import tool


${c.usedTools.map((t) => c.tools[t].code).join("\n\n\n")}


TOOLS = {${c.usedTools.map((t) => `${py(t)}: ${t}`).join(", ")}}
`;
}

function retrieverFile(): string {
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

function contextLine(c: Ctx) {
  return c.hasRetriever
    ? `    if state.get("context"):
        system += "\\n\\n[참고 문서]\\n" + state["context"]
`
    : "";
}

function nodeFile(c: Ctx, n: GNode): string {
  const name = n.data.name;
  const prompt = py(n.data.prompt ?? "");
  const header = (doc: string, imports: string[]) => `"""${doc}"""

${imports.join("\n")}
`;
  const sup = supervisorOf(c, n);
  switch (n.kind) {
    case "llm": {
      const tools = boundTools(c, n);
      if (isMapWorker(c, n)) {
        return `${header(`'${name}' — Map 워커 LLM 노드. Send 로 받은 개별 항목(item)을 처리한다.`, [
          "from langchain.messages import HumanMessage, SystemMessage",
          "",
          "from agent.config import get_llm",
          `from ${c.pkg}.state import State`,
        ])}
PROMPT = ${prompt}
llm = ${llmExpr(c, n)}


def ${name}(state: State) -> dict:
    """항목 하나를 처리해 results 리스트에 추가한다 (operator.add 리듀서로 병합)."""
    item = state["item"]
    response = llm.invoke([SystemMessage(PROMPT), HumanMessage(f"다음 항목을 처리하세요: {item}")])
    return {"results": [f"■ {item}\\n{response.text}"]}
`;
      }
      return `${header(`'${name}' — LLM 노드.${tools.length ? " 도구가 바인딩되어 있어 tool_calls 를 생성할 수 있다." : ""}`, [
        sup ? "from langchain.messages import AIMessage, SystemMessage" : "from langchain.messages import SystemMessage",
        "",
        "from agent.config import get_llm",
        `from ${c.pkg}.state import State`,
        ...(tools.length ? ["from agent.tools import TOOLS"] : []),
      ])}
PROMPT = ${prompt}
${tools.length ? `# 이 노드 뒤의 tools_condition 라우터가 가리키는 ToolNode 의 도구를 바인딩한다.\nllm = ${llmExpr(c, n)}.bind_tools([TOOLS[name] for name in ${JSON.stringify(tools)}])` : `llm = ${llmExpr(c, n)}`}


def ${name}(state: State) -> dict:
    """대화 기록을 모델에 전달하고 응답 메시지를 상태에 추가한다."""
    system = PROMPT
${contextLine(c)}    response = llm.invoke([SystemMessage(system), *state["messages"]])
${sup ? `    # Supervisor 가 누가 답했는지 알 수 있도록 이름을 붙여 돌려준다.\n    return {"messages": [AIMessage(content=response.text, name=${py(name)})]}` : `    return {"messages": [response]}`}
`;
    }
    case "agent": {
      const tools = (n.data.tools ?? []).filter((t) => c.tools[t]);
      const mapWorker = isMapWorker(c, n);
      return `${header(`'${name}' — create_agent 로 만든 완성형 ReAct 에이전트를 노드로 사용한다.

에이전트 내부에서 모델 호출 ↔ 도구 실행 루프가 돌고, 최종 답변만 부모 그래프로 돌려준다
(컨텍스트 격리: 부모 대화에 도구 호출 기록이 쌓이지 않는다).`, [
        "from langchain.agents import create_agent",
        mapWorker ? "from langchain.messages import HumanMessage" : "from langchain.messages import AIMessage",
        "",
        ...(n.data.model?.trim() ? [] : ["from agent.config import MODEL"]),
        `from ${c.pkg}.state import State`,
        ...(tools.length ? ["from agent.tools import TOOLS"] : []),
      ])}
PROMPT = ${prompt}

_agent = create_agent(
    ${agentModelExpr(c, n)},
    tools=[${tools.map((t) => `TOOLS[${py(t)}]`).join(", ")}],
    system_prompt=PROMPT,
    name=${py(name)},
)


def ${name}(state: State) -> dict:
    """하위 에이전트를 실행하고 최종 답변만 반환한다."""
${
  mapWorker
    ? `    item = state["item"]
    result = _agent.invoke({"messages": [HumanMessage(f"다음 항목을 처리하세요: {item}")]})
    return {"results": [f"■ {item}\\n{result['messages'][-1].text}"]}`
    : `    result = _agent.invoke({"messages": state["messages"]})
    answer = result["messages"][-1]
    return {"messages": [AIMessage(content=answer.text, name=${py(name)})]}`
}
`;
    }
    case "tools": {
      const tools = (n.data.tools ?? []).filter((t) => c.tools[t]);
      return `${header(`'${name}' — ToolNode: 직전 AIMessage 의 tool_calls 를 실행해 ToolMessage 로 돌려준다.

handle_tool_errors=True 이면 도구 예외를 오류 메시지로 바꿔 LLM 이 스스로 복구할 기회를 준다.`, [
        "from langgraph.prebuilt import ToolNode",
        "",
        "from agent.tools import TOOLS",
      ])}
${name} = ToolNode([${tools.map((t) => `TOOLS[${py(t)}]`).join(", ")}], handle_tool_errors=True)
`;
    }
    case "retriever":
      return `${header(`'${name}' — 마지막 사용자 질문으로 문서를 검색해 state.context 에 저장한다.`, [
        "from langchain.messages import HumanMessage",
        "",
        "from agent.retriever import get_retriever",
        `from ${c.pkg}.state import State`,
      ])}
retriever = get_retriever(k=${n.data.k ?? 3})


def ${name}(state: State) -> dict:
    """가장 최근 사용자 메시지를 질의로 사용한다."""
    query = next((m.text for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    docs = retriever.invoke(query)
    context = "\\n".join(f"- ({d.metadata.get('source')}) {d.page_content}" for d in docs)
    print(f"  🔎 '{query[:40]}' → {len(docs)}건 검색")
    return {"context": context}
`;
    case "function":
      return `${header(`'${name}' — 사용자 정의 Function 노드.`, [`from ${c.pkg}.state import State`])}

def ${name}(state: State) -> dict:
    """상태를 받아 업데이트할 키만 dict 로 반환한다."""
${indent(n.data.code?.trim() || "return {}")}
`;
    case "human": {
      const hasReject = (c.out.get(n.id) ?? []).some((e) => e.sourceHandle === "reject");
      return `${header(`'${name}' — Human-in-the-loop.

interrupt() 는 그래프 실행을 멈추고 값을 클라이언트에 전달한다. 체크포인터가 상태를 저장해 두므로
나중에 graph.invoke(Command(resume=...), config) 로 같은 thread 를 이어서 실행할 수 있다.
주의: 재개 시 이 노드는 '처음부터' 다시 실행되므로 interrupt 이전에 부작용(side effect)을 두지 않는다.`, [
        "from langchain.messages import HumanMessage",
        "from langgraph.types import interrupt",
        "",
        `from ${c.pkg}.state import State`,
      ])}
QUESTION = ${py(n.data.prompt ?? "승인하시겠습니까?")}


def ${name}(state: State) -> dict:
    """사람의 승인/거절과 피드백을 받는다."""
    last = state["messages"][-1]
    decision = interrupt({"question": QUESTION, "draft": last.text})
    if not isinstance(decision, dict):
        decision = {"approved": bool(decision)}
    approved = decision.get("approved", True)
    update: dict = {${py(`${n.data.name}_decision`)}: "approve" if approved else "reject"}
    if not approved and decision.get("feedback"):
        update["messages"] = [HumanMessage(f"[검토자 피드백] {decision['feedback']}")]
    return update
${hasReject ? "" : "\n# reject 경로가 연결되지 않아 승인 여부와 관계없이 다음 노드로 진행합니다.\n"}`;
    }
    case "evaluator":
      return `${header(`'${name}' — Evaluator (Reflection / Evaluator-Optimizer).

구조화 출력으로 pass/retry 를 판정하고, retry 면 피드백을 메시지로 남겨 생성 노드가 개선하게 한다.
반복 상한(MAX_ITERATIONS)으로 무한 루프를 막는다.`, [
        "from typing import Literal",
        "",
        "from langchain.messages import HumanMessage, SystemMessage",
        "from pydantic import BaseModel, Field",
        "",
        "from agent.config import get_llm",
        `from ${c.pkg}.state import State`,
      ])}
CRITERIA = ${prompt}
MAX_ITERATIONS = ${n.data.maxIterations ?? 3}


class Verdict(BaseModel):
    """평가 결과."""

    verdict: Literal["pass", "retry"] = Field(description="기준을 만족하면 pass, 아니면 retry")
    feedback: str = Field(description="개선이 필요하면 구체적인 피드백")


grader = ${llmExpr(c, n)}.with_structured_output(Verdict)


def ${name}(state: State) -> dict:
    """직전 답변을 평가한다."""
    count = state.get(${py(`${name}_count`)}, 0) + 1
    question = next((m.text for m in state["messages"] if isinstance(m, HumanMessage)), "")
    answer = state["messages"][-1].text
    result: Verdict = grader.invoke(
        [
            SystemMessage(f"당신은 엄격한 평가자입니다. 평가 기준: {CRITERIA}"),
            HumanMessage(f"질문: {question}\\n\\n답변: {answer}"),
        ]
    )
    print(f"  ⚖️  평가 #{count}: {result.verdict}")
    update: dict = {${py(`${name}_count`)}: count, ${py(`${name}_verdict`)}: result.verdict}
    if result.verdict == "retry" and count < MAX_ITERATIONS:
        update["messages"] = [HumanMessage(f"[평가 피드백] {result.feedback} — 피드백을 반영해 다시 작성하세요.")]
    return update
`;
    case "supervisor": {
      const outs = (c.out.get(n.id) ?? []).map((e) => c.byId.get(e.target)!).filter(Boolean);
      const workers = outs.filter((w) => w.kind !== "end" && (c.out.get(w.id) ?? []).some((x) => x.target === n.id));
      const finish = outs.find((w) => !workers.includes(w));
      const finishExpr = finish ? target(c, finish.id) : "END";
      const dests = [...workers.map((w) => py(w.data.name)), finish && finish.kind !== "end" ? py(finish.data.name) : '"__end__"'];
      const members = workers.map((w) => `    ${py(w.data.name)}: ${py(w.data.description || w.data.prompt?.slice(0, 60) || w.data.name)},`).join("\n");
      return `${header(`'${name}' — Supervisor 패턴.

LLM 이 구조화 출력으로 다음 워커를 고르고 Command(goto=...)로 제어를 넘긴다.
Command 를 쓰면 '상태 업데이트 + 라우팅'을 한 번에 할 수 있어 별도의 조건부 엣지가 필요 없다.`, [
        "from typing import Literal",
        "",
        "from langchain.messages import SystemMessage",
        "from langgraph.graph import END",
        "from langgraph.types import Command",
        "from pydantic import BaseModel, Field",
        "",
        "from agent.config import get_llm",
        `from ${c.pkg}.state import State`,
      ])}
PROMPT = ${prompt}
MAX_TURNS = ${n.data.maxIterations ?? 6}
MEMBERS = {
${members || '    # 워커가 연결되지 않았습니다'}
}


class Route(BaseModel):
    """다음에 일할 팀원 또는 FINISH."""

    next: Literal[${[...workers.map((w) => py(w.data.name)), '"FINISH"'].join(", ")}] = Field(description="다음 작업자, 모두 끝났으면 FINISH")
    reason: str = Field(description="선택 이유 한 문장")


router_llm = ${llmExpr(c, n)}.with_structured_output(Route)


def ${name}(state: State) -> Command[Literal[${dests.join(", ")}]]:
    """다음 작업자를 고른다. 상한에 도달하면 강제로 종료한다."""
    turns = state.get(${py(`${name}_turns`)}, 0)
    if turns >= MAX_TURNS:
        print("  ⛔ 위임 상한 도달 → 종료")
        return Command(goto=${finishExpr})
    team = "\\n".join(f"- {k}: {v}" for k, v in MEMBERS.items())
    decision: Route = router_llm.invoke(
        [SystemMessage(f"{PROMPT}\\n\\n[팀원]\\n{team}"), *state["messages"]]
    )
    print(f"  👑 {decision.next} ← {decision.reason}")
    goto = ${finishExpr} if decision.next == "FINISH" else decision.next
    return Command(goto=goto, update={${py(`${name}_turns`)}: turns + 1})
`;
    }
    case "subgraph": {
      const childPkg = `${c.pkg}.subagents.${name}`;
      const mapWorker = isMapWorker(c, n);
      const memo = n.data.memory === "persistent" ? "\n같은 thread 에서 다시 호출되면 이전 대화를 기억한다 (checkpointer=True)." : "";
      if (n.data.io === "shared" && !mapWorker) {
        return `${header(`'${name}' — 서브그래프 (상태 공유 모드).

컴파일된 하위 그래프를 그대로 노드로 등록한다. 부모와 이름이 같은 상태 키(messages 등)를
주고받으므로 하위 그래프 안에서 생긴 메시지(도구 호출 포함)가 부모 대화에 그대로 쌓인다.${memo}
내부 구조: ${childPkg.replace(/\./g, "/")}/graph.py`, [`from ${childPkg}.graph import graph as ${name}`])}
__all__ = [${py(name)}]
`;
      }
      return `${header(`'${name}' — 서브그래프 (격리 모드).

하위 그래프를 별도로 실행하고 최종 답변 한 개만 부모 그래프로 돌려준다.
하위 그래프의 중간 메시지·도구 호출은 부모 대화에 섞이지 않는다 (컨텍스트 격리).${memo}
내부 구조: ${childPkg.replace(/\./g, "/")}/graph.py`, [
        mapWorker ? "from langchain.messages import HumanMessage" : "from langchain.messages import AIMessage",
        "",
        `from ${c.pkg}.state import State`,
        `from ${childPkg}.graph import graph as _subgraph`,
      ])}

def ${name}(state: State) -> dict:
    """서브 에이전트 '${name}' 을(를) 실행한다. config(thread, 콜백, interrupt)는 자동으로 전파된다."""
${
  mapWorker
    ? `    item = state["item"]
    result = _subgraph.invoke({"messages": [HumanMessage(f"다음 항목을 처리하세요: {item}")]})
    return {"results": [f"■ {item}\\n{result['messages'][-1].text}"]}`
    : `    result = _subgraph.invoke({"messages": state["messages"]})
    answer = result["messages"][-1]
    return {"messages": [AIMessage(content=answer.text, name=${py(name)})]}`
}
`;
    }
    case "reduce":
      return `${header(`'${name}' — Reduce: 병렬 워커 결과(state.results)를 하나의 답변으로 종합한다.`, [
        "from langchain.messages import AIMessage, HumanMessage, SystemMessage",
        "",
        "from agent.config import get_llm",
        `from ${c.pkg}.state import State`,
      ])}
PROMPT = ${prompt}
llm = ${llmExpr(c, n)}


def ${name}(state: State) -> dict:
    """부분 결과들을 종합한다."""
    parts = state.get("results", [])
    question = next((m.text for m in state["messages"] if isinstance(m, HumanMessage)), "")
    print(f"  🧩 부분 결과 {len(parts)}개 종합")
    response = llm.invoke([SystemMessage(PROMPT), HumanMessage(f"질문: {question}\\n\\n" + "\\n\\n".join(parts))])
    return {"messages": [AIMessage(content=response.text, name=${py(name)})]}
`;
  }
  return "";
}

function routingFile(c: Ctx): string | null {
  const routers = c.g.nodes.filter((n) => n.kind === "router");
  const maps = c.g.nodes.filter((n) => n.kind === "map");
  const evals = c.g.nodes.filter((n) => n.kind === "evaluator");
  const humans = c.g.nodes.filter((n) => n.kind === "human" && (c.out.get(n.id) ?? []).some((e) => e.sourceHandle === "reject"));
  if (!routers.length && !maps.length && !evals.length && !humans.length) return null;

  const imports = new Set<string>(["from typing import Literal", "", `from ${c.pkg}.state import State`]);
  const blocks: string[] = [];

  for (const r of routers) {
    const keys = (c.out.get(r.id) ?? []).map((e) => targetKey(c, e.target));
    const lit = `Literal[${keys.map(py).join(", ")}]`;
    const strategy = r.data.strategy ?? "llm";
    if (strategy === "tools_condition") {
      const toolsEdge = (c.out.get(r.id) ?? []).find((e) => c.byId.get(e.target)?.kind === "tools");
      const other = (c.out.get(r.id) ?? []).find((e) => e !== toolsEdge);
      blocks.push(`def ${r.data.name}(state: State) -> ${lit}:
    """tools_condition: 마지막 AIMessage 에 tool_calls 가 있으면 도구 노드로, 없으면 다음 단계로."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return ${py(toolsEdge ? targetKey(c, toolsEdge.target) : "__end__")}
    return ${py(other ? targetKey(c, other.target) : "__end__")}`);
    } else if (strategy === "state_key") {
      blocks.push(`def ${r.data.name}(state: State) -> ${lit}:
    """state[${py(r.data.stateKey ?? "route")}] 값과 같은 이름의 경로로 보낸다. 일치하지 않으면 첫 경로."""
    value = str(state.get(${py(r.data.stateKey ?? "route")}, ""))
    return value if value in ${JSON.stringify(keys)} else ${py(keys[0] ?? "__end__")}`);
    } else {
      imports.add("from langchain.messages import SystemMessage");
      imports.add("from pydantic import BaseModel, Field");
      imports.add("from agent.config import get_llm");
      if (r.data.model?.trim()) imports.add("import os");
      const cls = `${pascal(r.data.name)}Decision`;
      const desc = (c.out.get(r.id) ?? [])
        .map((e) => {
          const t = c.byId.get(e.target);
          return `- ${targetKey(c, e.target)}: ${t?.kind === "end" ? "더 할 일이 없으면 종료" : (t?.data.description || t?.data.prompt || "").slice(0, 80)}`;
        })
        .join("\\n");
      blocks.push(`class ${cls}(BaseModel):
    """라우팅 결정."""

    destination: ${lit} = Field(description="요청을 처리할 경로")


_${r.data.name}_llm = ${llmExpr(c, r)}.with_structured_output(${cls})


def ${r.data.name}(state: State) -> ${lit}:
    """LLM 이 구조화 출력으로 경로를 고른다 (Routing 패턴)."""
    decision = _${r.data.name}_llm.invoke(
        [SystemMessage(${py(r.data.prompt ?? "가장 적절한 경로를 고르세요.")} + "\\n\\n[경로]\\n${desc}"), *state["messages"]]
    )
    print(f"  🔀 ${r.data.name} → {decision.destination}")
    return decision.destination`);
    }
  }

  for (const m of maps) {
    imports.add("from langgraph.types import Send");
    const worker = (c.out.get(m.id) ?? [])[0];
    const wname = worker ? targetKey(c, worker.target) : "__end__";
    blocks.push(`MAX_ITEMS_${m.data.name.toUpperCase()} = ${m.data.maxItems ?? 4}


def ${m.data.name}(state: State) -> list[Send]:
    """직전 메시지를 줄/불릿 단위 항목으로 나눠 각각 '${wname}' 워커로 병렬 전송한다 (map 단계).

    Send(node, payload) 는 같은 노드를 서로 다른 입력으로 여러 번 동시에 실행한다.
    """
    text = state["messages"][-1].text
    items = [line.strip(" -*•0123456789.)\\t") for line in text.splitlines()]
    items = [i for i in items if len(i) > 1][:MAX_ITEMS_${m.data.name.toUpperCase()}] or [text[:200]]
    print(f"  🔱 {len(items)}개 항목으로 분기")
    return [Send(${py(wname)}, {"item": item}) for item in items]`);
  }

  for (const e of evals) {
    const pass = (c.out.get(e.id) ?? []).find((x) => x.sourceHandle === "pass");
    const retry = (c.out.get(e.id) ?? []).find((x) => x.sourceHandle === "retry");
    blocks.push(`def route_${e.data.name}(state: State) -> Literal["pass", "retry"]:
    """평가 결과 또는 반복 상한에 따라 분기한다. (pass → ${pass ? targetKey(c, pass.target) : "?"}, retry → ${retry ? targetKey(c, retry.target) : "?"})"""
    from ${c.pkg}.nodes.${e.data.name} import MAX_ITERATIONS

    if state.get(${py(`${e.data.name}_verdict`)}) == "pass" or state.get(${py(`${e.data.name}_count`)}, 0) >= MAX_ITERATIONS:
        return "pass"
    return "retry"`);
  }

  for (const h of humans) {
    blocks.push(`def route_${h.data.name}(state: State) -> Literal["approve", "reject"]:
    """사람의 결정에 따라 분기한다."""
    return "reject" if state.get(${py(`${h.data.name}_decision`)}) == "reject" else "approve"`);
  }

  const imp = [...imports];
  const std = imp.filter((x) => x.startsWith("from typing") || x === "import os").sort((a, b) => (a.startsWith("import") ? -1 : 0) - (b.startsWith("import") ? -1 : 0));
  const third = imp.filter((x) => x.startsWith("from langchain") || x.startsWith("from langgraph") || x.startsWith("from pydantic")).sort();
  const local = imp.filter((x) => x.startsWith("from agent")).sort();
  return `"""라우팅 함수 모음: add_conditional_edges 에 전달된다.

라우팅 함수는 노드가 아니다. 상태를 읽고 '다음에 갈 곳'만 반환한다.
반환 타입의 Literal 은 그래프 시각화와 정적 검증에 사용된다.
"""

${std.join("\n")}

${third.join("\n")}

${local.join("\n")}


${blocks.join("\n\n\n")}
`;
}

function graphFile(c: Ctx): string {
  const lines: string[] = [];
  const s = c.g.settings;
  const nodeImports = c.real.map((n) => n.data.name).sort();
  const routingImports = new Set<string>();

  // 노드 등록
  for (const n of c.real) {
    const opts: string[] = [];
    const plainRealIn = (c.inc.get(n.id) ?? []).filter((e) => {
      const src = c.byId.get(e.source);
      return src && !VIRTUAL.has(src.kind) && !["evaluator", "supervisor"].includes(src.kind) && !(src.kind === "human" && e.sourceHandle === "reject");
    });
    // 여러 실제 노드에서 합류하는 노드는 defer=True 로 모든 브랜치가 끝날 때까지 기다린다 (supervisor 는 Command 로 순차 실행되므로 제외)
    if (n.kind === "reduce" || (plainRealIn.length >= 2 && n.kind !== "supervisor")) opts.push("defer=True");
    if (n.kind === "agent" || n.kind === "llm") opts.push("retry_policy=RetryPolicy(max_attempts=3)");
    if (n.kind === "supervisor") {
      const outs = (c.out.get(n.id) ?? []).map((e) => targetKey(c, e.target));
      if (!outs.includes("__end__")) outs.push("__end__");
      opts.push(`destinations=(${outs.map(py).join(", ")}${outs.length === 1 ? "," : ""})`);
    }
    lines.push(`    builder.add_node(${py(n.data.name)}, ${n.data.name}${opts.length ? ", " + opts.join(", ") : ""})`);
  }
  lines.push("");

  // 엣지
  const handled = new Set<string>();
  const sources = c.g.nodes.filter((n) => n.kind !== "end" && n.kind !== "router" && n.kind !== "map" && n.kind !== "supervisor");
  for (const src of sources) {
    const srcExpr = src.kind === "start" ? "START" : py(src.data.name);
    const outs = c.out.get(src.id) ?? [];
    if (src.kind === "evaluator") {
      const pm = outs
        .filter((e) => e.sourceHandle === "pass" || e.sourceHandle === "retry")
        .map((e) => `${py(e.sourceHandle!)}: ${target(c, e.target)}`);
      routingImports.add(`route_${src.data.name}`);
      lines.push(`    builder.add_conditional_edges(${srcExpr}, route_${src.data.name}, {${pm.join(", ")}})`);
      continue;
    }
    if (src.kind === "human" && outs.some((e) => e.sourceHandle === "reject")) {
      const approve = outs.find((e) => e.sourceHandle !== "reject");
      const reject = outs.find((e) => e.sourceHandle === "reject")!;
      routingImports.add(`route_${src.data.name}`);
      lines.push(
        `    builder.add_conditional_edges(${srcExpr}, route_${src.data.name}, {"approve": ${approve ? target(c, approve.target) : "END"}, "reject": ${target(c, reject.target)}})`,
      );
      continue;
    }
    for (const e of outs) {
      const t = c.byId.get(e.target);
      if (!t) continue;
      if (t.kind === "router") {
        const pm = (c.out.get(t.id) ?? []).map((x) => `${py(targetKey(c, x.target))}: ${target(c, x.target)}`);
        routingImports.add(t.data.name);
        lines.push(`    builder.add_conditional_edges(${srcExpr}, ${t.data.name}, {${pm.join(", ")}})`);
      } else if (t.kind === "map") {
        const w = (c.out.get(t.id) ?? [])[0];
        routingImports.add(t.data.name);
        lines.push(`    builder.add_conditional_edges(${srcExpr}, ${t.data.name}, [${w ? target(c, w.target) : "END"}])`);
      } else {
        const key = `${srcExpr}->${target(c, e.target)}`;
        if (handled.has(key)) continue;
        handled.add(key);
        lines.push(`    builder.add_edge(${srcExpr}, ${target(c, e.target)})`);
      }
    }
  }

  const cp = !c.isRoot
    ? null
    : s.checkpointer === "memory"
      ? { imp: "from langgraph.checkpoint.memory import InMemorySaver", make: "InMemorySaver()" }
      : s.checkpointer === "sqlite"
        ? {
            imp: "import sqlite3\n\nfrom langgraph.checkpoint.sqlite import SqliteSaver",
            make: 'SqliteSaver(sqlite3.connect("checkpoints.db", check_same_thread=False))',
          }
        : null;
  const needsRetry = c.real.some((n) => n.kind === "agent" || n.kind === "llm");
  const stdImports = cp?.imp.startsWith("import sqlite3") ? "import sqlite3\n\n" : "";
  const usesEnd = lines.some((l) => /\bEND\b/.test(l));
  const lgImports = [
    `from langgraph.graph import ${usesEnd ? "END, " : ""}START, StateGraph`,
    ...(cp ? [cp.imp.replace("import sqlite3\n\n", "")] : []),
    ...(s.store && c.isRoot ? ["from langgraph.store.memory import InMemoryStore"] : []),
    ...(needsRetry ? ["from langgraph.types import RetryPolicy"] : []),
  ].sort();

  if (!c.isRoot) {
    return `"""서브그래프 '${c.graphName}' 조립.

부모 그래프의 노드로 쓰이는 하위 에이전트다. 체크포인터는 부모에서 자동으로 이어받으므로
여기서 따로 만들지 않는다${c.memory === "persistent" ? " (checkpointer=True: thread 마다 이 서브그래프의 대화를 따로 기억한다)" : ""}.
단독으로 테스트하려면: python -c "from ${c.pkg}.graph import graph; print(graph.invoke({'messages': [('user', '안녕')]}))"
"""

${lgImports.join("\n")}

from ${c.pkg}.nodes import ${nodeImports.join(", ") || "# (노드 없음)"}
${routingImports.size ? `from ${c.pkg}.routing import ${[...routingImports].sort().join(", ")}\n` : ""}from ${c.pkg}.state import State


def build_graph(checkpointer=${c.memory === "persistent" ? "True" : "None"}):
    """하위 StateGraph 를 구성하고 컴파일한다."""
    builder = StateGraph(State)

${lines.join("\n")}

    return builder.compile(checkpointer=checkpointer, name=${py(c.graphName)})


graph = build_graph()
`;
  }

  return `"""그래프 조립: 노드 등록 → 엣지 연결 → 컴파일.

이 파일은 플레이그라운드 캔버스의 구조를 그대로 반영한다.
"""

${stdImports}${lgImports.join("\n")}

from ${c.pkg}.nodes import ${nodeImports.join(", ") || "# (노드 없음)"}
${routingImports.size ? `from ${c.pkg}.routing import ${[...routingImports].sort().join(", ")}\n` : ""}from ${c.pkg}.state import State


def build_graph(${cp ? "checkpointer=None, use_default_checkpointer: bool = True" : "checkpointer=None"}):
    """StateGraph 를 구성하고 컴파일한다."""
    builder = StateGraph(State)

${lines.join("\n")}

${cp ? `    if checkpointer is None and use_default_checkpointer:\n        checkpointer = ${cp.make}\n` : ""}    return builder.compile(checkpointer=checkpointer${s.store ? ", store=InMemoryStore()" : ""}, name=${py("agent")})


# LangGraph Server(langgraph.json)용 export — 서버가 자체 체크포인터를 주입한다.
graph = build_graph(${cp ? "use_default_checkpointer=False" : ""})
`;
}

function nodesInit(c: Ctx): string {
  return `"""노드 패키지: 각 노드는 개별 모듈로 분리되어 있다."""

${c.real
  .map((n) => n.data.name)
  .sort()
  .map((n) => `from ${c.pkg}.nodes.${n} import ${n}`)
  .join("\n")}

__all__ = [${c.real
    .map((n) => py(n.data.name))
    .sort()
    .join(", ")}]
`;
}

function mainFile(c: Ctx): string {
  const s = c.g.settings;
  const everything = allNodes(c.g);
  const hasHuman = everything.some((n) => n.kind === "human");
  const hasSub = everything.some((n) => n.kind === "subgraph");
  const trace = `"run_name": "agentlab-demo", "tags": ["agentlab", "demo"], "metadata": {"source": "agentlab-playground"}`;
  const cfg = s.checkpointer !== "none" ? `{"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": ${s.recursionLimit}, ${trace}}` : `{"recursion_limit": ${s.recursionLimit}, ${trace}}`;
  return `"""실행 진입점: 데모 입력으로 그래프를 스트리밍 실행한다.

    python main.py
"""

${s.checkpointer !== "none" ? "import uuid\n\n" : ""}from langgraph.errors import GraphRecursionError
${hasHuman ? "from langgraph.types import Command\n" : ""}
from agent.graph import build_graph

DEMO_INPUT = ${py(s.demoInput)}


def show(update: object) -> None:
    """노드가 반환한 상태 업데이트를 읽기 좋게 출력한다."""
    if not isinstance(update, dict):
        return
    for msg in update.get("messages", []) or []:
        role = getattr(msg, "type", "?")
        name = f"({msg.name})" if getattr(msg, "name", None) else ""
        if getattr(msg, "tool_calls", None):
            calls = ", ".join(f"{t['name']}({t['args']})" for t in msg.tool_calls)
            print(f"   [{role}{name}] 🛠  {calls}")
        else:
            print(f"   [{role}{name}] {str(msg.content)[:400]}")
    for key, value in update.items():
        if key != "messages":
            print(f"   · {key} = {str(value)[:200]}")


${
  hasSub
    ? `def run(graph, payload, config) -> bool:
    """스트리밍 실행. interrupt 가 발생하면 True 를 반환한다.

    subgraphs=True 로 서브 에이전트 내부 노드의 업데이트도 함께 받는다.
    ns(namespace)는 ("researcher:<task id>", ...) 처럼 바깥 → 안쪽 순서의 경로다.
    """
    for ns, chunk in graph.stream(payload, config, stream_mode="updates", subgraphs=True):
        where = "".join(f"{part.split(':')[0]} › " for part in ns)
        for node, update in chunk.items():
            if node == "__interrupt__":
                for it in update:
                    print(f"\\n⏸  interrupt ({where.rstrip(' ›') or 'root'}): {it.value}")
                return True
            print(f"\\n{'  ' * len(ns)}▶ {where}{node}")
            show(update)
    return False`
    : `def run(graph, payload, config) -> bool:
    """스트리밍 실행. interrupt 가 발생하면 True 를 반환한다."""
    for chunk in graph.stream(payload, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                for it in update:
                    print(f"\\n⏸  interrupt: {it.value}")
                return True
            print(f"\\n▶ {node}")
            show(update)
    return False`
}


def main() -> None:
    graph = build_graph()
    config = ${cfg}
    print("노드:", ", ".join(n for n in graph.get_graph().nodes if not n.startswith("__")))
    print(f"입력: {DEMO_INPUT}")
    try:
        interrupted = run(graph, {"messages": [{"role": "user", "content": DEMO_INPUT}]}, config)
${
  hasHuman
    ? `        # 데모: 사람이 승인했다고 가정하고 재개한다. (실서비스에서는 UI/API 로 결정을 받는다)
        resumes = 0
        while interrupted and resumes < 5:
            resumes += 1
            print("👤 승인 → Command(resume=...) 로 재개")
            interrupted = run(graph, Command(resume={"approved": True}), config)`
    : `        if interrupted:
            print("(interrupt 발생 — Command(resume=...) 로 재개하세요)")`
}
    except GraphRecursionError:
        print("\\n⛔ recursion_limit 초과: 루프의 종료 조건을 확인하세요.")
        raise
    print("\\n✅ 실행 완료")


if __name__ == "__main__":
    main()
`;
}

function mermaid(c: Ctx): string {
  const lines = ["flowchart TD"];
  const level = (g: SubGraph, prefix: string, pad: string) => {
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const id = (n: GNode) => prefix + (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name);
    for (const n of g.nodes) {
      if (n.kind === "subgraph" && n.data.graph) {
        lines.push(`${pad}subgraph ${id(n)} [${n.data.name}]`);
        level(n.data.graph, `${id(n)}__`, pad + "  ");
        lines.push(`${pad}end`);
        continue;
      }
      const shape = n.kind === "router" || n.kind === "map" ? `{${n.data.name}}` : n.kind === "start" || n.kind === "end" ? `([${n.kind.toUpperCase()}])` : `[${n.data.name}]`;
      lines.push(`${pad}${id(n)}${shape}`);
    }
    for (const e of g.edges) {
      const s = byId.get(e.source);
      const t = byId.get(e.target);
      if (!s || !t) continue;
      const cond = ["router", "evaluator", "supervisor", "map"].includes(s.kind) || e.sourceHandle === "reject";
      lines.push(`${pad}${id(s)} ${cond ? "-.->" : "-->"}${e.sourceHandle && e.sourceHandle !== "out" ? `|${e.sourceHandle}|` : ""} ${id(t)}`);
    }
  };
  level(c.g, "", "  ");
  return lines.join("\n");
}

/** 모든 서브그래프 (경로 포함) */
function subagents(g: SubGraph) {
  const out: { node: GNode; pkg: string; names: string[] }[] = [];
  walkGraphs(g, (_lv, path, owner) => {
    if (!owner) return;
    const names: string[] = [];
    let cur: SubGraph = g;
    for (const id of path) {
      const n = cur.nodes.find((x) => x.id === id)!;
      names.push(n.data.name);
      cur = n.data.graph!;
    }
    out.push({ node: owner, names, pkg: ["agent", ...names.flatMap((nm) => ["subagents", nm])].join(".") });
  });
  return out;
}

function readme(c: Ctx): string {
  const subs = subagents(c.g);
  const subTable = subs.length
    ? `
## 서브 에이전트

| 경로 | 노드 | 입출력 | 메모리 | 역할 |
| --- | --- | --- | --- | --- |
${subs.map((x) => `| \`${x.pkg.replace(/\./g, "/")}/\` | ${x.names.join(" › ")} | ${x.node.data.io === "shared" ? "상태 공유" : "격리 (최종 답변만)"} | ${x.node.data.memory === "persistent" ? "독립 영속" : "부모 상속"} | ${x.node.data.description ?? ""} |`).join("\n")}

각 서브 에이전트는 독립된 패키지라서 단독으로 실행·테스트할 수 있고, \`langgraph dev\` 에서도 별도 그래프로 열립니다.
`
    : "";
  return `# LangGraph Agent (AgentLab Playground 생성)

\`\`\`mermaid
${mermaid(c)}
\`\`\`

## 실행

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env  # OPENAI_API_KEY 입력
python main.py
\`\`\`

## 구조

| 파일 | 역할 |
| --- | --- |
| \`agent/state.py\` | 공유 상태 스키마와 리듀서 |
| \`agent/nodes/*.py\` | 노드별 구현 (${c.real.map((n) => n.data.name).join(", ")}) |
${c.g.nodes.some((n) => ["router", "map", "evaluator"].includes(n.kind)) ? "| `agent/routing.py` | 조건부 엣지 라우팅 함수 / Send fan-out |\n" : ""}${subs.length ? "| `agent/subagents/<이름>/` | 서브 에이전트 패키지 (각자 state/nodes/routing/graph) |\n" : ""}${c.usedTools.length ? "| `agent/tools.py` | 도구 정의 |\n" : ""}| \`agent/graph.py\` | StateGraph 조립 및 컴파일 |
| \`main.py\` | 스트리밍 실행 데모 |
| \`langgraph.json\` | LangGraph Server(Agent Server) 배포 설정 |
${subTable}
## 배포

\`\`\`bash
pip install -U "langgraph-cli[inmem]"
langgraph dev   # 로컬 Agent Server + Studio
\`\`\`
`;
}

/** LLM 을 호출하지 않는 구조 테스트: 각 그래프가 캔버스와 같은 노드로 컴파일되는지 */
function testFile(c: Ctx): string {
  const nodesOf = (g: SubGraph) => g.nodes.filter((n) => !VIRTUAL.has(n.kind)).map((n) => n.data.name).sort();
  const subs = subagents(c.g).map((x) => {
    let cur: SubGraph = c.g;
    for (const nm of x.names) cur = cur.nodes.find((n) => n.data.name === nm && n.kind === "subgraph")!.data.graph!;
    return { module: `${x.pkg}.graph`, test: x.names.join("__"), nodes: nodesOf(cur) };
  });
  const set = (xs: string[]) => (xs.length ? `{${xs.map(py).join(", ")}}` : "set()");
  return `"""구조 테스트: LLM 을 호출하지 않고 그래프가 캔버스와 같은 모양으로 컴파일되는지 확인한다.

    pip install -r requirements-dev.txt
    pytest -q

CI 에 넣어 두면 노드 이름 변경·연결 누락 같은 회귀를 실제 호출 비용 없이 잡을 수 있다.
"""

import pytest


@pytest.fixture(autouse=True)
def _fake_key(monkeypatch):
    # 모델 객체를 만들 때 키가 있어야 하지만, 이 테스트는 모델을 호출하지 않는다
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")


def _nodes(graph) -> set[str]:
    return {n for n in graph.get_graph().nodes if not n.startswith("__")}


def test_root_graph():
    from agent.graph import graph

    assert _nodes(graph) == ${set(nodesOf(c.g))}
${subs
  .map(
    (x) => `

def test_subagent_${x.test}():
    from ${x.module} import graph

    assert _nodes(graph) == ${set(x.nodes)}
`,
  )
  .join("")}`;
}

/** 한 그래프(최상위 또는 서브그래프)의 패키지 파일: state / nodes / routing / graph */
function graphPackage(c: Ctx, files: Record<string, string>) {
  if (!c.isRoot) files[`${c.dir}/__init__.py`] = `"""서브 에이전트 '${c.graphName}'."""\n\nfrom ${c.pkg}.graph import build_graph, graph\n\n__all__ = ["build_graph", "graph"]\n`;
  files[`${c.dir}/state.py`] = stateFile(c);
  files[`${c.dir}/nodes/__init__.py`] = nodesInit(c);
  for (const n of c.real) files[`${c.dir}/nodes/${n.data.name}.py`] = withOs(nodeFile(c, n));
  const routing = routingFile(c);
  if (routing) files[`${c.dir}/routing.py`] = routing;
  files[`${c.dir}/graph.py`] = graphFile(c);
  const subs = c.real.filter((n) => n.kind === "subgraph" && n.data.graph);
  if (subs.length) files[`${c.dir}/subagents/__init__.py`] = `"""'${c.graphName}' 이(가) 사용하는 서브 에이전트 패키지."""\n`;
  for (const n of subs)
    graphPackage(context({ ...n.data.graph!, settings: c.g.settings }, `${c.pkg}.subagents.${n.data.name}`, n.data.name, n.data.memory ?? "inherit"), files);
}

export function generateProject(g: Graph): Record<string, string> {
  const c = context(g);
  const files: Record<string, string> = {};
  const everything = allNodes(g);
  files["main.py"] = mainFile(c);
  files["agent/__init__.py"] = '"""AgentLab 플레이그라운드에서 생성된 LangGraph 에이전트."""\n';
  files["agent/config.py"] = configFile();
  if (c.usedTools.length) files["agent/tools.py"] = toolsFile(c);
  if (everything.some((n) => n.kind === "retriever")) files["agent/retriever.py"] = retrieverFile();
  graphPackage(c, files);
  const graphs: Record<string, string> = { agent: "./agent/graph.py:graph" };
  // 부모 상속 메모리인 서브 에이전트는 Agent Server 에서도 단독 그래프로 노출한다
  for (const x of subagents(g)) if (x.node.data.memory !== "persistent") graphs[x.names.join("__")] = `./${x.pkg.replace(/\./g, "/")}/graph.py:graph`;
  // 노드별 모델이 다른 공급자를 쓰면 해당 통합 패키지를 추가한다
  const providers = new Set(["langchain-openai>=1.7", ...everything.filter((n) => n.data.model?.trim()).map((n) => PROVIDER_PACKAGES[providerOf(n.data.model)]).filter(Boolean)]);
  files["requirements.txt"] = `langgraph>=1.2\nlangchain>=1.4\n${[...providers].sort().join("\n")}\n${g.settings.checkpointer === "sqlite" ? "langgraph-checkpoint-sqlite>=3.1\n" : ""}python-dotenv\n`;
  files["requirements-dev.txt"] = "-r requirements.txt\npytest>=8\nruff>=0.8\n";
  files[".gitignore"] = ".env\n.venv/\n__pycache__/\n*.pyc\ncheckpoints.db*\n.langgraph_api/\n.pytest_cache/\n.ruff_cache/\n";
  files["tests/__init__.py"] = "";
  files["tests/test_graph.py"] = testFile(c);
  files["langgraph.json"] = JSON.stringify({ $schema: "https://langgra.ph/schema.json", dependencies: ["."], graphs, env: ".env" }, null, 2) + "\n";
  files[".env.example"] = "OPENAI_API_KEY=sk-...\nLAB_MODEL=openai:gpt-5-mini\n# LangSmith 트레이싱 (선택)\nLANGSMITH_TRACING=true\nLANGSMITH_API_KEY=\n";
  files["README.md"] = readme(c);
  return files;
}

/** 서버 캐시 키 계산용: 좌표/임의 id 를 제거하고 노드 이름 기준으로 정규화 (서브그래프까지 재귀) */
export function normalizeGraph(g: Graph) {
  return { ...normalizeLevel(g), settings: g.settings };
}

type NormNode = { id: string; type: string; data: Record<string, unknown> };
function normalizeLevel(g: SubGraph): { nodes: NormNode[]; edges: { source: string; target: string; sourceHandle: string | null; label: null }[] } {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const name = (id: string) => {
    const n = byId.get(id);
    return n ? (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name) : id;
  };
  return {
    nodes: g.nodes.map((n) => {
      const { graph, preset, ...data } = n.data;
      void preset; // 출처 정보는 코드에 영향이 없다
      return { id: name(n.id), type: n.kind, data: graph ? { ...data, graph: normalizeLevel(graph) } : { ...data } };
    }),
    edges: g.edges.map((e) => ({ source: name(e.source), target: name(e.target), sourceHandle: e.sourceHandle ?? null, label: null })),
  };
}
