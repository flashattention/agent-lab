// 서브그래프(하위 에이전트) 관련 순수 함수: 기본 그래프, 순회, 묶기/펼치기.
// React Flow 와 무관한 GNode/GEdge 만 다루므로 코드 생성기·분석기·스토어가 함께 쓴다.
import type { GEdge, GNode, SubGraph } from "./types.ts";

const rid = () => Math.random().toString(36).slice(2, 9);

/** 새 Sub-agent 노드의 안쪽 그래프: 도구를 쓰는 작은 ReAct 루프 */
export function defaultSubGraph(): SubGraph {
  return {
    nodes: [
      { id: "start", kind: "start", data: { name: "__start__" }, position: { x: 50, y: 0 } },
      {
        id: "assistant",
        kind: "llm",
        data: { name: "assistant", prompt: "당신은 맡은 하위 작업을 처리하는 전문 에이전트입니다. 필요하면 도구를 쓰고, 끝나면 결과만 간결하게 보고하세요." },
        position: { x: 0, y: 110 },
      },
      { id: "should_continue", kind: "router", data: { name: "should_continue", strategy: "tools_condition" }, position: { x: 0, y: 250 } },
      { id: "tools", kind: "tools", data: { name: "tools", tools: ["web_search"] }, position: { x: 280, y: 360 } },
      { id: "end", kind: "end", data: { name: "__end__" }, position: { x: 50, y: 400 } },
    ],
    edges: [
      { id: "e-start-assistant", source: "start", target: "assistant" },
      { id: "e-assistant-route", source: "assistant", target: "should_continue" },
      { id: "e-route-tools", source: "should_continue", target: "tools" },
      { id: "e-route-end", source: "should_continue", target: "end" },
      { id: "e-tools-assistant", source: "tools", target: "assistant" },
    ],
  };
}

/** create_agent 노드 하나를 START → agent → END 그래프로 감싼다 (프리셋 저장용) */
export function wrapNode(n: GNode): SubGraph {
  return {
    nodes: [
      { id: "start", kind: "start", data: { name: "__start__" }, position: { x: 50, y: 0 } },
      { ...n, id: n.data.name, data: { ...n.data, preset: undefined }, position: { x: 0, y: 110 } },
      { id: "end", kind: "end", data: { name: "__end__" }, position: { x: 50, y: 260 } },
    ],
    edges: [
      { id: "e-start", source: "start", target: n.data.name },
      { id: "e-end", source: n.data.name, target: "end" },
    ],
  };
}

export const cloneSub = (g: SubGraph): SubGraph => JSON.parse(JSON.stringify({ nodes: g.nodes, edges: g.edges }));

/** 모든 좌표가 같으면(패턴/프리셋처럼 좌표가 없는 그래프) 자동 배치가 필요하다 */
export const needsLayout = (nodes: { position: { x: number; y: number } }[]) =>
  nodes.length > 1 && nodes.every((n) => n.position.x === nodes[0].position.x && n.position.y === nodes[0].position.y);

/** 그래프와 모든 하위 그래프를 깊이 우선으로 방문한다. path 는 subgraph 노드 id 목록. */
export function walkGraphs(g: SubGraph, fn: (level: SubGraph, path: string[], owner: GNode | null) => void, path: string[] = [], owner: GNode | null = null) {
  fn(g, path, owner);
  for (const n of g.nodes) if (n.kind === "subgraph" && n.data.graph) walkGraphs(n.data.graph, fn, [...path, n.id], n);
}

export const allNodes = (g: SubGraph) => {
  const out: GNode[] = [];
  walkGraphs(g, (lv) => out.push(...lv.nodes));
  return out;
};

/** 서브그래프 깊이 (자기 자신 = 0) */
export function depthOf(g: SubGraph): number {
  return Math.max(0, ...g.nodes.filter((n) => n.kind === "subgraph" && n.data.graph).map((n) => 1 + depthOf(n.data.graph!)));
}

