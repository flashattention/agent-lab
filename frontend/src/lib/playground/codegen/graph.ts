// StateGraph 조립 (agent/graph.py) 과 노드 패키지 __init__.
import { VIRTUAL, py, target, targetKey } from "./context.ts";
import type { Ctx } from "./context.ts";

export function graphFile(c: Ctx): string {
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

  const cp =
    s.checkpointer === "memory"
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
    ...(s.store ? ["from langgraph.store.memory import InMemoryStore"] : []),
    ...(needsRetry ? ["from langgraph.types import RetryPolicy"] : []),
  ].sort();

  return `"""그래프 조립: 노드 등록 → 엣지 연결 → 컴파일.

이 파일은 플레이그라운드 캔버스의 구조를 그대로 반영한다.
"""

${stdImports}${lgImports.join("\n")}

from agent.nodes import ${nodeImports.join(", ") || "# (노드 없음)"}
${routingImports.size ? `from agent.routing import ${[...routingImports].sort().join(", ")}\n` : ""}from agent.state import State


def build_graph(${cp ? "checkpointer=None, use_default_checkpointer: bool = True" : "checkpointer=None"}):
    """StateGraph 를 구성하고 컴파일한다."""
    builder = StateGraph(State)

${lines.join("\n")}

${cp ? `    if checkpointer is None and use_default_checkpointer:\n        checkpointer = ${cp.make}\n` : ""}    return builder.compile(checkpointer=checkpointer${s.store ? ", store=InMemoryStore()" : ""}, name=${py("agent")})


# LangGraph Server(langgraph.json)용 export — 서버가 자체 체크포인터를 주입한다.
graph = build_graph(${cp ? "use_default_checkpointer=False" : ""})
`;
}

export function nodesInit(c: Ctx): string {
  return `"""노드 패키지: 각 노드는 개별 모듈로 분리되어 있다."""

${c.real
  .map((n) => n.data.name)
  .sort()
  .map((n) => `from agent.nodes.${n} import ${n}`)
  .join("\n")}

__all__ = [${c.real
    .map((n) => py(n.data.name))
    .sort()
    .join(", ")}]
`;
}
