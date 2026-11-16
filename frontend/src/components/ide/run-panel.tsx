"use client";

import { useState } from "react";
import { Activity, Loader2, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConsolePanel } from "./console-panel";
import { TracePanel } from "./trace-panel";
import type { useRunner } from "./use-runner";

/** 실행 결과 패널: 출력(콘솔) / 트레이스 탭. 트레이스가 들어오기 시작하면 한 번 자동으로 트레이스 탭을 보여 준다. */
export function RunPanel({ runner, onJump }: { runner: ReturnType<typeof useRunner>; onJump?: (file: string, line: number) => void }) {
  const [tab, setTab] = useState<"output" | "trace">("output");
  const running = runner.status === "running";
  const hasTrace = runner.trace.length > 0;

  // 새 실행에서 첫 트레이스가 오면 트레이스 탭으로 전환 (사용자가 다시 바꾸면 그대로 둔다)
  const [autoSwitched, setAutoSwitched] = useState(false);
  if (running && !hasTrace && autoSwitched) setAutoSwitched(false);
  if (running && hasTrace && !autoSwitched) {
    setAutoSwitched(true);
    setTab("trace");
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-8 shrink-0 items-stretch border-b border-border bg-surface text-xs">
        {(
          [
            ["output", "출력", Terminal],
            ["trace", "트레이스", Activity],
          ] as const
        ).map(([k, label, I]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={cn("flex items-center gap-1.5 border-b-2 px-3", tab === k ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")}
          >
            <I className="h-3.5 w-3.5" />
            {label}
            {k === "trace" && hasTrace && <span className="rounded-full bg-surface-2 px-1.5 text-[10px] text-muted">{new Set(runner.trace.map((e) => e.id)).size}</span>}
            {running && k === tab && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        {tab === "output" ? (
          <ConsolePanel lines={runner.lines} status={runner.status} mock={runner.meta?.mock} onClear={runner.clear} onJump={onJump} />
        ) : (
          <TracePanel events={runner.trace} live={running} />
        )}
      </div>
    </div>
  );
}
