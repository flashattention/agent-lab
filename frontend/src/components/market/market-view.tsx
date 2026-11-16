"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Download, Globe, Loader2, Search, ShieldCheck, Upload } from "lucide-react";
import { getSharedPreset, listMarket, MARKET_CATEGORIES, setPendingPreset, usePresets, type AgentPreset, type MarketQuery } from "@/lib/presets";
import { summarize } from "@/lib/playground/subgraph";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { GraphThumb } from "@/components/projects/graph-thumb";
import { arrangedSub } from "@/components/playground/store";
import { SignInButton } from "@/components/auth/auth-menu";
import { PresetDetail, TrustBadges } from "./preset-detail";

/** 공개 갤러리 목록: 검색 · 카테고리 · 정렬. 마켓 페이지와 플레이그라운드 프리셋 창에서 함께 쓴다. */
export function MarketGrid({ onOpen, dense }: { onOpen: (p: AgentPreset) => void; dense?: boolean }) {
  const [query, setQuery] = useState<MarketQuery>({ sort: "popular" });
  const [q, setQ] = useState("");
  const [items, setItems] = useState<AgentPreset[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    listMarket(query)
      .then((r) => alive && (setItems(r), setError("")))
      .catch((e) => alive && (setError((e as Error).message), setItems([])));
    return () => {
      alive = false;
    };
  }, [query]);

  const list = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!items || !words.length) return items ?? [];
    return items.filter((p) => {
      const text = [p.name, p.node_name, p.description, p.author_name, ...(p.tags ?? [])].join(" ").toLowerCase();
      return words.every((w) => text.includes(w));
    });
  }, [items, q]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름 · 설명 · 작성자 검색" className="w-full rounded-lg border border-border bg-bg py-1.5 pr-2.5 pl-8 text-[13px] outline-none focus:border-accent" />
        </div>
        <div className="flex rounded-lg border border-border p-0.5 text-xs">
          {(
            [
              ["popular", "인기순"],
              ["recent", "최신순"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => (setItems(null), setQuery((x) => ({ ...x, sort: id })))}
              className={cn("rounded-md px-2.5 py-1", query.sort === id ? "bg-accent text-accent-fg" : "text-muted hover:text-fg")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {[undefined, ...MARKET_CATEGORIES].map((c) => (
          <button
            key={c ?? "all"}
            onClick={() => (setItems(null), setQuery((x) => ({ ...x, category: c })))}
            className={cn("rounded-full px-3 py-1 text-xs", query.category === c ? "bg-fg text-bg" : "bg-surface-2 text-muted hover:text-fg")}
          >
            {c ?? "전체"}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning">{error}</p>}
      {items === null ? (
        <p className="mt-8 flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
        </p>
      ) : list.length === 0 && !error ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">
          {q ? "검색 결과가 없습니다." : "아직 이 카테고리에 공개된 에이전트가 없습니다. 첫 번째로 올려 보세요."}
        </div>
      ) : (
        <ul className={cn("mt-5 grid gap-4", dense ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4")}>
          {list.map((p) => (
            <li key={p.id}>
              <button onClick={() => onOpen(p)} className="flex h-full w-full flex-col overflow-hidden rounded-2xl border border-border bg-surface text-left transition hover:border-accent hover:shadow-soft">
                <div className="bg-grid h-32 w-full border-b border-border p-3">
                  <GraphThumb graph={arrangedSub(p.graph)} className="h-full w-full" />
                </div>
                <div className="flex flex-1 flex-col p-4">
                  <div className="mb-1.5">
                    <TrustBadges p={p} compact />
                  </div>
                  <span className="font-semibold">{p.name}</span>
                  <span className="text-[11.5px] text-muted">
                    {p.author_name || "익명"} · {p.category} · 노드 {summarize(p.graph).count}
                  </span>
                  <p className="mt-1.5 line-clamp-2 text-[12.5px] leading-relaxed text-muted">{p.description}</p>
                  <span className="mt-auto flex items-center gap-1 pt-3 text-[11.5px] text-muted">
                    <Download className="h-3 w-3" /> {(p.installs ?? 0).toLocaleString()}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** /agents: 에이전트 마켓 페이지. ?id= 로 링크 공유된 에이전트를 바로 연다. */
export function MarketView() {
  const router = useRouter();
  const sharedId = useSearchParams().get("id");
  const user = useAuth((x) => x.user);
  const [open, setOpen] = useState<AgentPreset | null>(null);
  const [sharedError, setSharedError] = useState("");

  useEffect(() => {
    if (!sharedId || !SUPABASE_ENABLED) return;
    let alive = true;
    getSharedPreset(sharedId)
      .then((p) => alive && (p ? setOpen(p) : setSharedError("이 링크의 에이전트를 찾을 수 없습니다. 비공개로 바뀌었거나 삭제되었습니다.")))
      .catch((e) => alive && setSharedError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [sharedId]);

  const use = (p: AgentPreset) => {
    setPendingPreset(p);
    router.push("/playground");
  };

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-12">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">
            <Globe className="h-3.5 w-3.5" /> 에이전트 마켓
          </span>
          <h1 className="mt-3 text-3xl font-bold tracking-tight">다른 사람이 만든 에이전트를 내 구조에 붙입니다</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            공개된 에이전트를 골라 플레이그라운드에 Sub-agent 로 넣거나, 내 프리셋으로 복제해 고쳐 씁니다. 공개 갤러리에는 직접 작성한 코드가 없는 에이전트만 올라옵니다.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 text-xs text-muted">
          <span className="flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-success" /> 배지는 내 브라우저에서 직접 검사한 결과입니다
          </span>
          <Link href="/playground" className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 font-medium text-fg hover:bg-surface-2">
            <Upload className="h-3.5 w-3.5" /> 내 에이전트 올리기
          </Link>
        </div>
      </div>

      {!SUPABASE_ENABLED ? (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">이 배포에는 로그인 기능이 설정되어 있지 않아 마켓을 쓸 수 없습니다.</p>
      ) : (
        <>
          {sharedError && <p className="mb-4 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning">{sharedError}</p>}
          <MarketGrid onOpen={setOpen} />
          <p className="mt-10 text-center text-xs text-muted">
            올리는 방법: 플레이그라운드 → 프리셋 → 내 에이전트에서 공개 범위를 &lsquo;공개&rsquo;로 바꿉니다. {!user && <SignInButton />}
          </p>
        </>
      )}

      {open && (
        <PresetDetail
          preset={open}
          onClose={() => {
            setOpen(null);
            if (sharedId) router.replace("/agents");
          }}
          onUse={use}
          onFork={
            user
              ? async (p) => {
                  await usePresets.getState().fork(p);
                }
              : undefined
          }
        />
      )}
    </main>
  );
}