/** 임의 문자열 → 파이썬 식별자 (한글 등은 fallback) */
export function pyIdent(s: string, fallback = "sub_agent") {
  const v = s
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_");
  return !v || /^[0-9]/.test(v) ? fallback : v;
}

export function uniqueIn(base: string, taken: Iterable<string>) {
  const names = new Set(taken);
  if (!names.has(base)) return base;
  let i = 2;
  while (names.has(`${base}_${i}`)) i++;
  return `${base}_${i}`;
}

export function summarize(g?: SubGraph) {
  const real = (g?.nodes ?? []).filter((n) => n.kind !== "start" && n.kind !== "end");
  const tools = new Set(allNodes(g ?? { nodes: [], edges: [] }).flatMap((n) => (n.kind === "tools" || n.kind === "agent" ? n.data.tools ?? [] : [])));
  return { count: real.length, nested: real.filter((n) => n.kind === "subgraph").length, tools: [...tools], names: real.map((n) => n.data.name) };
}

/* ------------------------------------------------------------------ 묶기 / 펼치기 */

type Result = { ok: true; graph: SubGraph; nodeId: string } | { ok: false; error: string };

/**
 * 선택한 노드들을 하나의 Sub-agent 노드로 묶는다.
 * 바깥에서 들어오는 지점과 바깥으로 나가는 대상이 각각 하나여야 의미가 보존된다.
 */
