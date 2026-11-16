"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type Edge, type EdgeChange, type Node, type NodeChange } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import type { Graph, GraphSettings, NodeData, NodeKind, SubGraph } from "@/lib/playground/types";
import { DEFAULT_SETTINGS } from "@/lib/playground/types";
import { defaultData, KINDS } from "@/lib/playground/catalog";
import { allNodes, cloneSub, flattenNode, groupNodes, needsLayout, uniqueIn } from "@/lib/playground/subgraph";

export type FlowData = NodeData & { kind: NodeKind };
export type FlowNode = Node<FlowData, "agent">;

export const CANVAS_TAB = "__canvas__";

/**
 * 서브그래프 안으로 들어갈 때 쌓이는 부모 레벨.
 * 화면(nodes/edges)은 항상 "지금 보고 있는 레벨"이고, 부모 레벨들은 들어가는 순간의 모습으로 여기에 보관된다.
 * 저장/코드 생성 때는 composeRoot 로 현재 레벨을 부모 노드의 data.graph 에 다시 끼워 넣어 전체 트리를 만든다.
 */
export type Frame = { nodeId: string; name: string; nodes: FlowNode[]; edges: Edge[] };

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
  // 프로젝트 (로그인 후 서버에 저장되는 작업). projectId 가 없으면 이 브라우저에만 있는 임시 캔버스다.
  projectId: string | null;
  projectName: string;
  owned: boolean; // 내 프로젝트인지. 공유받은 프로젝트는 false (수정해도 저장되지 않음)
  isPublic: boolean;
  // 서브그래프 탐색 (빈 배열 = 최상위)
  stack: Frame[];
  // 실행 취소
  past: Snapshot[];
  future: Snapshot[];

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
  openProject: (p: { id: string; name: string; graph: Graph; overrides: Record<string, string>; pattern_id: string | null; is_public: boolean }, owned: boolean) => void;
  attachProject: (p: { id: string; name: string; is_public: boolean }) => void;
  leaveProject: () => void;
  setProjectName: (name: string) => void;
  setIsPublic: (v: boolean) => void;
  undo: () => void;
  redo: () => void;
  // 서브그래프
  enter: (nodeId: string) => boolean;
  exitTo: (depth: number) => void;
  navigate: (path: string[]) => void;
  addSubgraph: (sub: SubGraph, data: Partial<NodeData>, position: { x: number; y: number }) => string;
  replaceSubgraph: (nodeId: string, sub: SubGraph, patch?: Partial<NodeData>) => void;
  groupSelected: (name: string) => string | null; // 오류 메시지 또는 null
  ungroup: (nodeId: string) => string | null;
  // 복사 · 붙여넣기 (브라우저 저장소를 클립보드로 써서 서브그래프·프로젝트 사이에서도 동작)
  copySelection: () => number;
  paste: () => number;
  duplicate: () => number;
  importGraph: (g: Graph) => void;
};

const CLIPBOARD_KEY = "agentlab-clipboard";
type Clip = { nodes: SubGraph["nodes"]; edges: SubGraph["edges"]; tools?: SubGraph["tools"]; at: number };

type Snapshot = { nodes: FlowNode[]; edges: Edge[]; settings: GraphSettings; stack: Frame[] };

const HISTORY_LIMIT = 60;
const SCRATCH_KEY = "agentlab-scratch";
let lastEditAt = 0; // 속성 입력처럼 연속된 수정은 한 단계로 묶는다
let dragging = false;

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
  for (const n of nodes) g.setNode(n.id, { width: n.data.kind === "start" || n.data.kind === "end" ? 120 : n.data.kind === "subgraph" ? 250 : 220, height: n.data.kind === "router" || n.data.kind === "map" ? 70 : 84 });
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
    const w = n.data.kind === "start" || n.data.kind === "end" ? 120 : n.data.kind === "subgraph" ? 250 : 220;
    return p ? { ...n, position: { x: p.x - w / 2, y: p.y - 40 } } : n;
  });
}

