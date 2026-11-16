"use client";

import { useMemo, useRef, useState } from "react";
import { Boxes, Cloud, Download, FileUp, HardDrive, Loader2, Package, Plus, Search, Trash2, X } from "lucide-react";
import { checkSub, PRESET_FORMAT } from "@/lib/playground/graph-file";
import { BUILTIN_PRESETS, usePresets, type AgentPreset } from "@/lib/presets";
import { allNodes, summarize, pyIdent } from "@/lib/playground/subgraph";
import type { SubGraph } from "@/lib/playground/types";
import { useAuth } from "@/lib/auth";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import { GraphThumb } from "@/components/projects/graph-thumb";
import { arrangedSub, usePlayground } from "./store";
import { usePlaygroundUI, type SaveDraft } from "./ui-store";

const field = "w-full rounded-lg border border-border bg-bg px-2.5 py-1.5 text-[13px] outline-none focus:border-accent";
const labelCls = "mb-1 block text-[11px] font-semibold tracking-wide text-muted uppercase";

/** 그래프가 쓰는 커스텀 도구 정의를 현재 그래프 설정에서 찾아 함께 담는다 */
export function withUsedTools(g: SubGraph): SubGraph {
  const used = new Set(allNodes(g).flatMap((n) => n.data.tools ?? []));
  const tools = (usePlayground.getState().settings.customTools ?? []).filter((t) => used.has(t.name));
  return { nodes: g.nodes, edges: g.edges, ...(tools.length ? { tools } : {}) };
}

export function SourceBadge({ source }: { source: AgentPreset["source"] }) {
  const map = {
    cloud: { icon: Cloud, text: "계정", cls: "bg-accent-soft text-accent" },
    local: { icon: HardDrive, text: "이 브라우저", cls: "bg-surface-2 text-fg-2" },
    builtin: { icon: Package, text: "기본 제공", cls: "bg-success/10 text-success" },
  }[source];
  const I = map.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold", map.cls)}>
      <I className="h-3 w-3" /> {map.text}
    </span>
  );
}

/** 프리셋이 노드에 연결된 뒤 수정되었는지 */
export function presetOutdated(link: { id: string; updatedAt?: string } | undefined, p: AgentPreset | undefined) {
  return !!link && !!p && p.source !== "builtin" && !!p.updated_at && link.updatedAt !== p.updated_at;
}

/* ------------------------------------------------------------------ 라이브러리 */

export function PresetsDialog({ onInsert }: { onInsert: (p: AgentPreset) => void }) {
  const open = usePlaygroundUI((x) => x.libraryOpen);
  return open ? <Library onInsert={onInsert} /> : null;
}

