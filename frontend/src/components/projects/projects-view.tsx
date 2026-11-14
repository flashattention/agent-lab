"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Copy, Globe, Link2, Loader2, Lock, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { createProject, deleteProject, duplicateProject, listProjects, saveProject, shareUrl, type Project } from "@/lib/projects";
import { PATTERNS } from "@/lib/playground/patterns";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import { SignInButton } from "@/components/auth/auth-menu";
import { arranged } from "@/components/playground/store";
import { GraphThumb } from "./graph-thumb";

const STARTERS = PATTERNS.map((p) => ({ ...p, graph: arranged(p.graph) }));

function ago(iso: string) {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "방금 전";
  if (m < 60) return `${m}분 전`;
  if (m < 60 * 24) return `${Math.floor(m / 60)}시간 전`;
  if (m < 60 * 24 * 30) return `${Math.floor(m / 1440)}일 전`;
  return new Date(iso).toLocaleDateString("ko-KR");
}

export function ProjectsView() {
  const { ready, user } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<Project[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!user) return;
    try {
      setItems(await listProjects(user.id));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [user]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  const create = async (patternId: string) => {
    const p = STARTERS.find((x) => x.id === patternId) ?? STARTERS[0];
    setCreating(patternId);
    try {
      const made = await createProject({ name: p.title, graph: p.graph, pattern_id: p.id });
      router.push(`/playground?p=${made.id}`);
    } catch (e) {
      setError((e as Error).message);
      setCreating(null);
    }
  };

  if (!SUPABASE_ENABLED)
    return (
      <Empty title="이 환경에는 로그인이 설정되어 있지 않습니다">
        프로젝트 저장은 Supabase 설정 후 쓸 수 있습니다. 플레이그라운드의 캔버스는 이 브라우저에 그대로 저장됩니다.
        <Link href="/playground" className="mt-5 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg">
          플레이그라운드 열기
        </Link>
      </Empty>
    );
  if (!ready) return <div className="grid flex-1 place-items-center text-sm text-muted">불러오는 중…</div>;
  if (!user)
    return (
      <Empty title="로그인하면 프로젝트가 계정에 저장됩니다">
        여러 프로젝트를 만들어 두고 어느 기기에서나 이어서 작업하고, 링크로 공유할 수 있습니다.
        <div className="mt-5 flex justify-center">
          <SignInButton className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium hover:border-border-strong hover:bg-surface-2" />
        </div>
      </Empty>
    );

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">내 프로젝트</h1>
          <p className="mt-1 text-sm text-muted">수정한 내용은 자동으로 저장됩니다.</p>
        </div>
        <button
          onClick={() => create(PATTERNS[0].id)}
          disabled={!!creating}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg hover:brightness-110 disabled:opacity-60"
        >
          {creating === PATTERNS[0].id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} 새 프로젝트
        </button>
      </div>

      {error && <div className="mb-6 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">프로젝트를 처리하지 못했습니다: {error}</div>}

      {items === null && !error && <div className="py-20 text-center text-sm text-muted">불러오는 중…</div>}

      {items && items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border-strong px-6 py-14 text-center">
          <p className="text-base font-medium">아직 프로젝트가 없습니다</p>
          <p className="mt-1 text-sm text-muted">아래 패턴 중 하나로 시작해 보세요.</p>
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((p) => (
            <ProjectCard key={p.id} project={p} onChanged={load} onToast={setToast} onError={setError} />
          ))}
        </ul>
      )}

      <h2 className="mt-14 mb-4 text-sm font-semibold text-fg-2">패턴으로 시작</h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STARTERS.map((p) => (
          <li key={p.id}>
            <button
              onClick={() => create(p.id)}
              disabled={!!creating}
              className="group flex h-full w-full flex-col rounded-xl border border-border bg-surface p-3 text-left transition hover:border-accent disabled:opacity-60"
            >
              <GraphThumb graph={p.graph} className="mb-3 h-24 w-full rounded-lg bg-surface-2 p-2" />
              <span className="flex items-center gap-1.5 text-sm font-medium">
                {p.title}
                {creating === p.id && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
              </span>
              <span className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted">{p.summary}</span>
            </button>
          </li>
        ))}
      </ul>

      {toast && <div className="fade-in fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-fg px-4 py-2 text-sm text-bg shadow-soft">{toast}</div>}
    </main>
  );
}

