"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type Edge, type EdgeChange, type Node, type NodeChange } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import type { Graph, GraphSettings, NodeData, NodeKind } from "@/lib/playground/types";
import { DEFAULT_SETTINGS } from "@/lib/playground/types";
import { defaultData, KINDS } from "@/lib/playground/catalog";

export type FlowData = NodeData & { kind: NodeKind };
export type FlowNode = Node<FlowData, "agent">;

export const CANVAS_TAB = "__canvas__";

type PlaygroundState = {
  nodes: FlowNode[];
  edges: Edge[];
  settings: GraphSettings;
  selectedId: string | null;
  // 코드
  overrides: Record<string, string>; // 사용자가 직접 수정한 파일
  refined: { key: string; files: Record<string, string>; notes: string; model?: string; cached: boolean } | null;
  useRefined: boolean;
  tabs: string[];
  activeTab: string;
  patternId: string | null;

  onNodesChange: (c: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (c: EdgeChange[]) => void;
  onConnect: (c: Connection) => void;
  addNode: (kind: NodeKind, position: { x: number; y: number }) => void;
  updateNode: (id: string, patch: Partial<NodeData>) => void;
  removeNode: (id: string) => void;
  setSettings: (patch: Partial<GraphSettings>) => void;
  select: (id: string | null) => void;
  loadGraph: (g: Graph, patternId?: string | null) => void;
  clear: () => void;
  autoLayout: () => void;
  setOverride: (path: string, content: string | null) => void;
  resetOverrides: () => void;
  setRefined: (r: PlaygroundState["refined"]) => void;
  setUseRefined: (v: boolean) => void;
  openTab: (path: string) => void;
  closeTab: (path: string) => void;
  setActiveTab: (path: string) => void;
};

const uid = () => Math.random().toString(36).slice(2, 9);

function uniqueName(base: string, nodes: FlowNode[]) {
  const names = new Set(nodes.map((n) => n.data.name));
  if (!names.has(base)) return base;
  let i = 2;
  while (names.has(`${base}_${i}`)) i++;
  return `${base}_${i}`;
}

export function layout(nodes: FlowNode[], edges: Edge[]): FlowNode[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 70, ranksep: 80, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: n.data.kind === "start" || n.data.kind === "end" ? 120 : 220, height: n.data.kind === "router" || n.data.kind === "map" ? 70 : 84 });
  // 역방향(루프) 엣지는 레이아웃 계산에서 제외해 위→아래 흐름을 유지한다
  const order = new Map<string, number>();
  const visit = (id: string, d: number) => {
    if (order.has(id)) return;
    order.set(id, d);
    edges.filter((e) => e.source === id).forEach((e) => visit(e.target, d + 1));
  };
  nodes.filter((n) => n.data.kind === "start").forEach((n) => visit(n.id, 0));
  for (const e of edges) {
    const back = (order.get(e.target) ?? 1e9) <= (order.get(e.source) ?? 0);
    if (!back || nodes.find((n) => n.id === e.target)?.data.kind === "end") g.setEdge(e.source, e.target);
  }
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    const w = n.data.kind === "start" || n.data.kind === "end" ? 120 : 220;
    return p ? { ...n, position: { x: p.x - w / 2, y: p.y - 40 } } : n;
  });
}

export function toGraph(s: Pick<PlaygroundState, "nodes" | "edges" | "settings">): Graph {
  return {
    nodes: s.nodes.map((n) => {
      const { kind, ...data } = n.data;
      return { id: n.id, kind, data, position: n.position };
    }),
    edges: s.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null })),
    settings: s.settings,
  };
}

function fromGraph(g: Graph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = g.nodes.map((n) => ({ id: n.id, type: "agent", position: n.position, data: { ...n.data, kind: n.kind } }));
  const edges: Edge[] = g.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? undefined }));
  return { nodes, edges };
}

export const usePlayground = create<PlaygroundState>()(
  persist(
    (set, get) => ({
      nodes: [],
      edges: [],
      settings: DEFAULT_SETTINGS,
      selectedId: null,
      overrides: {},
      refined: null,
      useRefined: true,
      tabs: [CANVAS_TAB],
      activeTab: CANVAS_TAB,
      patternId: null,

      onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
      onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),
      onConnect: (c) => {
        if (!c.source || !c.target) return;
        const { nodes, edges } = get();
        const src = nodes.find((n) => n.id === c.source);
        // evaluator/human 은 핸들별 경로를 하나씩만 갖는다 → 같은 핸들의 기존 엣지를 교체
        let next = edges;
        if (src && (src.data.kind === "evaluator" || src.data.kind === "human") && c.sourceHandle)
          next = edges.filter((e) => !(e.source === c.source && e.sourceHandle === c.sourceHandle));
        set({ edges: addEdge({ ...c, id: `e-${uid()}` }, next) });
      },
      addNode: (kind, position) => {
        const { nodes } = get();
        if (KINDS[kind].unique && nodes.some((n) => n.data.kind === kind)) return;
        const data = defaultData(kind);
        const id = kind === "start" || kind === "end" ? kind : `${kind}-${uid()}`;
        if (kind !== "start" && kind !== "end") data.name = uniqueName(data.name, nodes);
        const node: FlowNode = { id, type: "agent", position, data: { ...data, kind } };
        set({ nodes: [...nodes, node], selectedId: id });
      },
      updateNode: (id, patch) => set({ nodes: get().nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)) }),
      removeNode: (id) =>
        set({
          nodes: get().nodes.filter((n) => n.id !== id),
          edges: get().edges.filter((e) => e.source !== id && e.target !== id),
          selectedId: get().selectedId === id ? null : get().selectedId,
        }),
      setSettings: (patch) => set({ settings: { ...get().settings, ...patch } }),
      select: (id) => set({ selectedId: id }),
      loadGraph: (g, patternId = null) => {
        const { nodes, edges } = fromGraph(g);
        set({
          nodes: layout(nodes, edges),
          edges,
          settings: g.settings,
          selectedId: null,
          overrides: {},
          refined: null,
          patternId,
          tabs: [CANVAS_TAB],
          activeTab: CANVAS_TAB,
        });
      },
      clear: () =>
        set({ nodes: [], edges: [], selectedId: null, overrides: {}, refined: null, patternId: null, tabs: [CANVAS_TAB], activeTab: CANVAS_TAB }),
      autoLayout: () => set({ nodes: layout(get().nodes, get().edges) }),
      setOverride: (path, content) => {
        const o = { ...get().overrides };
        if (content === null) delete o[path];
        else o[path] = content;
        set({ overrides: o });
      },
      resetOverrides: () => set({ overrides: {} }),
      setRefined: (refined) => set({ refined }),
      setUseRefined: (useRefined) => set({ useRefined }),
      openTab: (path) => set({ tabs: get().tabs.includes(path) ? get().tabs : [...get().tabs, path], activeTab: path }),
      closeTab: (path) => {
        const tabs = get().tabs.filter((t) => t !== path);
        set({ tabs, activeTab: get().activeTab === path ? tabs[tabs.length - 1] ?? CANVAS_TAB : get().activeTab });
      },
      setActiveTab: (activeTab) => set({ activeTab }),
    }),
    {
      name: "agentlab-playground",
      partialize: (s) => ({ nodes: s.nodes, edges: s.edges, settings: s.settings, overrides: s.overrides, patternId: s.patternId }),
    },
  ),
);
