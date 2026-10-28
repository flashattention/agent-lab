"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertTriangle, OctagonAlert } from "lucide-react";
import { KINDS, TOOL_LIBRARY } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import type { FlowNode } from "./store";

export type NodeStatus = "ok" | "warn" | "error";

const handleCls = "!h-2.5 !w-2.5 !border-2 !bg-surface";

function SourceHandle({ id, label, left, color }: { id: string; label: string; left: string; color: string }) {
  return (
    <>
      <Handle type="source" id={id} position={Position.Bottom} style={{ left, borderColor: color }} className={handleCls} />
      <span className="pointer-events-none absolute -bottom-5 -translate-x-1/2 text-[10px] font-semibold" style={{ left, color }}>
        {label}
      </span>
    </>
  );
}

export const AgentNode = memo(function AgentNode({ data, selected }: NodeProps<FlowNode>) {
  const info = KINDS[data.kind];
  const status = (data as FlowNode["data"] & { __status?: NodeStatus }).__status ?? "ok";
  const color = info.color;

  if (data.kind === "start" || data.kind === "end") {
    return (
      <div
        className={cn(
          "flex w-[120px] items-center justify-center gap-1.5 rounded-full border-2 bg-surface py-2 text-xs font-bold tracking-wide shadow-soft transition",
          selected && "ring-2 ring-accent/40",
          status === "error" && "pulse-danger border-danger",
        )}
        style={{ borderColor: status === "error" ? undefined : color, color }}
      >
        {data.kind === "end" && <Handle type="target" position={Position.Top} className={handleCls} />}
        <Icon name={info.icon} className="h-3.5 w-3.5" />
        {data.kind.toUpperCase()}
        {data.kind === "start" && <Handle type="source" position={Position.Bottom} className={handleCls} />}
      </div>
    );
  }

  const isRouting = data.kind === "router" || data.kind === "map";
  const detail =
    data.kind === "router"
      ? { llm: "LLM 구조화 출력", tools_condition: "tools_condition", state_key: `state["${data.stateKey ?? ""}"]` }[data.strategy ?? "llm"]
      : data.kind === "map"
        ? `Send × 최대 ${data.maxItems ?? 4}`
        : data.kind === "evaluator" || data.kind === "supervisor"
          ? `최대 ${data.maxIterations ?? 3}회`
          : data.kind === "retriever"
            ? `top-k = ${data.k ?? 3}`
            : null;
  const tools = data.kind === "tools" || data.kind === "agent" ? data.tools ?? [] : [];

  return (
    <div
      className={cn(
        "relative w-[220px] rounded-2xl border bg-surface shadow-soft transition-[box-shadow,border-color]",
        isRouting ? "border-dashed border-2" : "border-border",
        selected && "ring-2 ring-accent/50",
        status === "error" && "pulse-danger !border-danger !border-2 bg-danger-soft",
        status === "warn" && "!border-warning !border-2",
      )}
      style={isRouting && status === "ok" ? { borderColor: color } : undefined}
    >
      <Handle type="target" position={Position.Top} className={handleCls} />
      <div className="flex items-center gap-2.5 px-3 pt-2.5 pb-2">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl text-white" style={{ background: color }}>
          <Icon name={info.icon} className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[10px] font-semibold tracking-wide uppercase" style={{ color }}>
            {info.label}
          </div>
          <div className="truncate font-mono text-[13px] font-semibold text-fg">{data.name}</div>
        </div>
        {status === "error" && <OctagonAlert className="h-4 w-4 shrink-0 text-danger" />}
        {status === "warn" && <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />}
      </div>
      {(detail || tools.length > 0 || data.prompt) && (
        <div className="border-t border-border px-3 py-2">
          {detail && <div className="font-mono text-[10.5px] text-muted">{detail}</div>}
          {tools.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {tools.slice(0, 4).map((t) => (
                <span
                  key={t}
                  className={cn(
                    "rounded-md px-1.5 py-0.5 font-mono text-[10px]",
                    TOOL_LIBRARY[t]?.sensitive ? "bg-danger/10 text-danger" : "bg-surface-2 text-fg-2",
                  )}
                >
                  {t}
                </span>
              ))}
              {tools.length > 4 && <span className="text-[10px] text-muted">+{tools.length - 4}</span>}
            </div>
          )}
          {!detail && !tools.length && data.prompt && <div className="line-clamp-2 text-[11px] leading-snug text-muted">{data.prompt}</div>}
        </div>
      )}

      {data.kind === "evaluator" ? (
        <>
          <SourceHandle id="pass" label="pass" left="30%" color="#10b981" />
          <SourceHandle id="retry" label="retry" left="70%" color="#e11d48" />
        </>
      ) : data.kind === "human" ? (
        <>
          <SourceHandle id="approve" label="승인" left="30%" color="#10b981" />
          <SourceHandle id="reject" label="거절" left="70%" color="#e11d48" />
        </>
      ) : (
        <Handle type="source" position={Position.Bottom} className={handleCls} style={{ borderColor: color }} />
      )}
    </div>
  );
});
