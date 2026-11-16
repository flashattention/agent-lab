"use client";

import Link from "next/link";
import { useMemo } from "react";
import { PATTERNS } from "@/lib/playground/patterns";
import { arranged } from "@/components/playground/store";
import { GraphThumb } from "@/components/projects/graph-thumb";
import { cn } from "@/lib/utils";

/** 첫 화면의 패턴 목록. 실제 패턴 그래프를 그대로 축소해 보여 준다. Sub-agent 를 쓰는 패턴은 크게 보여 준다. */
export function PatternStrip() {
  const items = useMemo(() => {
    const all = PATTERNS.map((p) => ({ ...p, graph: arranged(p.graph), featured: p.graph.nodes.some((n) => n.kind === "subgraph") }));
    return [...all.filter((p) => p.featured), ...all.filter((p) => !p.featured)];
  }, []);
  return (
    <ul className="grid grid-flow-dense grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((p) => (
        <li key={p.id} className={cn(p.featured && "col-span-2 row-span-2")}>
          <Link
            href="/playground"
            className={cn("flex h-full flex-col rounded-xl border bg-surface p-3 transition hover:border-accent", p.featured ? "border-accent/50" : "border-border")}
          >
            <GraphThumb graph={p.graph} className={cn("mb-3 w-full rounded-lg bg-surface-2 p-2.5", p.featured ? "h-44 flex-1 sm:h-auto sm:min-h-56" : "h-20 sm:h-28")} />
            <span className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
              {p.title}
              {p.featured && <span className="rounded-full bg-accent-soft px-1.5 py-px text-[10px] font-semibold text-accent">Sub-agent</span>}
            </span>
            <span className="mt-1 text-xs text-muted">
              {p.category}, {p.difficulty}
            </span>
            {p.featured && <span className="mt-2 text-[13px] leading-relaxed text-muted">{p.summary}</span>}
          </Link>
        </li>
      ))}
    </ul>
  );
}
