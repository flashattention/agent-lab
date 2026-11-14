"use client";

import { useEffect, useRef, useState } from "react";
import { Check, CloudOff, Copy, Eye, Globe, Link2, Loader2, Lock, Save, Share2, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { shareUrl } from "@/lib/projects";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import { SignInButton } from "@/components/auth/auth-menu";
import { usePlayground } from "./store";
import type { SaveState, useProjectSync } from "./use-project-sync";

type Sync = ReturnType<typeof useProjectSync>;

const STATUS: Partial<Record<SaveState, string>> = { saved: "저장됨", dirty: "저장 대기 중", saving: "저장 중…", loading: "불러오는 중…" };

/** 툴바 왼쪽: 프로젝트 이름, 저장 상태, 공유. */
export function ProjectBar({ sync }: { sync: Sync }) {
  const user = useAuth((s) => s.user);
  const { projectId, projectName, owned, setProjectName } = usePlayground();
  const [share, setShare] = useState(false);

  if (!SUPABASE_ENABLED) return null;

  // 임시 캔버스: 저장하면 프로젝트가 된다
  if (!projectId) {
    if (sync.state === "loading") return <Status state="loading" />;
    return user ? (
      <button onClick={sync.saveAsProject} disabled={sync.state === "saving"} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2 disabled:opacity-50" title="이 캔버스를 내 프로젝트로 저장합니다">
        {sync.state === "saving" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} 프로젝트로 저장
      </button>
    ) : (
      <span className="hidden items-center gap-2 text-xs text-muted lg:flex">
        <CloudOff className="h-3.5 w-3.5" /> 이 브라우저에만 저장됨
      </span>
    );
  }

  if (!owned)
    return (
      <div className="flex min-w-0 items-center gap-2">
        <span className="flex shrink-0 items-center gap-1 rounded-full bg-surface-2 px-2 py-1 text-[11px] font-medium text-muted">
          <Eye className="h-3 w-3" /> 보기 전용
        </span>
        <span className="truncate text-sm font-medium">{projectName}</span>
        {user ? (
          <button onClick={sync.duplicate} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
            <Copy className="h-3.5 w-3.5" /> 내 프로젝트로 복제
          </button>
        ) : (
          <SignInButton label="로그인하고 복제" />
        )}
      </div>
    );

  return (
    <div className="flex min-w-0 items-center gap-2">
      <input
        value={projectName}
        maxLength={80}
        onChange={(e) => setProjectName(e.target.value)}
        onBlur={() => !projectName.trim() && setProjectName("제목 없는 프로젝트")}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        aria-label="프로젝트 이름"
        className="w-full min-w-0 flex-1 truncate rounded-md border border-transparent bg-transparent px-1.5 py-1 text-sm font-medium outline-none hover:border-border focus:border-accent focus:bg-bg"
      />
      <Status state={sync.state} error={sync.error} onRetry={sync.flush} />
      <button onClick={() => setShare(true)} className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-surface-2">
        <Share2 className="h-3.5 w-3.5" /> 공유
      </button>
      {share && <ShareDialog sync={sync} onClose={() => setShare(false)} />}
    </div>
  );
}

function Status({ state, error, onRetry }: { state: SaveState; error?: string; onRetry?: () => void }) {
  if (state === "error")
    return (
      <button onClick={onRetry} title={error} className="flex shrink-0 items-center gap-1 text-[11px] font-medium text-danger">
        <CloudOff className="h-3.5 w-3.5" /> 저장 실패 · 다시 시도
      </button>
    );
  const text = STATUS[state];
  if (!text) return null;
  return (
    <span className="hidden shrink-0 items-center gap-1 text-[11px] text-muted md:flex" aria-live="polite">
      {state === "saved" ? <Check className="h-3 w-3 text-success" /> : <Loader2 className={cn("h-3 w-3", state !== "dirty" && "animate-spin")} />}
      {text}
    </span>
  );
}

function ShareDialog({ sync, onClose }: { sync: Sync; onClose: () => void }) {
  const { projectId, isPublic } = usePlayground();
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const url = projectId ? shareUrl(projectId) : "";

  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  const toggle = async (v: boolean) => {
    setBusy(true);
    setError("");
    try {
      await sync.setPublic(v);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="프로젝트 공유" className="fade-in w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-soft outline-none">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">프로젝트 공유</h2>
          <button onClick={onClose} aria-label="닫기" className="grid h-7 w-7 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-fg">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {[
            { v: false, icon: Lock, title: "나만 보기", desc: "다른 사람은 열 수 없습니다" },
            { v: true, icon: Globe, title: "링크가 있는 누구나", desc: "보기와 복제만 가능합니다" },
          ].map(({ v, icon: I, title, desc }) => (
            <button
              key={title}
              disabled={busy}
              onClick={() => isPublic !== v && toggle(v)}
              aria-pressed={isPublic === v}
              className={cn("rounded-xl border p-3 text-left transition disabled:opacity-60", isPublic === v ? "border-accent bg-accent-soft" : "border-border hover:border-border-strong")}
            >
              <I className={cn("mb-2 h-4 w-4", isPublic === v ? "text-accent" : "text-muted")} />
              <div className="text-sm font-medium">{title}</div>
              <div className="text-xs text-muted">{desc}</div>
            </button>
          ))}
        </div>
        {isPublic && (
          <div className="mt-4 flex items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-bg px-2.5 py-2">
              <Link2 className="h-3.5 w-3.5 shrink-0 text-muted" />
              <span className="truncate font-mono text-xs">{url}</span>
            </div>
            <button onClick={copy} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-accent-fg hover:brightness-110">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} {copied ? "복사됨" : "링크 복사"}
            </button>
          </div>
        )}
        {error && <p className="mt-3 text-xs text-danger">공유 설정을 바꾸지 못했습니다: {error}</p>}
        <p className="mt-4 text-xs leading-relaxed text-muted">링크를 받은 사람은 그래프와 생성된 코드를 볼 수 있고, 로그인하면 자기 작업 공간에 복제해 편집할 수 있습니다. 원본은 바뀌지 않습니다.</p>
      </div>
    </div>
  );
}
