// 코드 생성 컨텍스트: 그래프를 한 번 훑어 인접 리스트·사용 도구 등을 계산하고, 문자열 도우미를 제공한다.
import type { ToolDef } from "../catalog.ts";
import { toolCatalog } from "../catalog.ts";
import { allNodes } from "../subgraph.ts";
import type { GEdge, GNode, GraphSettings, SubGraph } from "../types.ts";

export const GENERATOR_VERSION = "2026.11-1";

export const VIRTUAL = new Set(["start", "end", "router", "map"]);

export const py = (s: string) => JSON.stringify(s ?? "");

export const indent = (s: string, n = 4) =>
  s
    .split("\n")
    .map((l) => (l.trim() ? " ".repeat(n) + l : ""))
    .join("\n");

export const pascal = (s: string) => s.replace(/(^|_)([a-z0-9])/g, (_, __, c: string) => c.toUpperCase());

export type Ctx = {
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

export function context(g: SubGraph & { settings: GraphSettings }, pkg = "agent", graphName = "agent", memory: Ctx["memory"] = "inherit"): Ctx {
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
export const modelEnv = (c: Ctx, n: GNode) => `LAB_MODEL__${c.envPrefix}${n.data.name.toUpperCase()}`;

export const llmExpr = (c: Ctx, n: GNode) => (n.data.model?.trim() ? `get_llm(os.getenv(${py(modelEnv(c, n))}, ${py(n.data.model.trim())}))` : "get_llm()");

export const agentModelExpr = (c: Ctx, n: GNode) => (n.data.model?.trim() ? `os.getenv(${py(modelEnv(c, n))}, ${py(n.data.model.trim())})` : "MODEL");

/** 파일이 os.getenv 를 쓰면 docstring 뒤에 import os 를 넣는다 */
export const withOs = (src: string) => (/\bos\.getenv\(/.test(src) && !/^import os$/m.test(src) ? src.replace(/^("""[\s\S]*?"""\n\n)/, "$1import os\n\n") : src);

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
      if (t?.kind === "tools") (t.data.tools ?? []).forEach((x) => c.tools[x] && tools.add(x));
    }
  }
  return [...tools];
}

export const isMapWorker = (c: Ctx, n: GNode) => (c.inc.get(n.id) ?? []).some((e) => c.byId.get(e.source)?.kind === "map");

export const supervisorOf = (c: Ctx, n: GNode) =>
  (c.inc.get(n.id) ?? []).map((e) => c.byId.get(e.source)).find((s) => s?.kind === "supervisor" && (c.out.get(n.id) ?? []).some((x) => x.target === s.id));

/* ======================================================================== files */
