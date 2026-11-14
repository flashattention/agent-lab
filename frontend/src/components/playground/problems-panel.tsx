"use client";

import { AlertTriangle, CheckCircle2, OctagonAlert, Sparkles } from "lucide-react";
import type { analyze } from "@/lib/playground/analyze";
import type { ValidateReport } from "@/lib/api";
import { cn } from "@/lib/utils";

/** 구조 분석 결과, 코드 검증 결과, LLM 고도화 노트. 문제를 누르면 해당 노드로 이동한다. */
export function ProblemsPanel({
  analysis,
  validation,
  refinedNotes,
  onFocus,
}: {
  analysis: ReturnType<typeof analyze>;
  validation: ValidateReport | null;
  refinedNotes?: string;
  onFocus: (ids?: string[]) => void;
}) {
  return (
    <div className="h-full overflow-y-auto bg-surface px-2 py-1.5 text-[12.5px]">
      {analysis.issues.length === 0 && !validation && (
        <div className="flex items-center gap-2 p-2 text-success">
          <CheckCircle2 className="h-4 w-4" /> 구조 분석 통과 — 실행하거나 &lsquo;검증&rsquo;으로 문법·실행 검사를 해보세요.
        </div>
      )}
      {analysis.issues.map((i, k) => (
        <button key={k} onClick={() => onFocus(i.nodes)} className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
          {i.level === "error" ? (
            <OctagonAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
          ) : i.level === "warning" ? (
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" />
          )}
          <span>
            <span className="text-fg">{i.message}</span>
            {i.hint && <span className="block text-[11.5px] text-muted">{i.hint}</span>}
          </span>
        </button>
      ))}
      {validation && (
        <div className="mt-2 border-t border-border px-2 pt-2">
          <div className={cn("mb-1 flex items-center gap-1.5 font-medium", validation.ok ? "text-success" : "text-danger")}>
            {validation.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <OctagonAlert className="h-3.5 w-3.5" />}
            코드 검증 {validation.ok ? "통과" : "실패"}
            {validation.run && <span className="text-[11px] font-normal text-muted">· Mock 실행 {validation.run.duration_ms}ms · exit {validation.run.exit_code}</span>}
          </div>
          {validation.lint.map((l, k) => (
            <div key={k} className="font-mono text-[11.5px] text-danger">
              {l.file}:{l.line}:{l.col} {l.code} {l.message}
            </div>
          ))}
          {validation.run && !validation.ok && <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-code p-2 font-mono text-[11px] whitespace-pre-wrap text-danger">{validation.run.stderr.slice(-2000)}</pre>}
        </div>
      )}
      {refinedNotes && (
        <div className="mt-2 border-t border-border px-2 pt-2">
          <div className="mb-1 flex items-center gap-1.5 font-medium text-accent">
            <Sparkles className="h-3.5 w-3.5" /> LLM 고도화 노트
          </div>
          <p className="text-[12px] whitespace-pre-wrap text-fg-2">{refinedNotes}</p>
        </div>
      )}
    </div>
  );
}
