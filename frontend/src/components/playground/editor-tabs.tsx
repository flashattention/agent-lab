"use client";

import { FileCode2, Network, RotateCcw, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { CANVAS_TAB, usePlayground } from "./store";

/** 가운데 위 탭 바: Canvas + 열린 파일들. */
export function EditorTabs({ modified, activeFile }: { modified: Set<string>; activeFile: string | null }) {
  const { tabs, activeTab, setActiveTab, closeTab, setOverride } = usePlayground();
  return (
    <div className="flex h-9 shrink-0 items-stretch overflow-x-auto border-b border-border bg-surface-2/60">
      {tabs.map((t) => (
        <div
          key={t}
          onClick={() => setActiveTab(t)}
          className={cn("group flex shrink-0 cursor-pointer items-center gap-1.5 border-r border-border px-3 text-[12px]", activeTab === t ? "bg-surface text-fg" : "text-muted hover:text-fg")}
        >
          {t === CANVAS_TAB ? <Network className="h-3.5 w-3.5 text-accent" /> : <FileCode2 className="h-3.5 w-3.5 opacity-60" />}
          <span className={t === CANVAS_TAB ? "font-medium" : "font-mono"}>{t === CANVAS_TAB ? "Canvas" : t.split("/").pop()}</span>
          {modified.has(t) && <span className="h-1.5 w-1.5 rounded-full bg-warning" />}
          {t !== CANVAS_TAB && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeTab(t);
              }}
              aria-label={`${t} 닫기`}
              className="rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-surface-3"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      ))}
      {activeFile && modified.has(activeFile) && (
        <button onClick={() => setOverride(activeFile, null)} className="ml-auto flex shrink-0 items-center gap-1 px-3 text-[11px] text-muted hover:text-fg">
          <RotateCcw className="h-3 w-3" /> 생성 코드로 되돌리기
        </button>
      )}
    </div>
  );
}
