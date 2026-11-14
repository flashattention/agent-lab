"use client";

import type { Ref } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, useReactFlow, type Edge } from "@xyflow/react";
import { useTheme } from "next-themes";
import { OctagonAlert } from "lucide-react";
import { KINDS } from "@/lib/playground/catalog";
import type { NodeKind } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import { AgentNode } from "./agent-node";
import { usePlayground, type FlowNode } from "./store";

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
}: {
  ref: Ref<HTMLDivElement>;
  nodes: FlowNode[];
  edges: Edge[];
  hidden: boolean;
  errorCount: number;
  onShowProblems: () => void;
  onDropKind: (kind: NodeKind, pos: { x: number; y: number }) => void;
}) {
  const { onNodesChange, onEdgesChange, onConnect, select } = usePlayground();
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
        const kind = e.dataTransfer.getData("application/agentlab-node") as NodeKind;
        if (!kind || !KINDS[kind]) return;
        const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
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
