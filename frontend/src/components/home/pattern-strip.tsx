"use client";

import Link from "next/link";
import { useMemo } from "react";
import { PATTERNS } from "@/lib/playground/patterns";
import { arranged } from "@/components/playground/store";
import { GraphThumb } from "@/components/projects/graph-thumb";

/** 첫 화면의 패턴 목록. 실제 패턴 그래프를 그대로 축소해 보여 준다. */
export function PatternStrip() {
  const items = useMemo(() => PATTERNS.map((p) => ({ ...p, graph: arranged(p.graph) })), []);
  return (
    <ul className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((p) => (
        <li key={p.id}>
          <Link href="/playground" className="flex h-full flex-col rounded-xl border border-border bg-surface p-3 transition hover:border-accent">
            <GraphThumb graph={p.graph} className="mb-3 h-20 w-full sm:h-28 rounded-lg bg-surface-2 p-2.5" />
            <span className="text-sm font-medium">{p.title}</span>
            <span className="mt-1 text-xs text-muted">
              {p.category}, {p.difficulty}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
