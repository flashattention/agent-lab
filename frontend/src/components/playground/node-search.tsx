"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import { KINDS } from "@/lib/playground/catalog";
import { walkGraphs } from "@/lib/playground/subgraph";
import type { Graph } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";

type Hit = { id: string; path: string[]; trail: string[]; name: string; kind: keyof typeof KINDS; text: string };

/** Ctrl/⌘+K: 모든 서브그래프를 포함한 전체 트리에서 노드를 찾아 이동한다. */
type Props = { open: boolean; onClose: () => void; graph: Graph; onPick: (path: string[], id: string) => void };

export function NodeSearch(props: Props) {
  // 열 때마다 새로 마운트해 검색어/선택을 초기화한다
  return props.open ? <SearchBody {...props} /> : null;
}

function SearchBody({ onClose, graph, onPick }: Props) {
  const [q, setQ] = useState("");
  const [cur, setCur] = useState(0);

  const all = useMemo(() => {
    const out: Hit[] = [];
    const names = new Map<string, string>();
    walkGraphs(graph, (lv, path, owner) => {
      if (owner) names.set(owner.id, owner.data.name);
      for (const n of lv.nodes) {
        if (n.kind === "start" || n.kind === "end") continue;
        out.push({
          id: n.id,
          path,
          trail: path.map((id) => names.get(id) ?? id),
          name: n.data.name,
          kind: n.kind,
          text: [n.data.name, KINDS[n.kind].label, n.data.description ?? "", n.data.prompt ?? "", (n.data.tools ?? []).join(" ")].join(" ").toLowerCase(),
        });
      }
    });
    return out;
  }, [graph]);

  const list = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const hits = words.length ? all.filter((h) => words.every((w) => h.text.includes(w))) : all;
    // 이름이 먼저 맞는 노드를 위로
    return hits.sort((a, b) => Number(!a.name.toLowerCase().startsWith(words[0] ?? "")) - Number(!b.name.toLowerCase().startsWith(words[0] ?? ""))).slice(0, 50);
  }, [q, all]);


  return (
    <div className="fixed inset-0 z-50 flex justify-center bg-black/30 p-4 pt-[12vh] backdrop-blur-[2px]" onClick={onClose}>
      <div role="dialog" className="fade-in flex h-fit max-h-[70vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="h-4 w-4 text-muted" />
          <input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setCur(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") {
                e.preventDefault();
                setCur((c) => Math.min(list.length - 1, c + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setCur((c) => Math.max(0, c - 1));
              } else if (e.key === "Enter" && list[cur]) onPick(list[cur].path, list[cur].id);
            }}
            placeholder="노드 이름, 종류, 프롬프트, 도구로 찾기 (서브 에이전트 안까지)"
            className="h-12 flex-1 bg-transparent text-sm outline-none"
          />
          <kbd className="rounded border border-border px-1.5 text-[10px] text-muted">Esc</kbd>
        </div>
        <div className="min-h-0 overflow-y-auto py-1">
          {list.length === 0 && <p className="px-4 py-6 text-center text-sm text-muted">찾는 노드가 없습니다.</p>}
          {list.map((h, i) => (
            <button
              key={`${h.path.join("/")}/${h.id}`}
              onMouseEnter={() => setCur(i)}
              onClick={() => onPick(h.path, h.id)}
              className={cn("flex w-full items-center gap-2.5 px-4 py-2 text-left", i === cur && "bg-accent-soft")}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-white" style={{ background: KINDS[h.kind].color }}>
                <Icon name={KINDS[h.kind].icon} className="h-3 w-3" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[13px]">{h.name}</span>
                <span className="flex items-center gap-0.5 truncate text-[11px] text-muted">
                  agent
                  {h.trail.map((t, k) => (
                    <span key={k} className="flex items-center gap-0.5">
                      <ChevronRight className="h-3 w-3" />
                      {t}
                    </span>
                  ))}
                  <span className="ml-1.5">· {KINDS[h.kind].label}</span>
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
