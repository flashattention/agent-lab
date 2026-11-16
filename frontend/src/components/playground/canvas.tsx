"use client";

import type { Ref } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, useReactFlow, type Edge } from "@xyflow/react";
import { useTheme } from "next-themes";
import { Boxes, ChevronRight, CornerLeftUp, Home, OctagonAlert } from "lucide-react";
import { KINDS } from "@/lib/playground/catalog";
import type { NodeKind } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import { AgentNode } from "./agent-node";
import { usePlayground, type FlowNode } from "./store";
import { usePlaygroundUI } from "./ui-store";

const nodeTypes = { agent: AgentNode };

/** React Flow 캔버스: 노드 끌어다 놓기, 연결, 선택, 구조 오류 표시. */
export function Canvas({
  ref,
  nodes,
  edges,
  hidden,
  errorCount,
  onShowProblems,
  onDropKind,
  onDropPreset,
}: {
  ref: Ref<HTMLDivElement>;
  nodes: FlowNode[];
  edges: Edge[];
  hidden: boolean;
  errorCount: number;
  onShowProblems: () => void;
  onDropKind: (kind: NodeKind, pos: { x: number; y: number }) => void;
  onDropPreset: (presetId: string, pos: { x: number; y: number }) => void;
}) {
  const { onNodesChange, onEdgesChange, onConnect, select, enter } = usePlayground();
  const { resolvedTheme } = useTheme();
  const rf = useReactFlow();

  return (
    <div
      ref={ref}
      className={cn("absolute inset-0 transition-[box-shadow]", hidden && "invisible", errorCount > 0 && "shadow-[inset_0_0_0_2px_var(--danger)]")}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
      }}
      onDrop={(e) => {
        e.preventDefault();
        const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
        const presetId = e.dataTransfer.getData("application/agentlab-preset");
        if (presetId) return onDropPreset(presetId, { x: p.x - 120, y: p.y - 30 });
        const kind = e.dataTransfer.getData("application/agentlab-node") as NodeKind;
        if (!kind || !KINDS[kind]) return;
        onDropKind(kind, { x: p.x - 110, y: p.y - 30 });
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => select(n.id)}
        onNodeDoubleClick={(_, n) => {
          if (n.data.kind === "subgraph") enter(n.id);
          else if (n.data.kind === "agent") usePlaygroundUI.getState().setAgentDialog(n.id);
        }}
        zoomOnDoubleClick={false}
        onPaneClick={() => select(null)}
        colorMode={resolvedTheme === "dark" ? "dark" : "light"}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode={["Backspace", "Delete"]}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="var(--grid)" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => KINDS[(n.data as { kind: NodeKind }).kind]?.color ?? "#888"} maskColor="color-mix(in srgb, var(--bg) 70%, transparent)" />
      </ReactFlow>
      <Breadcrumb />
      {errorCount > 0 && (
        <button
          onClick={onShowProblems}
          className="fade-in absolute top-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border border-danger/40 bg-surface px-4 py-1.5 text-xs font-medium text-danger shadow-soft"
        >
          <OctagonAlert className="h-4 w-4" /> 실행 전 구조 오류 {errorCount}개 — 빨간 노드/엣지를 확인하세요
        </button>
      )}
      {nodes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <div className="text-center text-sm text-muted">
            오른쪽 컴포넌트를 끌어다 놓거나
            <br />
            <b className="text-accent">패턴 예시</b>를 불러오세요.
          </div>
        </div>
      )}
    </div>
  );
}

/** 캔버스 왼쪽 위: 지금 보고 있는 그래프의 위치 (agent › researcher › ...) */
function Breadcrumb() {
  const stack = usePlayground((s) => s.stack);
  const exitTo = usePlayground((s) => s.exitTo);
  const top = stack[stack.length - 1];
  const owner = top?.nodes.find((n) => n.id === top.nodeId);
  return (
    <div className="absolute top-3 left-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-col gap-1.5">
      <div className={cn("flex items-center gap-0.5 overflow-x-auto rounded-xl border bg-surface/95 px-1 py-1 text-xs shadow-soft backdrop-blur", stack.length ? "border-accent/40" : "border-border")}>
        <button onClick={() => exitTo(0)} className={cn("flex shrink-0 items-center gap-1 rounded-lg px-2 py-1", stack.length ? "text-muted hover:bg-surface-2 hover:text-fg" : "font-semibold text-fg")}>
          <Home className="h-3.5 w-3.5" /> agent
        </button>
        {stack.map((f, i) => (
          <span key={f.nodeId} className="flex shrink-0 items-center">
            <ChevronRight className="h-3 w-3 text-muted" />
            <button
              onClick={() => exitTo(i + 1)}
              disabled={i === stack.length - 1}
              className={cn("flex items-center gap-1 rounded-lg px-2 py-1 font-mono", i === stack.length - 1 ? "font-semibold text-accent" : "text-muted hover:bg-surface-2 hover:text-fg")}
            >
              <Boxes className="h-3.5 w-3.5" /> {f.name}
            </button>
          </span>
        ))}
        {stack.length > 0 && (
          <button onClick={() => exitTo(stack.length - 1)} className="ml-1 flex shrink-0 items-center gap-1 rounded-lg border-l border-border px-2 py-1 text-muted hover:text-fg" title="상위 그래프로 (Esc)">
            <CornerLeftUp className="h-3.5 w-3.5" /> 위로
          </button>
        )}
      </div>
      {owner && (
        <div className="w-fit max-w-sm rounded-lg bg-accent-soft px-2.5 py-1 text-[11px] text-accent">
          Sub-agent <b className="font-mono">{owner.data.name}</b> 내부 · {owner.data.io === "shared" ? "상태 공유" : "격리"} 모드 · 그래프 설정(체크포인터 등)은 최상위를 따릅니다
        </div>
      )}
    </div>
  );
}
