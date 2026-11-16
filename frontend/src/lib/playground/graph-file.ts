// agentlab.json: 플레이그라운드 그래프 원본 명세 (저장소에 커밋, 리뷰, 다시 가져오기)
import type { GEdge, GNode, Graph, SubGraph } from "./types.ts";
import { DEFAULT_SETTINGS } from "./types.ts";
import { KINDS } from "./catalog.ts";
import { GENERATOR_VERSION } from "./codegen.ts";

export const GRAPH_FORMAT = "agentlab.graph";
export const PRESET_FORMAT = "agentlab.preset";

export function exportGraphJson(g: Graph): string {
  return JSON.stringify({ format: GRAPH_FORMAT, version: 1, generator: GENERATOR_VERSION, graph: g }, null, 2) + "\n";
}

const MAX_NODES = 500;

/** 외부에서 온 그래프를 검증한다. 모르는 노드 종류나 깨진 엣지는 거부한다. */
export function checkSub(raw: unknown, depth = 0): SubGraph {
  if (depth > 6) throw new Error("서브그래프가 너무 깊습니다.");
  const g = raw as { nodes?: unknown; edges?: unknown; tools?: unknown };
  if (!g || !Array.isArray(g.nodes) || !Array.isArray(g.edges)) throw new Error("nodes/edges 배열이 없습니다.");
  if (g.nodes.length > MAX_NODES) throw new Error("노드가 너무 많습니다.");
  const ids = new Set<string>();
  const nodes: GNode[] = g.nodes.map((n: GNode) => {
    if (!n || typeof n.id !== "string" || !KINDS[n.kind] || typeof n.data?.name !== "string") throw new Error(`잘못된 노드: ${JSON.stringify(n).slice(0, 80)}`);
    ids.add(n.id);
    const data = { ...n.data };
    if (n.kind === "subgraph") data.graph = checkSub(n.data.graph ?? { nodes: [], edges: [] }, depth + 1);
    const position = n.position && Number.isFinite(n.position.x) && Number.isFinite(n.position.y) ? { x: n.position.x, y: n.position.y } : { x: 0, y: 0 };
    return { id: n.id, kind: n.kind, data, position };
  });
  const edges: GEdge[] = g.edges.map((e: GEdge) => {
    if (!e || !ids.has(e.source) || !ids.has(e.target)) throw new Error("존재하지 않는 노드를 잇는 엣지가 있습니다.");
    return { id: typeof e.id === "string" ? e.id : `e-${e.source}-${e.target}`, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null };
  });
  const tools = Array.isArray(g.tools) ? (g.tools as SubGraph["tools"])!.filter((t) => t && typeof t.name === "string" && typeof t.code === "string") : undefined;
  return { nodes, edges, ...(tools?.length ? { tools } : {}) };
}

export function parseGraphJson(text: string): Graph {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error("JSON 형식이 아닙니다.");
  }
  const obj = raw as { format?: string; graph?: unknown; settings?: unknown };
  const body = (obj?.format === GRAPH_FORMAT ? obj.graph : raw) as Graph;
  const sub = checkSub(body);
  return { nodes: sub.nodes, edges: sub.edges, settings: { ...DEFAULT_SETTINGS, ...((body as Graph).settings ?? {}) } };
}