export function toSub(nodes: FlowNode[], edges: Edge[]): SubGraph {
  return {
    nodes: nodes.map((n) => {
      const { kind, ...data } = n.data;
      delete (data as { __status?: unknown }).__status;
      return { id: n.id, kind, data, position: n.position };
    }),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null })),
  };
}

/** 현재 레벨을 부모 프레임들에 차례로 끼워 넣어 최상위 노드/엣지를 만든다. */
export function composeRoot(nodes: FlowNode[], edges: Edge[], stack: Frame[]): { nodes: FlowNode[]; edges: Edge[] } {
  let n = nodes;
  let e = edges;
  for (let i = stack.length - 1; i >= 0; i--) {
    const f = stack[i];
    const graph = toSub(n, e);
    n = f.nodes.map((x) => (x.id === f.nodeId ? { ...x, data: { ...x.data, graph } } : x));
    e = f.edges;
  }
  return { nodes: n, edges: e };
}

/** 저장·코드 생성용 전체 그래프. stack 이 있으면 서브그래프 안에서 편집 중인 내용까지 합친다. */
export function toGraph(s: Pick<PlaygroundState, "nodes" | "edges" | "settings"> & { stack?: Frame[] }): Graph {
  const root = s.stack?.length ? composeRoot(s.nodes, s.edges, s.stack) : s;
  return { ...toSub(root.nodes, root.edges), settings: s.settings };
}

export const currentPath = (stack: Frame[]) => stack.map((f) => f.nodeId);

/** 좌표가 없는 그래프(패턴 예시)를 위→아래로 배치해 돌려준다. */
export function arranged(g: Graph): Graph {
  const { nodes, edges } = fromGraph(g);
  return toGraph({ nodes: layout(nodes, edges), edges, settings: g.settings });
}

function fromGraph(g: SubGraph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = g.nodes.map((n) => ({ id: n.id, type: "agent", position: n.position, data: { ...n.data, kind: n.kind } }));
  const edges: Edge[] = g.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? undefined }));
  return { nodes, edges };
}

/** 좌표가 없는 서브그래프(프리셋/패턴)는 배치해서 돌려준다. */
export function arrangedSub(g: SubGraph): SubGraph {
  const { nodes, edges } = fromGraph(g);
  return needsLayout(nodes) ? toSub(layout(nodes, edges), edges) : g;
}

