"use client";

import { AlertTriangle } from "lucide-react";

/**
 * 공유받은 프로젝트에 작성자가 직접 쓴 코드(수정한 파일, Function 노드 코드)가 있을 때,
 * 내 API 키로 실행하기 전에 확인을 받는다. 키 문자열은 키 프록시 덕분에 노출되지 않지만 비용은 발생할 수 있다.
 */
export function SharedRunDialog({
  files,
  functionNodes,
  onOpenFile,
  onCancel,
  onRunWithKey,
  onRunMock,
}: {
  files: string[];
  functionNodes: string[];
  onOpenFile: (f: string) => void;
  onCancel: () => void;
  onRunWithKey: () => void;
  onRunMock: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div role="dialog" aria-modal="true" aria-label="공유 프로젝트 실행 확인" className="fade-in w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-soft">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <AlertTriangle className="h-4 w-4 text-warning" /> 다른 사람이 작성한 코드가 들어 있습니다
        </div>
        <p className="text-[12.5px] leading-relaxed text-fg-2">
          이 공유 프로젝트에는 작성자가 직접 쓴 코드가 있습니다. API 키 문자열은 실행 코드에 전달되지 않지만, 코드가 실행되는 동안 <b>내 키로 OpenAI를 호출해 비용을 발생시킬 수는 있습니다.</b> 먼저 코드를
          확인하거나 Mock 모드로 실행해 보세요.
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          {files.map((f) => (
            <button key={f} onClick={() => onOpenFile(f)} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-2 hover:text-accent">
              {f}
            </button>
          ))}
          {functionNodes.map((n) => (
            <span key={n} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-2">
              Function 노드: {n}
            </span>
          ))}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-fg">
            취소
          </button>
          <button onClick={onRunWithKey} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2">
            내 키로 실행
          </button>
          <button onClick={onRunMock} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
            Mock 모드로 실행
          </button>
        </div>
      </div>
    </div>
  );
}
