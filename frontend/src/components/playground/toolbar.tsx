"use client";

import { useRef } from "react";
import { AlertTriangle, Boxes, CheckCircle2, Download, Eraser, FileUp, Group, LayoutGrid, Library, Loader2, OctagonAlert, Play, Redo2, Save, ShieldCheck, Sparkles, Square, Undo2 } from "lucide-react";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import { ProjectBar } from "./project-bar";
import { usePlayground } from "./store";
import { ToolButton } from "./tool-button";
import type { useProjectSync } from "./use-project-sync";

type Props = {
  sync: ReturnType<typeof useProjectSync>;
  counts: { errors: number; warnings: number; nodes: number };
  canRun: boolean;
  busy: null | "validate" | "refine";
  running: boolean;
  onPatterns: () => void;
  onPresets: () => void;
  onGroup: () => void;
  canGroup: boolean;
  onSaveAgent: () => void;
  inside: boolean; // 서브그래프 안을 보고 있는지
  onImport: (file: File) => void;
  onAutoLayout: () => void;
  onDownload: () => void;
  onValidate: () => void;
  onRefine: () => void;
  onRun: () => void;
  onStop: () => void;
};

/** 플레이그라운드 왼쪽 위 툴바: 프로젝트 이름·공유, 편집 도구, 구조 상태, 검증·고도화·실행. */
export function PlaygroundToolbar({ sync, counts, canRun, busy, running, onPatterns, onPresets, onGroup, canGroup, onSaveAgent, inside, onImport, onAutoLayout, onDownload, onValidate, onRefine, onRun, onStop }: Props) {
  const { undo, redo, clear, past, future } = usePlayground();
  const fileRef = useRef<HTMLInputElement>(null);
  const { errors, warnings, nodes } = counts;
  const status = errors ? `오류 ${errors}` : warnings ? `경고 ${warnings}` : nodes ? "정상" : "비어 있음";

  return (
    <div className="shrink-0 space-y-1.5 border-b border-border px-2 py-2">
      <div className="min-w-0">{SUPABASE_ENABLED ? <ProjectBar sync={sync} /> : <span className="px-1.5 text-sm font-semibold">플레이그라운드</span>}</div>
      <div className="flex flex-wrap items-center gap-0.5">
        <button onClick={onPatterns} className="mr-1 flex shrink-0 items-center gap-1.5 rounded-lg bg-accent-soft px-2.5 py-1.5 text-xs font-semibold text-accent hover:brightness-105">
          <Library className="h-3.5 w-3.5" /> 패턴
        </button>
        <button onClick={onPresets} title="저장해 둔 에이전트를 Sub-agent 로 불러오기" className="mr-1 flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-surface-2">
          <Boxes className="h-3.5 w-3.5 text-accent" /> 프리셋
        </button>
        <ToolButton icon={Undo2} label="실행 취소" title="실행 취소 (Ctrl/⌘+Z)" onClick={undo} disabled={!past.length} />
        <ToolButton icon={Redo2} label="다시 실행" title="다시 실행 (Ctrl/⌘+Shift+Z)" onClick={redo} disabled={!future.length} />
        <ToolButton icon={LayoutGrid} label="자동 정렬" onClick={onAutoLayout} />
        <ToolButton icon={Eraser} label="비우기" onClick={() => confirm(inside ? "이 서브그래프 내부를 비울까요?" : "캔버스를 비울까요?") && clear()} />
        <ToolButton icon={Group} label="Sub-agent로 묶기" title="선택한 노드를 Sub-agent 하나로 묶기 (Shift+드래그로 여러 개 선택)" onClick={onGroup} disabled={!canGroup} />
        <ToolButton icon={Save} label={inside ? "이 서브그래프를 프리셋으로" : "에이전트로 저장"} title="지금 보고 있는 그래프를 프리셋으로 저장해 다른 그래프에서 Sub-agent 로 재사용" onClick={onSaveAgent} disabled={!nodes} />
        <ToolButton icon={FileUp} label="가져오기" title="agentlab.json 또는 내려받은 ZIP 에서 그래프 가져오기" onClick={() => fileRef.current?.click()} />
        <input
          ref={fileRef}
          type="file"
          accept=".json,.zip,application/json,application/zip"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onImport(f);
            e.target.value = "";
          }}
        />
        <ToolButton icon={Download} label="ZIP 다운로드" title="생성 코드 + agentlab.json 내려받기" onClick={onDownload} disabled={!nodes} />
        <div
          title={errors ? `구조 오류 ${errors}` : warnings ? `경고 ${warnings}` : nodes ? "구조 정상" : "비어 있음"}
          className={cn(
            "ml-auto flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium",
            errors ? "bg-danger/10 text-danger" : warnings ? "bg-warning/10 text-warning" : nodes ? "bg-success/10 text-success" : "text-muted",
          )}
        >
          {errors ? <OctagonAlert className="h-3.5 w-3.5" /> : warnings ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
          {status}
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <button
          onClick={onValidate}
          disabled={!!busy || !canRun}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-xs font-medium hover:bg-surface-2 disabled:opacity-40"
          title="ruff 문법 검사 + Mock LLM 실행 검증"
        >
          {busy === "validate" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />} 검증
        </button>
        <button
          onClick={onRefine}
          disabled={!!busy || !canRun}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-2 py-1.5 text-xs font-semibold whitespace-nowrap text-accent hover:border-accent disabled:opacity-40"
          title="고성능 LLM으로 코드를 고도화하고, 검증을 통과하면 구조별로 캐싱합니다"
        >
          {busy === "refine" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} 고도화
        </button>
        {running ? (
          <button onClick={onStop} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-danger px-2 py-1.5 text-xs font-semibold text-white">
            <Square className="h-3 w-3 fill-current" /> 중지
          </button>
        ) : (
          <button
            onClick={onRun}
            disabled={!canRun}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-accent px-2 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110 disabled:opacity-40"
            title={canRun ? "main.py 실행 (Ctrl/⌘+Enter)" : "구조 오류를 먼저 해결하세요"}
          >
            <Play className="h-3 w-3 fill-current" /> 실행
          </button>
        )}
      </div>
    </div>
  );
}