export const usePlayground = create<PlaygroundState>()(
  persist(
    (set, get) => {
      /** 변경 직전 상태를 실행 취소 기록에 남긴다. */
      const remember = () => {
        const { nodes, edges, settings, stack, past } = get();
        set({ past: [...past.slice(-(HISTORY_LIMIT - 1)), { nodes, edges, settings, stack }], future: [] });
      };
      const level = (): SubGraph => toSub(get().nodes, get().edges);
      const setLevel = (g: SubGraph, selectedId: string | null = null) => {
        const { nodes, edges } = fromGraph(g);
        set({ nodes, edges, selectedId });
      };
      return {
      nodes: [],
      edges: [],
      settings: DEFAULT_SETTINGS,
      selectedId: null,
      overrides: {},
      refined: null,
      // 공유 캐시에서 온 고도화 코드는 자동 적용하지 않는다 (사용자가 직접 켜야 함, 보안 S2)
      useRefined: false,
      tabs: [CANVAS_TAB],
      activeTab: CANVAS_TAB,
      patternId: null,
      projectId: null,
      projectName: "제목 없는 프로젝트",
      owned: false,
      isPublic: false,
      stack: [],
      past: [],
      future: [],

      onNodesChange: (changes) => {
        const dragStart = !dragging && changes.some((c) => c.type === "position" && c.dragging);
        if (changes.some((c) => c.type === "position")) dragging = changes.some((c) => c.type === "position" && c.dragging);
        if (dragStart || changes.some((c) => c.type === "remove")) remember();
        set({ nodes: applyNodeChanges(changes, get().nodes) });
      },
      onEdgesChange: (changes) => {
        if (changes.some((c) => c.type === "remove")) remember();
        set({ edges: applyEdgeChanges(changes, get().edges) });
      },
      onConnect: (c) => {
        if (!c.source || !c.target) return;
        const { nodes, edges } = get();
        const src = nodes.find((n) => n.id === c.source);
        // evaluator/human 은 핸들별 경로를 하나씩만 갖는다 → 같은 핸들의 기존 엣지를 교체
        let next = edges;
        if (src && (src.data.kind === "evaluator" || src.data.kind === "human") && c.sourceHandle)
          next = edges.filter((e) => !(e.source === c.source && e.sourceHandle === c.sourceHandle));
        remember();
        set({ edges: addEdge({ ...c, id: `e-${uid()}` }, next) });
      },
      addNode: (kind, position) => {
        const { nodes } = get();
        if (KINDS[kind].unique && nodes.some((n) => n.data.kind === kind)) return;
        const data = defaultData(kind);
        const id = kind === "start" || kind === "end" ? kind : `${kind}-${uid()}`;
        if (kind !== "start" && kind !== "end") data.name = uniqueName(data.name, nodes);
        const node: FlowNode = { id, type: "agent", position, data: { ...data, kind } };
        remember();
        set({ nodes: [...nodes, node], selectedId: id });
      },
      updateNode: (id, patch) => {
        if (Date.now() - lastEditAt > 1000) remember();
        lastEditAt = Date.now();
        set({ nodes: get().nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)) });
      },
      removeNode: (id) => {
        remember();
        set({
          nodes: get().nodes.filter((n) => n.id !== id),
          edges: get().edges.filter((e) => e.source !== id && e.target !== id),
          selectedId: get().selectedId === id ? null : get().selectedId,
        });
      },
      setSettings: (patch) => {
        if (Date.now() - lastEditAt > 1000) remember();
        lastEditAt = Date.now();
        set({ settings: { ...get().settings, ...patch } });
      },
      select: (id) => set({ selectedId: id }),
      loadGraph: (g, patternId = null) => {
        const { nodes, edges } = fromGraph(g);
        remember();
        set({
          nodes: layout(nodes, edges),
          edges,
          settings: g.settings,
          selectedId: null,
          overrides: {},
          refined: null,
          patternId,
          stack: [],
          tabs: [CANVAS_TAB],
          activeTab: CANVAS_TAB,
        });
      },
      clear: () => {
        remember();
        if (get().stack.length) set({ nodes: [], edges: [], selectedId: null });
        else set({ nodes: [], edges: [], selectedId: null, overrides: {}, refined: null, patternId: null, tabs: [CANVAS_TAB], activeTab: CANVAS_TAB });
      },
      autoLayout: () => {
        remember();
        set({ nodes: layout(get().nodes, get().edges) });
      },
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

      openProject: (p, owned) => {
        const cur = get();
        // 저장되지 않은 임시 캔버스는 따로 보관해 두었다가 프로젝트에서 나올 때 되돌린다
        if (!cur.projectId && cur.nodes.length) {
          try {
            localStorage.setItem(SCRATCH_KEY, JSON.stringify({ graph: toGraph(cur), overrides: cur.overrides, patternId: cur.patternId }));
          } catch {}
        }
        const { nodes, edges } = fromGraph(p.graph);
        set({
          nodes,
          edges,
          settings: { ...DEFAULT_SETTINGS, ...p.graph.settings },
          overrides: p.overrides ?? {},
          patternId: p.pattern_id,
          projectId: p.id,
          projectName: p.name,
          owned,
          isPublic: p.is_public,
          stack: [],
          selectedId: null,
          refined: null,
          tabs: [CANVAS_TAB],
          activeTab: CANVAS_TAB,
          past: [],
          future: [],
        });
      },
      attachProject: (p) => set({ projectId: p.id, projectName: p.name, owned: true, isPublic: p.is_public }),
      leaveProject: () => {
        let scratch: { graph: Graph; overrides: Record<string, string>; patternId: string | null } | null = null;
        try {
          scratch = JSON.parse(localStorage.getItem(SCRATCH_KEY) || "null");
          localStorage.removeItem(SCRATCH_KEY);
        } catch {}
        const base = { projectId: null, projectName: "제목 없는 프로젝트", owned: false, isPublic: false, stack: [], selectedId: null, refined: null, tabs: [CANVAS_TAB], activeTab: CANVAS_TAB, past: [], future: [] };
        if (scratch?.graph) {
          const { nodes, edges } = fromGraph(scratch.graph);
          set({ ...base, nodes, edges, settings: scratch.graph.settings, overrides: scratch.overrides ?? {}, patternId: scratch.patternId });
        } else set({ ...base, nodes: [], edges: [], settings: DEFAULT_SETTINGS, overrides: {}, patternId: null });
      },
      setProjectName: (projectName) => set({ projectName }),
      setIsPublic: (isPublic) => set({ isPublic }),

      undo: () => {
        const { past, future, nodes, edges, settings, stack } = get();
        const prev = past[past.length - 1];
        if (!prev) return;
        set({ ...prev, past: past.slice(0, -1), future: [{ nodes, edges, settings, stack }, ...future].slice(0, HISTORY_LIMIT), selectedId: null });
      },
      redo: () => {
        const { past, future, nodes, edges, settings, stack } = get();
        const next = future[0];
        if (!next) return;
        set({ ...next, future: future.slice(1), past: [...past, { nodes, edges, settings, stack }].slice(-HISTORY_LIMIT), selectedId: null });
      },

      /* ---------------------------------------------------------- 서브그래프 */
      enter: (nodeId) => {
        const { nodes, edges, stack } = get();
        const node = nodes.find((n) => n.id === nodeId);
        if (!node || node.data.kind !== "subgraph") return false;
        const child = fromGraph(node.data.graph ?? { nodes: [], edges: [] });
        set({
          stack: [...stack, { nodeId, name: node.data.name, nodes, edges }],
          nodes: needsLayout(child.nodes) ? layout(child.nodes, child.edges) : child.nodes,
          edges: child.edges,
          selectedId: null,
        });
        return true;
      },
      exitTo: (depth) => {
        const { nodes, edges, stack } = get();
        if (depth >= stack.length) return;
        const keep = stack.slice(0, depth);
        const root = composeRoot(nodes, edges, stack.slice(depth));
        set({ stack: keep, nodes: root.nodes, edges: root.edges, selectedId: stack[depth].nodeId });
      },
      navigate: (path) => {
        const st = get();
        const cur = currentPath(st.stack);
        let common = 0;
        while (common < cur.length && common < path.length && cur[common] === path[common]) common++;
        if (common < cur.length) st.exitTo(common);
        for (const id of path.slice(common)) if (!get().enter(id)) break;
      },
      addSubgraph: (sub, data, position) => {
        const { nodes, settings } = get();
        // 프리셋이 가져온 커스텀 도구를 그래프 설정에 합친다 (같은 이름이 이미 있으면 기존 것을 유지)
        const have = new Set((settings.customTools ?? []).map((t) => t.name));
        const incoming = (sub.tools ?? []).filter((t) => !have.has(t.name));
        if (incoming.length) set({ settings: { ...settings, customTools: [...(settings.customTools ?? []), ...incoming] } });
        const id = `subgraph-${uid()}`;
        const base = defaultData("subgraph");
        const name = uniqueName(data.name || base.name, nodes);
        const node: FlowNode = { id, type: "agent", position, data: { ...base, ...data, name, graph: arrangedSub(cloneSub(sub)), kind: "subgraph" } };
        remember();
        set({ nodes: [...nodes, node], selectedId: id });
        return id;
      },
      replaceSubgraph: (nodeId, sub, patch = {}) => {
        remember();
        set({ nodes: get().nodes.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch, graph: arrangedSub(cloneSub(sub)) } } : n)) });
      },
      groupSelected: (name) => {
        const ids = get().nodes.filter((n) => n.selected).map((n) => n.id);
        const taken = get().nodes.map((n) => n.data.name);
        const r = groupNodes(level(), ids, uniqueIn(name, taken));
        if (!r.ok) return r.error;
        remember();
        setLevel(r.graph, r.nodeId);
        return null;
      },
      copySelection: () => {
        const { nodes, edges, settings, selectedId } = get();
        const picked = nodes.filter((n) => (n.selected || n.id === selectedId) && n.data.kind !== "start" && n.data.kind !== "end");
        if (!picked.length) return 0;
        const ids = new Set(picked.map((n) => n.id));
        const sub = toSub(picked, edges.filter((e) => ids.has(e.source) && ids.has(e.target)));
        const used = new Set(picked.flatMap((n) => [...(n.data.tools ?? []), ...(n.data.graph ? allNodes(n.data.graph).flatMap((x) => x.data.tools ?? []) : [])]));
        const clip: Clip = { ...sub, tools: (settings.customTools ?? []).filter((t) => used.has(t.name)), at: Date.now() };
        try {
          localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(clip));
        } catch {}
        return picked.length;
      },
      paste: () => {
        let clip: Clip | null = null;
        try {
          clip = JSON.parse(localStorage.getItem(CLIPBOARD_KEY) || "null");
        } catch {}
        if (!clip?.nodes?.length) return 0;
        const { nodes, edges, settings } = get();
        const taken = nodes.map((n) => n.data.name);
        const idMap = new Map<string, string>();
        const pasted: FlowNode[] = clip.nodes.map((n) => {
          const id = `${n.kind}-${uid()}`;
          idMap.set(n.id, id);
          const name = uniqueIn(n.data.name, taken);
          taken.push(name);
          return { id, type: "agent", position: { x: n.position.x + 40, y: n.position.y + 40 }, selected: true, data: { ...n.data, name, kind: n.kind } };
        });
        const newEdges: Edge[] = clip.edges.map((e) => ({ id: `e-${uid()}`, source: idMap.get(e.source)!, target: idMap.get(e.target)!, sourceHandle: e.sourceHandle ?? undefined }));
        const have = new Set((settings.customTools ?? []).map((t) => t.name));
        const tools = (clip.tools ?? []).filter((t) => !have.has(t.name));
        remember();
        set({
          nodes: [...nodes.map((n) => (n.selected ? { ...n, selected: false } : n)), ...pasted],
          edges: [...edges, ...newEdges],
          selectedId: pasted.length === 1 ? pasted[0].id : null,
          ...(tools.length ? { settings: { ...settings, customTools: [...(settings.customTools ?? []), ...tools] } } : {}),
        });
        // 다음 붙여넣기는 조금 더 비켜서 놓는다
        try {
          localStorage.setItem(CLIPBOARD_KEY, JSON.stringify({ ...clip, nodes: clip.nodes.map((n) => ({ ...n, position: { x: n.position.x + 40, y: n.position.y + 40 } })) }));
        } catch {}
        return pasted.length;
      },
      duplicate: () => (get().copySelection() ? get().paste() : 0),
      importGraph: (g) => {
        const { nodes, edges } = fromGraph(g);
        remember();
        set({
          nodes: needsLayout(nodes) ? layout(nodes, edges) : nodes,
          edges,
          settings: { ...DEFAULT_SETTINGS, ...g.settings },
          stack: [],
          selectedId: null,
          overrides: {},
          refined: null,
          patternId: null,
          tabs: [CANVAS_TAB],
          activeTab: CANVAS_TAB,
        });
      },
      ungroup: (nodeId) => {
        const r = flattenNode(level(), nodeId);
        if (!r.ok) return r.error;
        remember();
        setLevel(r.graph);
        return null;
      },
      };
    },
    {
      name: "agentlab-playground",
      partialize: (s) => ({
        nodes: s.nodes,
        edges: s.edges,
        settings: s.settings,
        overrides: s.overrides,
        patternId: s.patternId,
        projectId: s.projectId,
        projectName: s.projectName,
        owned: s.owned,
        isPublic: s.isPublic,
        stack: s.stack,
      }),
    },
  ),
);
