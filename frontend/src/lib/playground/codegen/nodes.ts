// 노드별 파이썬 모듈 (agent/nodes/*.py, 서브 에이전트 패키지 포함).
import type { GNode } from "../types.ts";
import type { Ctx } from "./context.ts";
import { agentModelExpr, boundTools, indent, isMapWorker, llmExpr, py, supervisorOf, target } from "./context.ts";

export function contextLine(c: Ctx) {
  return c.hasRetriever
    ? `    if state.get("context"):
        system += "\\n\\n[참고 문서]\\n" + state["context"]
`
    : "";
}

export function nodeFile(c: Ctx, n: GNode): string {
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
      const mw = middlewareCode(c, n, tools);
      return `${header(`'${name}' — create_agent 로 만든 완성형 ReAct 에이전트를 노드로 사용한다.

에이전트 내부에서 모델 호출 ↔ 도구 실행 루프가 돌고, 최종 답변만 부모 그래프로 돌려준다
(컨텍스트 격리: 부모 대화에 도구 호출 기록이 쌓이지 않는다).`, [
        "from langchain.agents import create_agent",
        ...(mw.classes.length ? [`from langchain.agents.middleware import ${mw.classes.join(", ")}`] : []),
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
${mw.lines.length ? `    middleware=[\n${mw.lines.join("\n")}\n    ],\n` : ""}    name=${py(name)},
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
        "from langchain.messages import HumanMessage, ToolMessage",
        "from langgraph.types import interrupt",
        "",
        `from ${c.pkg}.state import State`,
      ])}
QUESTION = ${py(n.data.prompt ?? "승인하시겠습니까?")}


def ${name}(state: State) -> dict:
    """사람의 승인/거절과 피드백을 받는다. 직전 메시지가 도구 호출이면 그 호출을 승인받는다."""
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []
    request: dict = {"question": QUESTION, "draft": last.text}
    if calls:
        request["tool_calls"] = [{"name": c["name"], "args": c["args"]} for c in calls]
    decision = interrupt(request)
    if not isinstance(decision, dict):
        decision = {"approved": bool(decision)}
    approved = decision.get("approved", True)
    update: dict = {${py(`${n.data.name}_decision`)}: "approve" if approved else "reject"}
    feedback = decision.get("feedback") or ""
    if not approved and calls:
        # 도구 호출마다 응답(ToolMessage)이 있어야 모델이 대화를 이어갈 수 있다 (tool_calls 프로토콜)
        update["messages"] = [ToolMessage(content=f"[검토자 거절] {feedback or '실행하지 않았습니다.'}", tool_call_id=c["id"]) for c in calls]
    elif not approved and feedback:
        update["messages"] = [HumanMessage(f"[검토자 피드백] {feedback}")]
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

/** Agent 노드의 미들웨어 → create_agent(middleware=[...]) 항목. 리스트의 앞쪽이 바깥에서 감싼다. */
export function middlewareCode(c: Ctx, n: GNode, tools: string[]): { classes: string[]; lines: string[] } {
  const mw = n.data.middleware;
  const items: [cls: string, code: string, comment: string][] = [];
  if (!mw) return { classes: [], lines: [] };
  if (mw.summarization)
    items.push(["SummarizationMiddleware", `SummarizationMiddleware(${agentModelExpr(c, n)}, trigger=("tokens", ${mw.summarization.tokens}))`, `대화가 ${mw.summarization.tokens} 토큰을 넘으면 오래된 메시지를 요약으로 바꾼다`]);
  for (const t of mw.pii?.types ?? [])
    items.push(["PIIMiddleware", `PIIMiddleware(${py(t)}, strategy=${py(mw.pii!.strategy)})`, `모델에 보내기 전 사용자 입력의 ${t} 처리`]);
  if (mw.modelCallLimit) items.push(["ModelCallLimitMiddleware", `ModelCallLimitMiddleware(run_limit=${mw.modelCallLimit})`, `실행 한 번에 모델 호출 최대 ${mw.modelCallLimit}회 (넘으면 안내 메시지로 끝낸다)`]);
  if (mw.toolCallLimit) items.push(["ToolCallLimitMiddleware", `ToolCallLimitMiddleware(run_limit=${mw.toolCallLimit})`, `실행 한 번에 도구 호출 최대 ${mw.toolCallLimit}회 (넘는 호출은 오류 메시지로 막고 계속한다)`]);
  if (mw.retry) {
    items.push(["ModelRetryMiddleware", `ModelRetryMiddleware(max_retries=${mw.retry.maxRetries})`, "모델 호출 실패 시 지수 백오프로 재시도"]);
    items.push(["ToolRetryMiddleware", `ToolRetryMiddleware(max_retries=${mw.retry.maxRetries})`, "도구 실행 실패 시 재시도"]);
  }
  if (mw.fallback) items.push(["ModelFallbackMiddleware", `ModelFallbackMiddleware(${py(mw.fallback)})`, "기본 모델이 실패하면 이 모델로 다시 시도"]);
  const approve = (mw.hitl?.tools ?? []).filter((t) => tools.includes(t));
  if (approve.length)
    items.push(["HumanInTheLoopMiddleware", `HumanInTheLoopMiddleware(interrupt_on={${approve.map((t) => `${py(t)}: True`).join(", ")}})`, "이 도구들은 실행 전에 사람 승인 (interrupt, 체크포인터 필요)"]);
  return { classes: [...new Set(items.map((i) => i[0]))].sort(), lines: items.map(([, code, comment]) => `        # ${comment}\n        ${code},`) };
}
