"use client";

import { useEffect, useRef } from "react";
import { Loader2, Terminal, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConsoleLine, RunStatus } from "./use-runner";

const KIND_CLASS: Record<ConsoleLine["kind"], string> = {
  stdout: "text-fg-2",
  stderr: "text-danger/90",
  info: "text-muted",
  error: "text-danger font-medium",
  success: "text-success font-medium",
};

/** 실행 결과 콘솔. traceback 의 `File "x.py", line N` 을 클릭하면 에디터로 이동한다. */
export function ConsolePanel({
  lines,
  status,
  mock,
  onClear,
  onJump,
  title = "출력",
  extra,
}: {
  lines: ConsoleLine[];
  status: RunStatus;
  mock?: boolean;
  onClear: () => void;
  onJump?: (file: string, line: number) => void;
  title?: string;
  extra?: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [lines]);

  const renderText = (text: string) => {
    if (!onJump) return text;
    const parts = text.split(/(File "[^"]+", line \d+)/g);
    return parts.map((p, i) => {
      const m = /File "([^"]+)", line (\d+)/.exec(p);
      if (!m || m[1].includes("site-packages") || m[1].startsWith("<")) return <span key={i}>{p}</span>;
      return (
        <button
          key={i}
          onClick={() => onJump(m[1], Number(m[2]))}
          className="underline decoration-dotted underline-offset-2 hover:text-accent"
        >
          {p}
        </button>
      );
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-border px-3 text-xs">
        <Terminal className="h-3.5 w-3.5 text-muted" />
        <span className="font-medium">{title}</span>
        {status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
        {mock !== undefined && (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium",
              mock ? "bg-warning/15 text-warning" : "bg-success/15 text-success",
            )}
          >
            {mock ? "Mock LLM" : "OpenAI"}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {extra}
          <button onClick={onClear} title="지우기" className="rounded p-1 text-muted hover:bg-surface-2 hover:text-fg">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div ref={ref} className="min-h-0 flex-1 overflow-auto bg-code px-3 py-2 font-mono text-[12.5px] leading-relaxed">
        {lines.length === 0 ? (
          <div className="pt-1 text-muted">▶ 실행(⌘/Ctrl + Enter)하면 결과가 여기에 표시됩니다.</div>
        ) : (
          lines.map((l, i) => (
            <pre key={i} className={cn("break-words whitespace-pre-wrap", KIND_CLASS[l.kind])}>
              {l.kind === "stderr" ? renderText(l.text) : l.text}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}
