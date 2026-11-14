// 코드 생성 컨텍스트: 그래프를 한 번 훑어 인접 리스트·사용 도구 등을 계산하고, 문자열 도우미를 제공한다.
import type { GEdge, GNode, Graph } from "../types.ts";
import { TOOL_LIBRARY } from "../catalog.ts";

export const GENERATOR_VERSION = "2026.10-1";

export const VIRTUAL = new Set(["start", "end", "router", "map"]);
export const py = (s: string) => JSON.stringify(s ?? "");
export const indent = (s: string, n = 4) =>
  s
    .split("\n")
    .map((l) => (l.trim() ? " ".repeat(n) + l : ""))
    .join("\n");
export const pascal = (s: string) => s.replace(/(^|_)([a-z0-9])/g, (_, __, c: string) => c.toUpperCase());

export type Ctx = {
  g: Graph;
  byId: Map<string, GNode>;
  out: Map<string, GEdge[]>;
  inc: Map<string, GEdge[]>;
  real: GNode[];
  hasRetriever: boolean;
  hasMap: boolean;
  hasResults: boolean;
  usedTools: string[];
};

export function context(g: Graph): Ctx {
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
  const usedTools = [...new Set(g.nodes.filter((n) => n.kind === "tools" || n.kind === "agent").flatMap((n) => n.data.tools ?? []))].filter(
    (t) => TOOL_LIBRARY[t],
  );
  const hasMap = g.nodes.some((n) => n.kind === "map");
  return {
    g,
    byId,
    out,
    inc,
    real,
    hasRetriever: g.nodes.some((n) => n.kind === "retriever"),
    hasMap,
    hasResults: hasMap || g.nodes.some((n) => n.kind === "reduce"),
    usedTools,
  };
}

/** 노드 id → 파이썬 대상 표현식 (END 또는 "name") */
export const target = (c: Ctx, id: string) => {
  const n = c.byId.get(id);
  if (!n || n.kind === "end") return "END";
  return py(n.data.name);
};
export const targetKey = (c: Ctx, id: string) => {
  const n = c.byId.get(id);
  return !n || n.kind === "end" ? "__end__" : n.data.name;
};

/** LLM 노드 뒤 tools_condition 라우터가 가리키는 Tools 노드들의 도구 */
export function boundTools(c: Ctx, n: GNode): string[] {
  const tools = new Set<string>();
  for (const e of c.out.get(n.id) ?? []) {
    const r = c.byId.get(e.target);
    if (r?.kind !== "router" || r.data.strategy !== "tools_condition") continue;
    for (const e2 of c.out.get(r.id) ?? []) {
      const t = c.byId.get(e2.target);
      if (t?.kind === "tools") (t.data.tools ?? []).forEach((x) => TOOL_LIBRARY[x] && tools.add(x));
    }
  }
  return [...tools];
}

export const isMapWorker = (c: Ctx, n: GNode) => (c.inc.get(n.id) ?? []).some((e) => c.byId.get(e.source)?.kind === "map");
export const supervisorOf = (c: Ctx, n: GNode) =>
  (c.inc.get(n.id) ?? []).map((e) => c.byId.get(e.source)).find((s) => s?.kind === "supervisor" && (c.out.get(n.id) ?? []).some((x) => x.target === s.id));