function Library({ onInsert }: { onInsert: (p: AgentPreset) => void }) {
  const setOpen = usePlaygroundUI((x) => x.setLibraryOpen);
  const setNotice = usePlaygroundUI((x) => x.setNotice);
  const { items, loading, error, remove, save } = usePresets();
  // 저장한 프리셋이 없으면 기본 제공 탭부터 보여 준다
  const [tab, setTab] = useState<"mine" | "builtin">(() => (usePresets.getState().items.length ? "mine" : "builtin"));
  const fileRef = useRef<HTMLInputElement>(null);
  const exportPreset = (p: AgentPreset) => {
    const body = { format: PRESET_FORMAT, version: 1, preset: { name: p.name, node_name: p.node_name, description: p.description, graph: p.graph } };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
    a.download = `${p.node_name}.agentlab-preset.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const importPresets = async (files: FileList) => {
    let n = 0;
    for (const f of Array.from(files)) {
      try {
        const raw = JSON.parse(await f.text());
        const list = raw?.format === PRESET_FORMAT ? [raw.preset] : Array.isArray(raw?.presets) ? raw.presets : [];
        if (!list.length) throw new Error("에이전트 프리셋 파일이 아닙니다.");
        for (const p of list) {
          await save({ name: String(p.name ?? f.name), node_name: String(p.node_name ?? "sub_agent"), description: String(p.description ?? ""), graph: checkSub(p.graph) });
          n++;
        }
      } catch (e) {
        setNotice({ kind: "error", text: `${f.name}: ${(e as Error).message}` });
        return;
      }
    }
    setTab("mine");
    setNotice({ kind: "ok", text: `프리셋 ${n}개를 가져왔습니다.` });
  };
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const base = tab === "mine" ? items : BUILTIN_PRESETS;
    const k = q.trim().toLowerCase();
    return k ? base.filter((p) => [p.name, p.node_name, p.description].some((x) => x.toLowerCase().includes(k))) : base;
  }, [tab, items, q]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={() => setOpen(false)}>
      <div className="fade-in flex max-h-[88vh] w-full max-w-5xl flex-col rounded-2xl border border-border bg-surface shadow-soft" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Boxes className="h-5 w-5 text-accent" /> 에이전트 프리셋
            </h2>
            <p className="text-xs text-muted">저장해 둔 에이전트를 지금 보고 있는 그래프에 Sub-agent 노드로 넣습니다. 넣은 뒤에는 더블클릭해 내부를 고칠 수 있습니다.</p>
          </div>
          <button onClick={() => setOpen(false)} className="ml-auto rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-6 py-2.5">
          {(
            [
              ["mine", `내 에이전트 ${items.length}`],
              ["builtin", `기본 제공 ${BUILTIN_PRESETS.length}`],
            ] as const
          ).map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} className={cn("rounded-full px-3 py-1 text-xs", tab === id ? "bg-accent text-accent-fg" : "text-muted hover:bg-surface-2")}>
              {label}
            </button>
          ))}
          <button onClick={() => fileRef.current?.click()} className="ml-auto flex items-center gap-1 rounded-full px-3 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg" title="팀원이 보낸 .agentlab-preset.json 가져오기">
            <FileUp className="h-3.5 w-3.5" /> 가져오기
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files?.length) importPresets(e.target.files);
              e.target.value = "";
            }}
          />
          <div className="relative w-full sm:w-64">
            <Search className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름·설명 검색" className={cn(field, "pl-8")} />
          </div>
        </div>
        {error && <div className="border-b border-warning/30 bg-warning/10 px-6 py-1.5 text-xs text-warning">{error}</div>}
        <div className="grid min-h-0 flex-1 auto-rows-max gap-4 overflow-y-auto p-6 sm:grid-cols-2 lg:grid-cols-3">
          {loading && (
            <div className="col-span-full flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" /> 불러오는 중…
            </div>
          )}
          {!loading && list.length === 0 && (
            <div className="col-span-full rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
              {tab === "mine" ? (
                <>
                  아직 저장한 에이전트가 없습니다.
                  <br />
                  캔버스 위쪽의 <b className="text-fg">에이전트로 저장</b>을 누르거나, Sub-agent·Agent 노드의 속성 패널에서 <b className="text-fg">프리셋으로 저장</b>하세요.
                </>
              ) : (
                "검색 결과가 없습니다."
              )}
            </div>
          )}
          {list.map((p) => {
            const sum = summarize(p.graph);
            return (
              <div key={p.id} className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-bg transition hover:border-accent hover:shadow-soft">
                <button onClick={() => onInsert(p)} className="bg-grid h-32 border-b border-border p-3" title="Sub-agent 로 추가">
                  <GraphThumb graph={arrangedSub(p.graph)} className="h-full w-full" />
                </button>
                <div className="flex flex-1 flex-col p-4">
                  <div className="mb-1 flex items-center gap-2">
                    <SourceBadge source={p.source} />
                    {p.category && <span className="text-[11px] text-muted">{p.category}</span>}
                    {p.updated_at && <span className="ml-auto text-[10.5px] text-muted">{new Date(p.updated_at).toLocaleDateString()}</span>}
                  </div>
                  <div className="font-semibold">{p.name}</div>
                  <div className="font-mono text-[11px] text-muted">{p.node_name}</div>
                  <p className="mt-1 line-clamp-3 text-[12.5px] leading-relaxed text-muted">{p.description || "설명 없음"}</p>
                  <p className="mt-2 text-[11px] text-fg-2">
                    노드 {sum.count}개{sum.nested ? ` · 서브 ${sum.nested}` : ""}
                    {sum.tools.length ? ` · ${sum.tools.slice(0, 3).join(", ")}${sum.tools.length > 3 ? "…" : ""}` : ""}
                  </p>
                  <div className="mt-auto flex items-center gap-1.5 pt-3">
                    <button onClick={() => onInsert(p)} className="mr-auto flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
                      <Plus className="h-3.5 w-3.5" /> Sub-agent 로 추가
                    </button>
                    <button onClick={() => exportPreset(p)} className={cn("rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg", p.source === "builtin" && "ml-auto")} title="JSON 으로 내보내기 (팀원과 공유)">
                      <Download className="h-3.5 w-3.5" />
                    </button>
                    {p.source !== "builtin" && (
                      <button
                        onClick={async () => {
                          if (!confirm(`'${p.name}' 프리셋을 삭제할까요? 이미 그래프에 넣은 Sub-agent 는 그대로 남습니다.`)) return;
                          try {
                            await remove(p);
                          } catch (e) {
                            setNotice({ kind: "error", text: (e as Error).message });
                          }
                        }}
                        className="rounded-lg p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                        title="삭제"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 저장 */

export function SavePresetDialog() {
  const draft = usePlaygroundUI((x) => x.saveDraft);
  // 대화상자를 열 때마다 새로 마운트해 입력값을 draft 로 초기화한다
  return draft ? <SaveForm key={JSON.stringify([draft.name, draft.linkNodeId, draft.overwriteId])} draft={draft} /> : null;
}

function SaveForm({ draft }: { draft: SaveDraft }) {
  const close = () => usePlaygroundUI.getState().openSave(null);
  const setNotice = usePlaygroundUI((x) => x.setNotice);
  const { items, save, error } = usePresets();
  const user = useAuth((x) => x.user);
  const target = draft.overwriteId ? items.find((p) => p.id === draft.overwriteId) : undefined;
  const [name, setName] = useState(target?.name ?? draft.name);
  const [nodeName, setNodeName] = useState(draft.node_name);
  const [desc, setDesc] = useState(draft.description);
  const [mode, setMode] = useState<"new" | "overwrite">(target ? "overwrite" : "new");
  const [busy, setBusy] = useState(false);
  const sum = summarize(draft.graph);
  const where = SUPABASE_ENABLED && user && !error && target?.source !== "local" ? "계정에 저장되어 어느 기기에서나 불러올 수 있습니다." : "이 브라우저에 저장됩니다. 로그인하면 계정에 저장됩니다.";

  const submit = async () => {
    setBusy(true);
    try {
      const made = await save({ name, node_name: nodeName, description: desc, graph: withUsedTools(draft.graph) }, mode === "overwrite" ? target?.id : undefined);
      if (draft.linkNodeId) usePlayground.getState().updateNode(draft.linkNodeId, { preset: { id: made.id, name: made.name, updatedAt: made.updated_at } });
      setNotice({ kind: "ok", text: `'${made.name}' 프리셋을 ${mode === "overwrite" ? "덮어썼습니다" : "저장했습니다"}. 다른 그래프에서 프리셋 목록으로 불러올 수 있습니다.` });
      close();
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={close}>
      <div className="fade-in w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-soft" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center gap-2">
          <Boxes className="h-5 w-5 text-accent" />
          <h2 className="font-semibold">에이전트 프리셋으로 저장</h2>
          <button onClick={close} className="ml-auto rounded-lg p-1 text-muted hover:bg-surface-2">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mb-4 flex gap-3 rounded-xl border border-border bg-bg p-2">
          <GraphThumb graph={draft.graph} className="h-16 w-24 shrink-0 rounded-lg bg-surface-2 p-1.5" />
          <div className="min-w-0 text-[12px] text-muted">
            노드 {sum.count}개{sum.nested ? ` · 서브 ${sum.nested}` : ""}
            <div className="truncate font-mono text-[11px]">{sum.names.join(", ")}</div>
            {sum.tools.length > 0 && <div className="truncate">도구: {sum.tools.join(", ")}</div>}
          </div>
        </div>
        {target && (
          <div className="mb-3 grid grid-cols-2 gap-1.5 text-xs">
            {(
              [
                ["overwrite", `'${target.name}' 덮어쓰기`],
                ["new", "새 프리셋으로"],
              ] as const
            ).map(([id, label]) => (
              <button key={id} onClick={() => setMode(id)} className={cn("truncate rounded-lg border px-2 py-1.5", mode === id ? "border-accent bg-accent-soft text-accent" : "border-border text-muted")}>
                {label}
              </button>
            ))}
          </div>
        )}
        <div className="space-y-3">
          <div>
            <label className={labelCls}>프리셋 이름</label>
            <input autoFocus className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="예: 웹 리서처" />
          </div>
          <div>
            <label className={labelCls}>기본 노드 이름 (Python 식별자)</label>
            <input className={cn(field, "font-mono")} value={nodeName} onChange={(e) => setNodeName(e.target.value.replace(/\s/g, "_"))} />
            {pyIdent(nodeName) !== nodeName && <p className="mt-1 text-[11px] text-muted">저장 시 &apos;{pyIdent(nodeName)}&apos; 로 바뀝니다.</p>}
          </div>
          <div>
            <label className={labelCls}>역할 설명 (Supervisor 가 참고)</label>
            <textarea className={cn(field, "min-h-20 resize-y")} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="이 에이전트가 맡는 일과 잘하는 것" />
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted">{where}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={close} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-surface-2">
            취소
          </button>
          <button onClick={submit} disabled={busy || !name.trim()} className="flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-accent-fg disabled:opacity-40">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} 저장
          </button>
        </div>
      </div>
    </div>
  );
}
