"use client";

import { useState } from "react";
import { Info, Settings2, Shapes, SlidersHorizontal, Trash2 } from "lucide-react";
import { KINDS, PALETTE_ORDER, TOOL_LIBRARY } from "@/lib/playground/catalog";
import type { NodeKind, RouterStrategy } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import { usePlayground } from "./store";

const field = "w-full rounded-lg border border-border bg-bg px-2.5 py-1.5 text-[13px] outline-none focus:border-accent";
const labelCls = "mb-1 block text-[11px] font-semibold tracking-wide text-muted uppercase";

function Palette({ onAdd }: { onAdd: (k: NodeKind) => void }) {
  const groups = PALETTE_ORDER.reduce<Record<string, NodeKind[]>>((acc, k) => {
    (acc[KINDS[k].category] ??= []).push(k);
    return acc;
  }, {});
  return (
    <div className="space-y-5 p-3">
      <p className="rounded-lg bg-surface-2 px-3 py-2 text-[11.5px] leading-relaxed text-muted">
        끌어서 캔버스에 놓거나 클릭해 추가하세요. 노드의 아래 점 → 다른 노드의 위 점으로 드래그하면 연결됩니다.
      </p>
      {Object.entries(groups).map(([cat, kinds]) => (
        <div key={cat}>
          <div className="mb-2 px-1 text-[11px] font-semibold tracking-wide text-muted uppercase">{cat}</div>
          <div className="grid grid-cols-1 gap-1.5">
            {kinds.map((k) => {
              const info = KINDS[k];
              return (
                <button
                  key={k}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData("application/agentlab-node", k);
                    e.dataTransfer.effectAllowed = "move";
                  }}
                  onClick={() => onAdd(k)}
                  title={info.description}
                  className="group flex cursor-grab items-center gap-2.5 rounded-xl border border-border bg-surface px-2.5 py-2 text-left transition hover:border-accent/60 hover:shadow-soft active:cursor-grabbing"
                >
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-white" style={{ background: info.color }}>
                    <Icon name={info.icon} className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium">{info.label}</span>
                    <span className="block truncate font-mono text-[10.5px] text-muted">{info.api}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function Inspector() {
  const { nodes, selectedId, updateNode, removeNode, edges } = usePlayground();
  const node = nodes.find((n) => n.id === selectedId);
  if (!node)
    return (
      <div className="grid h-40 place-items-center px-6 text-center text-xs text-muted">캔버스에서 노드를 선택하면 속성을 편집할 수 있습니다.</div>
    );
  const d = node.data;
  const info = KINDS[d.kind];
  const set = (patch: Partial<typeof d>) => updateNode(node.id, patch);
  const toggleTool = (t: string) => set({ tools: d.tools?.includes(t) ? d.tools.filter((x) => x !== t) : [...(d.tools ?? []), t] });
  const outs = edges.filter((e) => e.source === node.id).map((e) => nodes.find((n) => n.id === e.target)?.data.name);

  return (
    <div className="space-y-4 p-3">
      <div className="flex items-start gap-2.5">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-white" style={{ background: info.color }}>
          <Icon name={info.icon} className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{info.label}</div>
          <div className="font-mono text-[11px] text-muted">{info.api}</div>
        </div>
        <button onClick={() => removeNode(node.id)} className="rounded-lg p-1.5 text-muted hover:bg-danger/10 hover:text-danger" title="삭제 (Delete)">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      <p className="flex gap-1.5 rounded-lg bg-surface-2 px-2.5 py-2 text-[11.5px] leading-relaxed text-muted">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {info.description}
      </p>

      {d.kind !== "start" && d.kind !== "end" && (
        <div>
          <label className={labelCls}>이름 (Python 식별자)</label>
          <input className={cn(field, "font-mono")} value={d.name} onChange={(e) => set({ name: e.target.value.replace(/\s/g, "_") })} />
        </div>
      )}

      {d.kind === "router" && (
        <div>
          <label className={labelCls}>라우팅 전략</label>
          <select className={field} value={d.strategy ?? "llm"} onChange={(e) => set({ strategy: e.target.value as RouterStrategy })}>
            <option value="llm">LLM 구조화 출력으로 선택</option>
            <option value="tools_condition">tools_condition (도구 호출 여부)</option>
            <option value="state_key">State 키 값으로 선택</option>
          </select>
          {d.strategy === "state_key" && (
            <input className={cn(field, "mt-2 font-mono")} placeholder="state 키 (예: category)" value={d.stateKey ?? ""} onChange={(e) => set({ stateKey: e.target.value })} />
          )}
          <p className="mt-1.5 text-[11px] text-muted">경로: {outs.length ? outs.map((o) => o ?? "END").join(" · ") : "연결된 경로 없음"}</p>
        </div>
      )}

      {["llm", "agent", "router", "evaluator", "supervisor", "reduce", "human"].includes(d.kind) && !(d.kind === "router" && d.strategy !== "llm") && (
        <div>
          <label className={labelCls}>{d.kind === "evaluator" ? "평가 기준" : d.kind === "human" ? "사람에게 보낼 질문" : "시스템 프롬프트"}</label>
          <textarea className={cn(field, "min-h-24 resize-y leading-relaxed")} value={d.prompt ?? ""} onChange={(e) => set({ prompt: e.target.value })} />
        </div>
      )}

      {["agent", "llm"].includes(d.kind) && (
        <div>
          <label className={labelCls}>역할 설명 (Supervisor/라우터가 참고)</label>
          <input className={field} value={d.description ?? ""} onChange={(e) => set({ description: e.target.value })} />
        </div>
      )}

      {(d.kind === "tools" || d.kind === "agent") && (
        <div>
          <label className={labelCls}>도구</label>
          <div className="space-y-1">
            {Object.values(TOOL_LIBRARY).map((t) => (
              <label key={t.name} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2">
                <input type="checkbox" checked={d.tools?.includes(t.name) ?? false} onChange={() => toggleTool(t.name)} className="accent-[var(--accent)]" />
                <span className="font-mono text-[12px]">{t.name}</span>
                <span className={cn("ml-auto text-[11px]", t.sensitive ? "text-danger" : "text-muted")}>{t.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {(d.kind === "evaluator" || d.kind === "supervisor") && (
        <div>
          <label className={labelCls}>{d.kind === "supervisor" ? "최대 위임 횟수" : "최대 반복 횟수"}</label>
          <input type="number" min={1} max={20} className={field} value={d.maxIterations ?? 3} onChange={(e) => set({ maxIterations: Number(e.target.value) })} />
        </div>
      )}
      {d.kind === "retriever" && (
        <div>
          <label className={labelCls}>top-k</label>
          <input type="number" min={1} max={10} className={field} value={d.k ?? 3} onChange={(e) => set({ k: Number(e.target.value) })} />
        </div>
      )}
      {d.kind === "map" && (
        <div>
          <label className={labelCls}>최대 분기 수</label>
          <input type="number" min={1} max={10} className={field} value={d.maxItems ?? 4} onChange={(e) => set({ maxItems: Number(e.target.value) })} />
        </div>
      )}
      {d.kind === "function" && (
        <div>
          <label className={labelCls}>함수 본문 (state → dict)</label>
          <textarea
            spellCheck={false}
            className={cn(field, "min-h-40 resize-y font-mono text-[12px] leading-relaxed")}
            value={d.code ?? ""}
            onChange={(e) => set({ code: e.target.value })}
          />
        </div>
      )}
    </div>
  );
}

function GraphSettingsPanel() {
  const { settings, setSettings } = usePlayground();
  return (
    <div className="space-y-4 p-3">
      <div>
        <label className={labelCls}>Checkpointer</label>
        <select className={field} value={settings.checkpointer} onChange={(e) => setSettings({ checkpointer: e.target.value as typeof settings.checkpointer })}>
          <option value="none">없음</option>
          <option value="memory">InMemorySaver (개발용)</option>
          <option value="sqlite">SqliteSaver (파일 영속)</option>
        </select>
        <p className="mt-1 text-[11px] text-muted">대화 메모리·HITL·장애 복구에 필요. 운영에서는 PostgresSaver 권장.</p>
      </div>
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={settings.store} onChange={(e) => setSettings({ store: e.target.checked })} className="accent-[var(--accent)]" />
        장기 메모리 Store (InMemoryStore)
      </label>
      <div>
        <label className={labelCls}>recursion_limit</label>
        <input type="number" min={5} max={200} className={field} value={settings.recursionLimit} onChange={(e) => setSettings({ recursionLimit: Number(e.target.value) })} />
      </div>
      <div>
        <label className={labelCls}>데모 입력 (main.py)</label>
        <textarea className={cn(field, "min-h-20 resize-y")} value={settings.demoInput} onChange={(e) => setSettings({ demoInput: e.target.value })} />
      </div>
    </div>
  );
}

export function RightPanel({ onAdd }: { onAdd: (k: NodeKind) => void }) {
  const selectedId = usePlayground((s) => s.selectedId);
  const [tab, setTab] = useState<"palette" | "props" | "graph">("palette");
  const active = selectedId && tab === "palette" ? "props" : tab;
  const tabs = [
    { id: "palette", label: "컴포넌트", icon: Shapes },
    { id: "props", label: "속성", icon: SlidersHorizontal },
    { id: "graph", label: "그래프", icon: Settings2 },
  ] as const;
  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex h-10 shrink-0 border-b border-border">
        {tabs.map(({ id, label, icon: I }) => (
          <button
            key={id}
            onClick={() => {
              setTab(id);
              if (id === "palette") usePlayground.getState().select(null);
            }}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 border-b-2 text-xs font-medium transition-colors",
              active === id ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
            )}
          >
            <I className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {active === "palette" ? <Palette onAdd={onAdd} /> : active === "props" ? <Inspector /> : <GraphSettingsPanel />}
      </div>
    </div>
  );
}
