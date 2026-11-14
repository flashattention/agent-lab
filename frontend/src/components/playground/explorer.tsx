"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronRight, FileCode2, FileJson, FileText, Folder, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";

type Tree = { [name: string]: Tree | string };

function buildTree(paths: string[]): Tree {
  const root: Tree = {};
  for (const p of paths) {
    const parts = p.split("/");
    let cur = root;
    parts.forEach((part, i) => {
      if (i === parts.length - 1) cur[part] = p;
      else cur = (cur[part] ??= {}) as Tree;
    });
  }
  return root;
}

const fileIcon = (name: string) =>
  name.endsWith(".py") ? (
    <FileCode2 className="h-3.5 w-3.5 text-sky-500" />
  ) : name.endsWith(".json") ? (
    <FileJson className="h-3.5 w-3.5 text-amber-500" />
  ) : (
    <FileText className="h-3.5 w-3.5 text-muted" />
  );

/** 그래프가 바뀔 때 새로 생기거나 내용이 바뀐 파일을 잠깐 강조한다. */
function useChangedFiles(files: Record<string, string>) {
  const [prev, setPrev] = useState(files);
  const [flash, setFlash] = useState<Record<string, "new" | "changed">>({});
  // 파일 목록이 바뀐 렌더에서 바로 차이를 계산한다 (렌더 중 상태 조정)
  if (prev !== files) {
    const f: Record<string, "new" | "changed"> = {};
    for (const [k, v] of Object.entries(files)) {
      if (!(k in prev)) f[k] = "new";
      else if (prev[k] !== v) f[k] = "changed";
    }
    setPrev(files);
    if (Object.keys(f).length) setFlash(f);
  }
  useEffect(() => {
    if (!Object.keys(flash).length) return;
    const t = setTimeout(() => setFlash({}), 1800);
    return () => clearTimeout(t);
  }, [flash]);
  return flash;
}

export function Explorer({
  files,
  active,
  modified,
  onOpen,
  title,
  badge,
}: {
  files: Record<string, string>;
  active: string;
  modified: Set<string>;
  onOpen: (path: string) => void;
  title: string;
  badge?: React.ReactNode;
}) {
  const tree = useMemo(() => buildTree(Object.keys(files).sort()), [files]);
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const flash = useChangedFiles(files);

  const render = (t: Tree, prefix: string, depth: number): React.ReactNode =>
    Object.entries(t)
      .sort(([a, av], [b, bv]) => (typeof av === "string" ? 1 : 0) - (typeof bv === "string" ? 1 : 0) || a.localeCompare(b))
      .map(([name, v]) => {
        const path = prefix ? `${prefix}/${name}` : name;
        const pad = { paddingLeft: 8 + depth * 12 };
        if (typeof v === "string") {
          return (
            <button
              key={path}
              onClick={() => onOpen(v)}
              style={pad}
              className={cn(
                "flex w-full items-center gap-1.5 py-[3px] pr-2 text-left text-[12.5px] transition-colors",
                active === v ? "bg-accent-soft text-fg" : "text-fg-2 hover:bg-surface-2",
                flash[v] === "new" && "bg-success/15",
                flash[v] === "changed" && "bg-accent/10",
              )}
            >
              <span className="w-3" />
              {fileIcon(name)}
              <span className="truncate">{name}</span>
              {flash[v] === "new" && <span className="ml-auto text-[9px] font-bold text-success">NEW</span>}
              {modified.has(v) && <span className="ml-auto text-[10px] font-bold text-warning">M</span>}
            </button>
          );
        }
        const open = !closed[path];
        return (
          <div key={path}>
            <button
              onClick={() => setClosed((c) => ({ ...c, [path]: open }))}
              style={pad}
              className="flex w-full items-center gap-1.5 py-[3px] pr-2 text-left text-[12.5px] text-fg-2 hover:bg-surface-2"
            >
              <ChevronRight className={cn("h-3 w-3 text-muted transition", open && "rotate-90")} />
              {open ? <FolderOpen className="h-3.5 w-3.5 text-accent" /> : <Folder className="h-3.5 w-3.5 text-accent" />}
              <span className="truncate">{name}</span>
            </button>
            {open && render(v, path, depth + 1)}
          </div>
        );
      });

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3">
        <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">{title}</span>
        <span className="ml-auto">{badge}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto py-1">
        {Object.keys(files).length ? render(tree, "", 0) : <p className="p-4 text-xs text-muted">노드를 배치하면 파일이 생성됩니다.</p>}
      </div>
    </div>
  );
}
