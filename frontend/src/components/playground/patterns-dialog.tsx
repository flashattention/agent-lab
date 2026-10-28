"use client";

import { useMemo, useState } from "react";
import { X } from "lucide-react";
import { PATTERNS, type Pattern } from "@/lib/playground/patterns";
import { KINDS } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";
import { layout, type FlowNode } from "./store";

function MiniGraph({ p }: { p: Pattern }) {
  const { nodes, edges, box } = useMemo(() => {
    const flow: FlowNode[] = p.graph.nodes.map((n) => ({ id: n.id, type: "agent", position: n.position, data: { ...n.data, kind: n.kind } }));
    const laid = layout(
      flow,
      p.graph.edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    );
    const xs = laid.map((n) => n.position.x + 110);
    const ys = laid.map((n) => n.position.y + 40);
    const box = { x: Math.min(...xs) - 130, y: Math.min(...ys) - 50, w: Math.max(...xs) - Math.min(...xs) + 260, h: Math.max(...ys) - Math.min(...ys) + 100 };
    return { nodes: laid, edges: p.graph.edges, box };
  }, [p]);
  const pos = (id: string) => {
    const n = nodes.find((x) => x.id === id)!;
    return { x: n.position.x + 110, y: n.position.y + 40 };
  };
  return (
    <svg viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} className="h-full w-full">
      {edges.map((e) => {
        const a = pos(e.source);
        const b = pos(e.target);
        const back = b.y <= a.y;
        return (
          <path
            key={e.id}
            d={back ? `M${a.x},${a.y} C${a.x + 160},${a.y} ${b.x + 160},${b.y} ${b.x},${b.y}` : `M${a.x},${a.y} L${b.x},${b.y}`}
            fill="none"
            stroke="var(--border-strong)"
            strokeWidth={5}
            strokeDasharray={back ? "14 10" : undefined}
          />
        );
      })}
      {nodes.map((n) => {
        const { x, y } = pos(n.id);
        const c = KINDS[n.data.kind].color;
        const small = n.data.kind === "start" || n.data.kind === "end";
        return <rect key={n.id} x={x - (small ? 50 : 90)} y={y - 24} width={small ? 100 : 180} height={48} rx={24} fill={c} opacity={0.9} />;
      })}
    </svg>
  );
}

export function PatternsDialog({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (p: Pattern) => void }) {
  const cats = ["전체", ...new Set(PATTERNS.map((p) => p.category))];
  const [cat, setCat] = useState("전체");
  if (!open) return null;
  const list = PATTERNS.filter((p) => cat === "전체" || p.category === cat);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="fade-in flex max-h-[88vh] w-full max-w-5xl flex-col rounded-2xl border border-border bg-surface shadow-soft" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold">에이전트 패턴 갤러리</h2>
            <p className="text-xs text-muted">검증된 설계를 불러와 구조와 생성 코드를 살펴보고 바로 실행해 보세요.</p>
          </div>
          <button onClick={onClose} className="ml-auto rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex gap-1.5 border-b border-border px-6 py-2.5">
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={cn("rounded-full px-3 py-1 text-xs", cat === c ? "bg-accent text-accent-fg" : "text-muted hover:bg-surface-2")}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="grid min-h-0 flex-1 auto-rows-max gap-4 overflow-y-auto p-6 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((p) => (
            <button
              key={p.id}
              onClick={() => onPick(p)}
              className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-bg text-left transition hover:-translate-y-0.5 hover:border-accent hover:shadow-soft"
            >
              <div className="bg-grid h-36 border-b border-border p-3">
                <MiniGraph p={p} />
              </div>
              <div className="flex flex-1 flex-col p-4">
                <div className="mb-1 flex items-center gap-2 text-[11px]">
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent">{p.category}</span>
                  <span className="text-muted">{p.difficulty}</span>
                </div>
                <div className="font-semibold group-hover:text-accent">{p.title}</div>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{p.summary}</p>
                <p className="mt-auto pt-3 text-[11.5px] leading-relaxed text-fg-2">
                  <b className="text-muted">언제?</b> {p.why}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
