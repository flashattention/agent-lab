"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertTriangle, CircleCheck, CircleX, Link2, Loader2, Maximize2, OctagonAlert, Pause } from "lucide-react";
import { KINDS, toolCatalog } from "@/lib/playground/catalog";
import { summarize } from "@/lib/playground/subgraph";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import { usePlayground, type FlowNode } from "./store";

export type NodeStatus = "ok" | "warn" | "error";
export type NodeRun = { status: "running" | "ok" | "error" | "interrupted" | "aborted"; runs: number };

/** 실행 트레이스 기준 노드 상태 배지 (실행 중 / 완료 횟수 / 오류). */
function RunBadge({ run }: { run?: NodeRun }) {
  if (!run) return null;
  const cls = "absolute -top-2.5 -right-2 z-10 flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold shadow-soft";
  if (run.status === "running")
    return (
      <span className={cn(cls, "border-accent bg-accent text-accent-fg")}>
        <Loader2 className="h-3 w-3 animate-spin" /> 실행 중
      </span>
    );
  const I = run.status === "error" ? CircleX : run.status === "interrupted" ? Pause : CircleCheck;
  return (
    <span className={cn(cls, "bg-surface", run.status === "error" ? "border-danger text-danger" : run.status === "interrupted" ? "border-warning text-warning" : "border-success/50 text-success")}>
      <I className="h-3 w-3" /> {run.runs > 1 ? `×${run.runs}` : ""}
    </span>
  );
}

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

export const AgentNode = memo(function AgentNode({ id, data, selected }: NodeProps<FlowNode>) {
  const info = KINDS[data.kind];
  const catalog = toolCatalog(usePlayground((s) => s.settings));
  const status = (data as FlowNode["data"] & { __status?: NodeStatus }).__status ?? "ok";
  const run = (data as FlowNode["data"] & { __run?: NodeRun }).__run;
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

  if (data.kind === "subgraph") return <SubgraphNode id={id} data={data} selected={!!selected} status={status} />;

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
            : data.model
              ? data.model
              : null;
  const tools = data.kind === "tools" || data.kind === "agent" ? data.tools ?? [] : [];

  return (
    <div
      className={cn(
        "relative w-[220px] rounded-2xl border bg-surface shadow-soft transition-[box-shadow,border-color]",
        run?.status === "running" && "ring-4 ring-accent/40 !border-accent",
        isRouting ? "border-dashed border-2" : "border-border",
        selected && "ring-2 ring-accent/50",
        status === "error" && "pulse-danger !border-danger !border-2 bg-danger-soft",
        status === "warn" && "!border-warning !border-2",
      )}
      style={isRouting && status === "ok" ? { borderColor: color } : undefined}
    >
      <Handle type="target" position={Position.Top} className={handleCls} />
      <RunBadge run={run} />
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
                    catalog[t]?.sensitive ? "bg-danger/10 text-danger" : "bg-surface-2 text-fg-2",
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

/** Sub-agent: 카드가 겹쳐 쌓인 모양으로 "안에 그래프가 있다"는 것을 보여 준다. */
function SubgraphNode({ id, data, selected, status }: { id: string; data: FlowNode["data"]; selected: boolean; status: NodeStatus }) {
  const info = KINDS.subgraph;
  const sum = summarize(data.graph);
  const catalog = toolCatalog(usePlayground((s) => s.settings));
  const color = info.color;
  return (
    <div className="relative w-[240px]">
      {/* 뒤에 겹친 카드 */}
      <div className="absolute inset-0 translate-x-2 translate-y-2 rounded-2xl border border-border bg-surface-2" />
      <div className="absolute inset-0 translate-x-1 translate-y-1 rounded-2xl border border-border bg-surface" />
      <div
        className={cn(
          "relative rounded-2xl border-2 bg-surface shadow-soft transition-[box-shadow,border-color]",
          selected && "ring-2 ring-accent/50",
          status === "error" && "pulse-danger !border-danger bg-danger-soft",
          status === "warn" && "!border-warning",
        )}
        style={status === "ok" ? { borderColor: color } : undefined}
      >
        <Handle type="target" position={Position.Top} className={handleCls} />
        <div className="flex items-center gap-2.5 px-3 pt-2.5 pb-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl text-white" style={{ background: color }}>
            <Icon name={info.icon} className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1 truncate text-[10px] font-semibold tracking-wide uppercase" style={{ color }}>
              Sub-agent
              <span className="rounded bg-surface-2 px-1 py-px text-[9px] font-medium tracking-normal text-muted normal-case">{data.io === "shared" ? "상태 공유" : "격리"}</span>
              {data.memory === "persistent" && <span className="rounded bg-surface-2 px-1 py-px text-[9px] font-medium tracking-normal text-muted normal-case">메모리</span>}
            </div>
            <div className="truncate font-mono text-[13px] font-semibold text-fg">{data.name}</div>
          </div>
          {status === "error" && <OctagonAlert className="h-4 w-4 shrink-0 text-danger" />}
          {status === "warn" && <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />}
        </div>
        <div className="border-t border-border px-3 py-2">
          {data.description && <div className="mb-1 line-clamp-2 text-[11px] leading-snug text-muted">{data.description}</div>}
          <div className="flex flex-wrap items-center gap-1">
            <span className="font-mono text-[10.5px] text-fg-2">
              노드 {sum.count}
              {sum.nested ? ` · 서브 ${sum.nested}` : ""}
            </span>
            {sum.tools.slice(0, 2).map((t) => (
              <span key={t} className={cn("rounded-md px-1.5 py-0.5 font-mono text-[10px]", catalog[t]?.sensitive ? "bg-danger/10 text-danger" : "bg-surface-2 text-fg-2")}>
                {t}
              </span>
            ))}
            {sum.tools.length > 2 && <span className="text-[10px] text-muted">+{sum.tools.length - 2}</span>}
          </div>
          <div className="mt-1.5 flex items-center gap-1">
            {data.preset && (
              <span className="flex min-w-0 items-center gap-1 truncate text-[10px] text-muted" title={`프리셋: ${data.preset.name}`}>
                <Link2 className="h-3 w-3 shrink-0" /> <span className="truncate">{data.preset.name}</span>
              </span>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                usePlayground.getState().enter(id);
              }}
              className="nodrag ml-auto flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold hover:bg-surface-2"
              style={{ color }}
              title="내부 그래프 열기 (더블클릭)"
            >
              <Maximize2 className="h-3 w-3" /> 열기
            </button>
          </div>
        </div>
        <Handle type="source" position={Position.Bottom} className={handleCls} style={{ borderColor: color }} />
      </div>
    </div>
  );
}