export function groupNodes(level: SubGraph, ids: string[], name: string): Result {
  const byId = new Map(level.nodes.map((n) => [n.id, n]));
  const sel = new Set(ids.filter((id) => byId.has(id) && !["start", "end"].includes(byId.get(id)!.kind)));
  if (sel.size === 0) return { ok: false, error: "묶을 노드를 선택하세요 (START/END 제외)." };
  const incoming = level.edges.filter((e) => sel.has(e.target) && !sel.has(e.source));
  const outgoing = level.edges.filter((e) => sel.has(e.source) && !sel.has(e.target));
  const entries = [...new Set(incoming.map((e) => e.target))];
  const exits = [...new Set(outgoing.map((e) => e.target))];
  if (entries.length > 1)
    return { ok: false, error: `바깥에서 들어오는 지점이 ${entries.length}곳입니다 (${entries.map((id) => byId.get(id)!.data.name).join(", ")}). 하나의 입구만 있도록 선택을 조정하세요.` };
  if (exits.length > 1)
    return { ok: false, error: `바깥으로 나가는 대상이 ${exits.length}곳입니다. 서브그래프는 하나의 출구(END)로 끝나야 하므로 선택을 조정하세요.` };

  const subId = `subgraph-${rid()}`;
  const inner = level.nodes.filter((n) => sel.has(n.id));
  const cx = inner.reduce((a, n) => a + n.position.x, 0) / inner.length;
  const minY = Math.min(...inner.map((n) => n.position.y));
  const maxY = Math.max(...inner.map((n) => n.position.y));
  const exitNode = exits[0] ? byId.get(exits[0]) : undefined;

  // 입구가 없으면 안쪽에서 들어오는 엣지가 없는 노드들을 시작점으로 삼는다
  const starts = entries.length ? entries : inner.filter((n) => !level.edges.some((e) => e.target === n.id && sel.has(e.source))).map((n) => n.id);
  const child: SubGraph = {
    nodes: [
      { id: "start", kind: "start", data: { name: "__start__" }, position: { x: cx + 50, y: minY - 120 } },
      ...inner.map((n) => ({ ...n })),
      { id: "end", kind: "end", data: { name: "__end__" }, position: { x: cx + 50, y: maxY + 140 } },
    ],
    edges: [
      ...starts.map((t) => ({ id: `e-${rid()}`, source: "start", target: t })),
      ...level.edges.filter((e) => sel.has(e.source) && sel.has(e.target)),
      ...outgoing.map((e) => ({ id: `e-${rid()}`, source: e.source, target: "end", sourceHandle: e.sourceHandle ?? null })),
    ],
  };
  // 같은 핸들 → END 가 중복되지 않게
  const seen = new Set<string>();
  child.edges = child.edges.filter((e) => {
    const k = `${e.source}>${e.target}:${e.sourceHandle ?? ""}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  const parentIn = new Map<string, GEdge>();
  for (const e of incoming) parentIn.set(`${e.source}:${e.sourceHandle ?? ""}`, { id: `e-${rid()}`, source: e.source, target: subId, sourceHandle: e.sourceHandle ?? null });
  const node: GNode = {
    id: subId,
    kind: "subgraph",
    data: { name, description: `${inner.map((n) => n.data.name).join(", ")} 를 묶은 서브 에이전트`, io: "isolated", memory: "inherit", graph: child },
    position: { x: cx, y: (minY + maxY) / 2 },
  };
  return {
    ok: true,
    nodeId: subId,
    graph: {
      nodes: [...level.nodes.filter((n) => !sel.has(n.id)), node],
      edges: [
        ...level.edges.filter((e) => !sel.has(e.source) && !sel.has(e.target)),
        ...parentIn.values(),
        ...(exitNode ? [{ id: `e-${rid()}`, source: subId, target: exitNode.id }] : []),
      ],
    },
  };
}

/** Sub-agent 노드를 풀어 안쪽 노드들을 현재 그래프에 직접 배치한다. */
export function flattenNode(level: SubGraph, nodeId: string): Result {
  const sub = level.nodes.find((n) => n.id === nodeId);
  if (!sub || sub.kind !== "subgraph" || !sub.data.graph) return { ok: false, error: "Sub-agent 노드가 아닙니다." };
  const g = sub.data.graph;
  const startIds = new Set(g.nodes.filter((n) => n.kind === "start").map((n) => n.id));
  const endIds = new Set(g.nodes.filter((n) => n.kind === "end").map((n) => n.id));
  const real = g.nodes.filter((n) => !startIds.has(n.id) && !endIds.has(n.id));
  if (!real.length) return { ok: false, error: "안쪽 그래프가 비어 있습니다." };

  const taken = new Set(level.nodes.filter((n) => n.id !== nodeId).map((n) => n.data.name));
  const idMap = new Map<string, string>();
  const cx = real.reduce((a, n) => a + n.position.x, 0) / real.length;
  const cy = real.reduce((a, n) => a + n.position.y, 0) / real.length;
  const moved: GNode[] = real.map((n) => {
    const id = `${n.id}-${rid()}`;
    idMap.set(n.id, id);
    const name = uniqueIn(n.data.name, taken);
    taken.add(name);
    return { ...n, id, data: { ...n.data, name }, position: { x: sub.position.x + n.position.x - cx, y: sub.position.y + n.position.y - cy } };
  });

  const parentIn = level.edges.filter((e) => e.target === nodeId);
  const parentOut = level.edges.filter((e) => e.source === nodeId);
  const edges: GEdge[] = level.edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
  const add = (source: string, target: string, sourceHandle?: string | null) => edges.push({ id: `e-${rid()}`, source, target, sourceHandle: sourceHandle ?? null });
  for (const e of g.edges) {
    const fromStart = startIds.has(e.source);
    const toEnd = endIds.has(e.target);
    if (fromStart && toEnd) for (const pi of parentIn) for (const po of parentOut) add(pi.source, po.target, pi.sourceHandle);
    else if (fromStart) for (const pi of parentIn) add(pi.source, idMap.get(e.target)!, pi.sourceHandle);
    else if (toEnd) for (const po of parentOut) add(idMap.get(e.source)!, po.target, e.sourceHandle);
    else if (idMap.has(e.source) && idMap.has(e.target)) add(idMap.get(e.source)!, idMap.get(e.target)!, e.sourceHandle);
  }
  return { ok: true, nodeId: moved[0].id, graph: { nodes: [...level.nodes.filter((n) => n.id !== nodeId), ...moved], edges } };
}
