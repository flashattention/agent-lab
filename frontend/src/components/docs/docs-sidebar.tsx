"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import { ChevronDown, Search } from "lucide-react";
import type { DocCategory, DocMeta } from "@/lib/content";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";

export type SearchDoc = DocMeta & { categoryTitle: string; headings: string[]; text: string };

export function DocsSearch({ search, autoFocus = false, large = false }: { search: SearchDoc[]; autoFocus?: boolean; large?: boolean }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const fuse = useMemo(
    () =>
      new Fuse(search, {
        keys: [
          { name: "title", weight: 3 },
          { name: "tags", weight: 2 },
          { name: "headings", weight: 1.5 },
          { name: "description", weight: 1 },
          { name: "text", weight: 0.4 },
        ],
        threshold: 0.35,
        ignoreLocation: true,
      }),
    [search],
  );
  const results = q.trim() ? fuse.search(q).slice(0, 10).map((r) => r.item) : [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (d: SearchDoc) => {
    router.push(`/docs/${d.category}/${d.slug}`);
    setQ("");
  };

  return (
    <div className="relative">
      <Search className={cn("absolute top-1/2 left-3 -translate-y-1/2 text-muted", large ? "h-5 w-5" : "h-4 w-4")} />
      <input
        ref={input}
        autoFocus={autoFocus}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setSel(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, results.length - 1));
          if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
          if (e.key === "Enter" && results[sel]) go(results[sel]);
          if (e.key === "Escape") setQ("");
        }}
        placeholder="API, 클래스, 개념 검색…"
        className={cn(
          "w-full rounded-xl border border-border bg-surface outline-none focus:border-accent",
          large ? "py-3.5 pr-4 pl-11 text-base shadow-soft" : "py-2 pr-12 pl-9 text-sm",
        )}
      />
      {!large && (
        <kbd className="absolute top-1/2 right-2.5 -translate-y-1/2 rounded border border-border px-1.5 font-mono text-[10px] text-muted">
          ⌘K
        </kbd>
      )}
      {results.length > 0 && (
        <div className="fade-in absolute inset-x-0 top-full z-40 mt-1.5 max-h-96 overflow-y-auto rounded-xl border border-border bg-surface p-1.5 shadow-soft">
          {results.map((d, i) => (
            <button
              key={`${d.category}/${d.slug}`}
              onMouseEnter={() => setSel(i)}
              onClick={() => go(d)}
              className={cn("block w-full rounded-lg px-3 py-2 text-left", i === sel ? "bg-surface-2" : "")}
            >
              <span className="block text-sm font-medium">{d.title}</span>
              <span className="block truncate text-xs text-muted">
                {d.categoryTitle} · {d.description}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function DocsSidebar({ index, search }: { index: DocCategory[]; search: SearchDoc[] }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  return (
    <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-72 shrink-0 flex-col border-r border-border bg-surface/50 lg:flex">
      <div className="border-b border-border p-3">
        <DocsSearch search={search} />
      </div>
      <nav className="flex-1 overflow-y-auto p-3">
        {index.map((c) => (
          <div key={c.slug} className="mb-3">
            <button
              onClick={() => setCollapsed((s) => ({ ...s, [c.slug]: !s[c.slug] }))}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] font-semibold"
            >
              <Icon name={c.icon} className="h-4 w-4 text-accent" />
              {c.title}
              <ChevronDown className={cn("ml-auto h-3.5 w-3.5 text-muted transition", collapsed[c.slug] && "-rotate-90")} />
            </button>
            {!collapsed[c.slug] && (
              <div className="mt-0.5 ml-4 border-l border-border pl-2">
                {c.docs.map((d) => {
                  const href = `/docs/${c.slug}/${d.slug}`;
                  return (
                    <Link
                      key={d.slug}
                      href={href}
                      className={cn(
                        "block truncate rounded-md px-2 py-1 text-[13px]",
                        pathname === href ? "bg-accent-soft font-medium text-accent" : "text-muted hover:text-fg",
                      )}
                    >
                      {d.title}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}
