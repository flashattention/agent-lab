"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

// rehype-slug 와 같은 규칙(github-slugger 단순화)으로 id 를 만든다
const slug = (s: string) =>
  s
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/g, "-");

export function DocToc({ headings }: { headings: { depth: number; text: string }[] }) {
  const [active, setActive] = useState("");
  useEffect(() => {
    const els = headings.map((h) => document.getElementById(slug(h.text))).filter(Boolean) as HTMLElement[];
    const obs = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting);
        if (vis[0]) setActive(vis[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px" },
    );
    els.forEach((e) => obs.observe(e));
    return () => obs.disconnect();
  }, [headings]);

  if (headings.length < 2) return null;
  return (
    <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-56 shrink-0 overflow-y-auto py-10 pr-4 xl:block">
      <div className="mb-2 text-xs font-semibold text-muted">이 페이지</div>
      {headings.map((h, i) => (
        <a
          key={i}
          href={`#${slug(h.text)}`}
          className={cn(
            "block truncate py-1 text-[12.5px] transition-colors",
            h.depth === 3 && "pl-3",
            active === slug(h.text) ? "text-accent" : "text-muted hover:text-fg",
          )}
        >
          {h.text}
        </a>
      ))}
    </aside>
  );
}
