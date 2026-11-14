"use client";

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type BottomTab = "problems" | "terminal";

/** 왼쪽 아래 패널: 문제 / 터미널 탭. */
export function BottomPanel({
  tab,
  onTab,
  issueCount,
  hasErrors,
  running,
  problems,
  terminal,
}: {
  tab: BottomTab;
  onTab: (t: BottomTab) => void;
  issueCount: number;
  hasErrors: boolean;
  running: boolean;
  problems: ReactNode;
  terminal: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-8 shrink-0 items-stretch border-b border-border bg-surface text-xs">
        {(["problems", "terminal"] as const).map((t) => (
          <button
            key={t}
            onClick={() => onTab(t)}
            className={cn("flex items-center gap-1.5 border-b-2 px-3", tab === t ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")}
          >
            {t === "problems" ? "문제" : "터미널"}
            {t === "problems" && issueCount > 0 && <span className={cn("rounded-full px-1.5 text-[10px] font-bold text-white", hasErrors ? "bg-danger" : "bg-warning")}>{issueCount}</span>}
            {t === "terminal" && running && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">{tab === "terminal" ? terminal : problems}</div>
    </div>
  );
}
