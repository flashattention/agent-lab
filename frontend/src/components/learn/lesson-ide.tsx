"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { Eye, FileCode2, FlaskConical, KeyRound, Play, RotateCcw, Square, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProgress, useSettings } from "@/lib/settings";
import { CodeEditor, type EditorMarker } from "@/components/ide/code-editor";
import { ConsolePanel } from "@/components/ide/console-panel";
import { parseTraceback, useRunner } from "@/components/ide/use-runner";
import { SplitGroup, SplitHandle, SplitPanel } from "@/components/ui/split";

export type LessonIDEHandle = { openSnippet: (code: string) => void };

const tabLabel = (p: string) =>
  p === "exercise.py" ? "실습 과제" : p === "solution.py" ? "정답 코드" : p.replace(/^examples\//, "");

function orderFiles(paths: string[]) {
  const rank = (p: string) =>
    p.startsWith("examples/") ? 0 : p === "exercise.py" ? 1 : p.startsWith("scratch") ? 3 : p === "solution.py" ? 4 : 2;
  return [...paths].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

export const LessonIDE = forwardRef<LessonIDEHandle, { lessonId: string; files: Record<string, string>; requiresKey: boolean }>(
  function LessonIDE({ lessonId, files: original, requiresKey }, ref) {
    const storageKey = `agentlab-code:${lessonId}`;
    const [files, setFiles] = useState<Record<string, string>>(original);
    const [hydrated, setHydrated] = useState(false);
    const [showSolution, setShowSolution] = useState(false);
    const [open, setOpen] = useState<string[]>(() =>
      orderFiles(Object.keys(original).filter((p) => p.endsWith(".py") && p !== "solution.py")),
    );
    const [active, setActive] = useState<string>(() => open[0] ?? Object.keys(original)[0]);
    const [markers, setMarkers] = useState<Record<string, EditorMarker[]>>({});
    const [reveal, setReveal] = useState<{ line: number; nonce: number } | null>(null);
    const runner = useRunner();
    const apiKey = useSettings((s) => s.apiKey);
    const setOpenSettings = useSettings((s) => s.setOpen);
    const { done, toggle } = useProgress();

    // 저장된 수정본 복원
    useEffect(() => {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
        if (saved && typeof saved === "object") {
          setFiles((f) => ({ ...f, ...saved }));
          const scratch = Object.keys(saved).filter((k) => k.startsWith("scratch"));
          if (scratch.length) setOpen((o) => orderFiles([...new Set([...o, ...scratch])]));
        }
      } catch {}
      setHydrated(true);
    }, [storageKey]);

    // 원본과 다른 파일만 저장
    useEffect(() => {
      if (!hydrated) return;
      const diff = Object.fromEntries(Object.entries(files).filter(([k, v]) => original[k] !== v));
      try {
        if (Object.keys(diff).length) localStorage.setItem(storageKey, JSON.stringify(diff));
        else localStorage.removeItem(storageKey);
      } catch {}
    }, [files, hydrated, original, storageKey]);

    useImperativeHandle(ref, () => ({
      openSnippet: (code: string) => {
        let n = 1;
        while (files[`scratch_${n}.py`] !== undefined) n++;
        const p = `scratch_${n}.py`;
        setFiles((f) => ({ ...f, [p]: code }));
        setOpen((o) => orderFiles([...o, p]));
        setActive(p);
      },
    }));

    const run = useCallback(async () => {
      if (runner.status === "running") return;
      setMarkers({});
      const res = await runner.run(files, active);
      if (!res.ok) {
        const loc = parseTraceback(res.stderr, Object.keys(files));
        if (loc) {
          setMarkers({ [loc.file]: [{ line: loc.line, message: loc.message }] });
          if (loc.file === active) setReveal({ line: loc.line, nonce: Date.now() });
        }
      } else if (active === "exercise.py" && !done[lessonId]) {
        toggle(lessonId); // 과제 통과 → 강의 완료 처리
      }
    }, [active, done, files, lessonId, runner, toggle]);

    const jump = (file: string, line: number) => {
      const hit = Object.keys(files).find((f) => f === file || file.endsWith("/" + f));
      if (!hit) return;
      if (!open.includes(hit)) setOpen((o) => orderFiles([...o, hit]));
      setActive(hit);
      setTimeout(() => setReveal({ line, nonce: Date.now() }), 50);
    };

    const closeTab = (p: string) => {
      const next = open.filter((x) => x !== p);
      setOpen(next);
      if (p.startsWith("scratch")) setFiles(({ [p]: _, ...rest }) => rest);
      if (p === "solution.py") setShowSolution(false);
      if (active === p) setActive(next[0]);
    };

    const isModified = (p: string) => original[p] !== undefined && original[p] !== files[p];
    const helpers = useMemo(
      () => Object.keys(original).filter((p) => !open.includes(p) && p !== "solution.py" && !p.startsWith("examples/")),
      [open, original],
    );

    return (
      <div className="flex h-full min-h-0 flex-col bg-surface">
        {/* 탭 바 */}
        <div className="flex h-10 shrink-0 items-stretch border-b border-border bg-surface-2/60">
          <div className="flex min-w-0 flex-1 items-stretch overflow-x-auto">
            {open.map((p) => (
              <div
                key={p}
                onClick={() => setActive(p)}
                className={cn(
                  "group flex shrink-0 cursor-pointer items-center gap-1.5 border-r border-border px-3 text-[12.5px] transition-colors",
                  active === p ? "bg-surface text-fg" : "text-muted hover:text-fg",
                )}
              >
                {p === "exercise.py" ? (
                  <FlaskConical className="h-3.5 w-3.5 text-accent" />
                ) : (
                  <FileCode2 className="h-3.5 w-3.5 opacity-60" />
                )}
                <span className="font-mono">{tabLabel(p)}</span>
                {isModified(p) && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
                {(p.startsWith("scratch") || p === "solution.py") && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      closeTab(p);
                    }}
                    className="rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-surface-3"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
            {helpers.map((p) => (
              <button
                key={p}
                onClick={() => {
                  setOpen((o) => orderFiles([...o, p]));
                  setActive(p);
                }}
                className="shrink-0 px-2 font-mono text-[11px] text-muted hover:text-fg"
                title="보조 파일 열기"
              >
                + {p}
              </button>
            ))}
          </div>
          <div className="flex shrink-0 items-center gap-1 px-2">
            {original["solution.py"] && !showSolution && (
              <button
                onClick={() => {
                  setShowSolution(true);
                  setOpen((o) => orderFiles([...o, "solution.py"]));
                  setActive("solution.py");
                }}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted hover:bg-surface-3 hover:text-fg"
                title="정답 코드 보기"
              >
                <Eye className="h-3.5 w-3.5" /> 정답
              </button>
            )}
            <button
              onClick={() => original[active] !== undefined && setFiles((f) => ({ ...f, [active]: original[active] }))}
              disabled={!isModified(active)}
              className="rounded-md p-1.5 text-muted hover:bg-surface-3 hover:text-fg disabled:opacity-30"
              title="이 파일을 원래대로 되돌리기"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
            {runner.status === "running" ? (
              <button
                onClick={runner.stop}
                className="flex items-center gap-1.5 rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Square className="h-3 w-3 fill-current" /> 중지
              </button>
            ) : (
              <button
                onClick={run}
                className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg shadow-sm transition hover:brightness-110"
                title="실행 (⌘/Ctrl + Enter)"
              >
                <Play className="h-3 w-3 fill-current" /> 실행
              </button>
            )}
          </div>
        </div>

        {requiresKey && !apiKey && (
          <button
            onClick={() => setOpenSettings(true)}
            className="flex shrink-0 items-center gap-2 border-b border-border bg-warning/10 px-3 py-1.5 text-left text-[11.5px] text-warning"
          >
            <KeyRound className="h-3.5 w-3.5 shrink-0" />이 강의는 실제 LLM 응답을 봐야 효과가 큽니다. 지금은 Mock 모드로 실행됩니다. → API Key 설정
          </button>
        )}

        <SplitGroup orientation="vertical" className="min-h-0 flex-1">
          <SplitPanel defaultSize="64" minSize="20">
            {files[active] !== undefined ? (
              <CodeEditor
                path={`${lessonId}/${active}`}
                value={files[active]}
                onChange={(v) => setFiles((f) => ({ ...f, [active]: v }))}
                markers={markers[active]}
                onRun={run}
                revealLine={reveal}
              />
            ) : (
              <div className="grid h-full place-items-center text-sm text-muted">파일을 선택하세요</div>
            )}
          </SplitPanel>
          <SplitHandle vertical />
          <SplitPanel defaultSize="36" minSize="10">
            <ConsolePanel
              lines={runner.lines}
              status={runner.status}
              mock={runner.meta?.mock}
              onClear={runner.clear}
              onJump={jump}
            />
          </SplitPanel>
        </SplitGroup>
      </div>
    );
  },
);
