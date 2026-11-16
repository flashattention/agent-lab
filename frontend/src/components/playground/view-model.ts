// 캔버스에 그릴 노드·엣지: 저장된 그래프 + 구조 분석 결과 + 실행 상태를 합친다 (순수 함수).
import { MarkerType, type Edge } from "@xyflow/react";
import type { Highlight } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import type { NodeRun, NodeStatus } from "./agent-node";
import type { FlowNode } from "./store";

const CONDITIONAL = new Set(["router", "supervisor", "evaluator", "map"]);

export function toViewNodes(nodes: FlowNode[], analysis: Pick<Highlight, "errorNodes" | "warnNodes">, runStates: Map<string, NodeRun>) {
  const status = (id: string): NodeStatus => (analysis.errorNodes.has(id) ? "error" : analysis.warnNodes.has(id) ? "warn" : "ok");
  return nodes.map((n) => ({ ...n, data: { ...n.data, __status: status(n.id), __run: runStates.get(n.data.name) } }));
}

/** 엣지 라벨: 분기 이름(라우터), pass/retry(평가), 승인/거절(사람), Send(맵). */
export function edgeLabel(src: FlowNode | undefined, tgt: FlowNode | undefined, sourceHandle?: string | null): string | undefined {
  const kind = src?.data.kind;
  if (kind === "evaluator" || kind === "human") {
    if (sourceHandle === "reject") return "거절";
    if (sourceHandle === "approve") return "승인";
    return sourceHandle ?? undefined;
  }
  if (kind === "router" || kind === "supervisor") return tgt?.data.kind === "end" ? "END" : tgt?.data.name;
  if (kind === "map") return "Send(…)";
  return undefined;
}

export function toViewEdges(nodes: FlowNode[], edges: Edge[], analysis: Pick<Highlight, "errorEdges" | "warnEdges">): Edge[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return edges.map((e) => {
    const src = byId.get(e.source);
    const conditional = !!src && CONDITIONAL.has(src.data.kind);
    const err = analysis.errorEdges.has(e.id);
    const warn = analysis.warnEdges.has(e.id);
    return {
      ...e,
      type: "smoothstep",
      label: edgeLabel(src, byId.get(e.target), e.sourceHandle),
      animated: conditional || err,
      className: cn(err && "edge-error", !err && warn && "edge-warn", conditional && "edge-conditional"),
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: err ? "var(--danger)" : "var(--border-strong)" },
    };
  });
}