function Empty({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="grid flex-1 place-items-center px-6 py-20">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-bold tracking-tight">{title}</h1>
        <div className="mt-2 text-sm leading-relaxed text-muted">{children}</div>
      </div>
    </main>
  );
}

function ProjectCard({ project: p, onChanged, onToast, onError }: { project: Project; onChanged: () => void; onToast: (s: string) => void; onError: (s: string) => void }) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(p.name);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setMenu(false);
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [menu]);

  const act = async (fn: () => Promise<unknown>, done?: string) => {
    setMenu(false);
    try {
      await fn();
      if (done) onToast(done);
      onChanged();
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const rename = () => {
    setRenaming(false);
    const next = name.trim().slice(0, 80);
    if (!next || next === p.name) return setName(p.name);
    act(() => saveProject(p.id, { name: next }));
  };

  const copyLink = async () => {
    if (!p.is_public) await saveProject(p.id, { is_public: true });
    await navigator.clipboard.writeText(shareUrl(p.id));
  };

  return (
    <li className="group relative rounded-xl border border-border bg-surface transition hover:border-border-strong hover:shadow-soft">
      <Link href={`/playground?p=${p.id}`} className="block p-3 pb-0" aria-label={`${p.name} 열기`}>
        <GraphThumb graph={p.graph} className="h-36 w-full rounded-lg bg-surface-2 p-3" />
      </Link>
      <div className="flex items-start gap-2 p-3">
        <div className="min-w-0 flex-1">
          {renaming ? (
            <input
              autoFocus
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              onBlur={rename}
              onKeyDown={(e) => {
                if (e.key === "Enter") rename();
                if (e.key === "Escape") {
                  setName(p.name);
                  setRenaming(false);
                }
              }}
              className="w-full rounded-md border border-accent bg-bg px-1.5 py-0.5 text-sm font-medium outline-none"
            />
          ) : (
            <Link href={`/playground?p=${p.id}`} className="block truncate text-sm font-medium hover:text-accent">
              {p.name}
            </Link>
          )}
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            {p.is_public ? <Globe className="h-3 w-3" /> : <Lock className="h-3 w-3" />}
            {p.is_public ? "링크 공유 중" : "나만 보기"} · {ago(p.updated_at)} 수정
          </div>
        </div>
        <div ref={ref} className="relative">
          <button onClick={() => setMenu((v) => !v)} aria-label={`${p.name} 메뉴`} aria-haspopup="menu" aria-expanded={menu} className="grid h-7 w-7 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-fg">
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {menu && (
            <div role="menu" className="fade-in absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-lg border border-border bg-surface py-1 text-sm shadow-soft">
              <MenuItem icon={Pencil} onClick={() => { setMenu(false); setRenaming(true); }}>이름 바꾸기</MenuItem>
              <MenuItem icon={Copy} onClick={() => act(() => duplicateProject(p), "복제했습니다")}>복제</MenuItem>
              <MenuItem icon={Link2} onClick={() => act(copyLink, "공유 링크를 복사했습니다")}>공유 링크 복사</MenuItem>
              {p.is_public && <MenuItem icon={Lock} onClick={() => act(() => saveProject(p.id, { is_public: false }), "공유를 껐습니다")}>공유 끄기</MenuItem>}
              <MenuItem icon={Trash2} danger onClick={() => { setMenu(false); if (confirm(`'${p.name}' 프로젝트를 삭제할까요? 되돌릴 수 없습니다.`)) act(() => deleteProject(p.id), "삭제했습니다"); }}>삭제</MenuItem>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function MenuItem({ icon: I, children, onClick, danger }: { icon: typeof Copy; children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button role="menuitem" onClick={onClick} className={cn("flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-surface-2", danger && "text-danger")}>
      <I className="h-3.5 w-3.5" /> {children}
    </button>
  );
}
