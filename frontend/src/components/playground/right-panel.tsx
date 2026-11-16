"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Activity, Boxes, ChevronDown, Info, Library, Link2, Loader2, Maximize2, Plus, RefreshCw, Save, Settings2, Shapes, SlidersHorizontal, Trash2, Unlink, Ungroup, Wrench } from "lucide-react";
import { CUSTOM_TOOL_TEMPLATE, KINDS, MODEL_KINDS, MODEL_SUGGESTIONS, PALETTE_ORDER, toolCatalog } from "@/lib/playground/catalog";
import type { CustomTool, NodeKind, RouterStrategy, SubgraphIO, SubgraphMemory } from "@/lib/playground/types";
import { summarize, wrapNode } from "@/lib/playground/subgraph";
import { getSharedPreset, usePresets, type AgentPreset } from "@/lib/presets";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import { presetOutdated, SourceBadge } from "./presets-dialog";
import { usePlayground } from "./store";
import { usePlaygroundUI } from "./ui-store";

const field = "w-full rounded-lg border border-border bg-bg px-2.5 py-1.5 text-[13px] outline-none focus:border-accent";
const labelCls = "mb-1 block text-[11px] font-semibold tracking-wide text-muted uppercase";

function PresetPalette({ onAddPreset }: { onAddPreset: (p: AgentPreset) => void }) {
  const items = usePresets((x) => x.items);
  const setLibraryOpen = usePlaygroundUI((x) => x.setLibraryOpen);
  return (
    <div>
      <div className="mb-2 flex items-center px-1">
        <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">내 에이전트 프리셋</span>
        <button onClick={() => setLibraryOpen(true)} className="ml-auto flex items-center gap-1 text-[11px] font-medium text-accent hover:underline">
          <Library className="h-3 w-3" /> 전체 보기
        </button>
      </div>
      {items.length === 0 ? (
        <button onClick={() => setLibraryOpen(true)} className="w-full rounded-xl border border-dashed border-border px-3 py-2.5 text-left text-[11.5px] leading-relaxed text-muted hover:border-accent/60">
          만든 에이전트를 저장하면 여기에 나타납니다. 기본 제공 프리셋은 <b className="text-accent">전체 보기</b>에서 고를 수 있습니다.
        </button>
      ) : (
        <div className="grid grid-cols-1 gap-1.5">
          {items.slice(0, 8).map((p) => (
            <button
              key={p.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData("application/agentlab-preset", p.id);
                e.dataTransfer.effectAllowed = "move";
              }}
              onClick={() => onAddPreset(p)}
              title={p.description}
              className="flex cursor-grab items-center gap-2.5 rounded-xl border border-border bg-surface px-2.5 py-2 text-left transition hover:border-accent/60 hover:shadow-soft active:cursor-grabbing"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-white" style={{ background: KINDS.subgraph.color }}>
                <Boxes className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">{p.name}</span>
                <span className="block truncate font-mono text-[10.5px] text-muted">
                  {p.node_name} · 노드 {summarize(p.graph).count}
                </span>
              </span>
            </button>
          ))}
          {items.length > 8 && (
            <button onClick={() => setLibraryOpen(true)} className="text-[11px] text-muted hover:text-fg">
              +{items.length - 8}개 더 보기
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Palette({ onAdd, onAddPreset }: { onAdd: (k: NodeKind) => void; onAddPreset: (p: AgentPreset) => void }) {
  const groups = PALETTE_ORDER.reduce<Record<string, NodeKind[]>>((acc, k) => {
    (acc[KINDS[k].category] ??= []).push(k);
    return acc;
  }, {});
  return (
    <div className="space-y-5 p-3">
      <p className="rounded-lg bg-surface-2 px-3 py-2 text-[11.5px] leading-relaxed text-muted">
        끌어서 캔버스에 놓거나 클릭해 추가하세요. 노드의 아래 점 → 다른 노드의 위 점으로 드래그하면 연결됩니다.
      </p>
      <PresetPalette onAddPreset={onAddPreset} />
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
  const { nodes, selectedId, updateNode, removeNode, edges, settings, stack } = usePlayground();
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
  const openSave = usePlaygroundUI.getState().openSave;

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

      {MODEL_KINDS.has(d.kind) && !(d.kind === "router" && d.strategy !== "llm") && (
        <div>
          <label className={labelCls}>모델 (비우면 기본 모델)</label>
          <input
            list="node-models"
            className={cn(field, "font-mono")}
            placeholder="예: openai:gpt-5-mini"
            value={d.model ?? ""}
            onChange={(e) => set({ model: e.target.value.trim() || undefined })}
          />
          <datalist id="node-models">
            {MODEL_SUGGESTIONS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <p className="mt-1 text-[11px] text-muted">
            배포 시 <code className="font-mono break-all">LAB_MODEL__{stack.map((f) => `${f.name.toUpperCase()}__`).join("")}{d.name.toUpperCase()}</code> 환경 변수로 바꿀 수 있습니다.
          </p>
        </div>
      )}

      {d.kind === "subgraph" && <SubgraphInspector id={node.id} />}

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
            {Object.values(toolCatalog(settings)).map((t) => (
              <label key={t.name} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2">
                <input type="checkbox" checked={d.tools?.includes(t.name) ?? false} onChange={() => toggleTool(t.name)} className="accent-[var(--accent)]" />
                <span className="font-mono text-[12px]">{t.name}</span>
                <span className={cn("ml-auto text-[11px]", t.sensitive ? "text-danger" : "text-muted")}>{t.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {d.kind === "agent" && (
        <button
          onClick={() => {
            const { kind, ...data } = d;
            openSave({ graph: wrapNode({ id: node.id, kind, data, position: node.position }), name: d.name, node_name: d.name, description: d.description ?? "" });
          }}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2"
        >
          <Save className="h-3.5 w-3.5" /> 프리셋으로 저장
        </button>
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

function SubgraphInspector({ id }: { id: string }) {
  const node = usePlayground((s) => s.nodes.find((n) => n.id === id));
  const { updateNode, enter, ungroup, replaceSubgraph } = usePlayground.getState();
  const find = usePresets((x) => x.find);
  usePresets((x) => x.items); // 목록이 바뀌면 다시 그린다
  const setNotice = usePlaygroundUI((x) => x.setNotice);
  // 마켓에서 가져온 노드는 원본을 서버에서 확인한다 (업데이트 알림·다시 불러오기)
  const [remote, setRemote] = useState<{ id: string; p: AgentPreset | null } | null>(null);
  const marketId = node?.data.preset?.market ? node.data.preset.id : null;
  useEffect(() => {
    if (!marketId) return;
    let alive = true;
    getSharedPreset(marketId)
      .then((p) => alive && setRemote({ id: marketId, p }))
      .catch(() => alive && setRemote({ id: marketId, p: null }));
    return () => {
      alive = false;
    };
  }, [marketId]);
  if (!node) return null;
  const d = node.data;
  const sum = summarize(d.graph);
  const preset = d.preset ? (find(d.preset.id) ?? (remote?.id === d.preset.id ? (remote.p ?? undefined) : undefined)) : undefined;
  const outdated = presetOutdated(d.preset, preset);
  const btn = "flex items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-surface-2";

  return (
    <>
      <div>
        <label className={labelCls}>역할 설명 (Supervisor/라우터가 참고)</label>
        <textarea className={cn(field, "min-h-16 resize-y")} value={d.description ?? ""} onChange={(e) => updateNode(id, { description: e.target.value })} />
      </div>

      <div className="rounded-xl border border-border p-2.5">
        <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-medium">
          <Boxes className="h-3.5 w-3.5 text-accent" /> 내부 그래프
          <span className="ml-auto font-mono text-[11px] text-muted">
            노드 {sum.count}
            {sum.nested ? ` · 서브 ${sum.nested}` : ""}
          </span>
        </div>
        <div className="mb-2 flex flex-wrap gap-1">
          {sum.names.map((n) => (
            <span key={n} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-fg-2">
              {n}
            </span>
          ))}
        </div>
        <button onClick={() => enter(id)} className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
          <Maximize2 className="h-3.5 w-3.5" /> 내부 열기 (더블클릭)
        </button>
      </div>

      <div>
        <label className={labelCls}>입출력 방식</label>
        <select className={field} value={d.io ?? "isolated"} onChange={(e) => updateNode(id, { io: e.target.value as SubgraphIO })}>
          <option value="isolated">격리: 대화를 넘기고 최종 답변만 받기</option>
          <option value="shared">상태 공유: 서브그래프를 노드로 직접 등록</option>
        </select>
        <p className="mt-1 text-[11px] leading-relaxed text-muted">
          {d.io === "shared"
            ? "messages 등 같은 이름의 상태 키를 그대로 주고받습니다. 내부 도구 호출 기록까지 부모 대화에 쌓입니다."
            : "부모 대화 기록을 입력으로 넘기고, 끝나면 최종 메시지 하나만 이름표를 붙여 돌려줍니다. Supervisor 워커에 권장."}
        </p>
      </div>
      <div>
        <label className={labelCls}>메모리 (체크포인트)</label>
        <select className={field} value={d.memory ?? "inherit"} onChange={(e) => updateNode(id, { memory: e.target.value as SubgraphMemory })}>
          <option value="inherit">부모 상속: 호출마다 새로 시작</option>
          <option value="persistent">독립 영속: 같은 thread 에서 이전 호출을 기억</option>
        </select>
      </div>

      <div className="rounded-xl border border-border p-2.5">
        <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium">
          <Link2 className="h-3.5 w-3.5 text-accent" /> 프리셋
          {preset && <span className="ml-auto"><SourceBadge source={preset.source} /></span>}
        </div>
        {d.preset ? (
          <p className="mb-2 text-[11.5px] text-muted">
            <b className="text-fg">{d.preset.name}</b> 에서 가져왔습니다.
            {!preset && " (프리셋을 찾을 수 없음: 삭제되었거나 다른 브라우저에 있습니다)"}
            {outdated && <span className="mt-1 block font-medium text-warning">프리셋이 그 뒤로 수정되었습니다.</span>}
          </p>
        ) : (
          <p className="mb-2 text-[11.5px] text-muted">저장해 두면 다른 그래프에서 이 에이전트를 그대로 불러올 수 있습니다.</p>
        )}
        <div className="grid grid-cols-1 gap-1.5">
          <button
            className={btn}
            onClick={() =>
              usePlaygroundUI.getState().openSave({
                graph: d.graph ?? { nodes: [], edges: [] },
                name: d.preset?.name ?? d.name,
                node_name: d.name,
                description: d.description ?? "",
                linkNodeId: id,
                overwriteId: preset && (preset.source === "cloud" || preset.source === "local") ? preset.id : undefined, // 남의 마켓 프리셋은 덮어쓰지 않는다
              })
            }
          >
            <Save className="h-3.5 w-3.5" /> 프리셋으로 저장
          </button>
          {preset && (
            <button
              className={cn(btn, outdated && "border-warning/50 text-warning")}
              onClick={() => {
                if (!confirm(`'${preset.name}' 프리셋의 최신 내용으로 내부 그래프를 바꿀까요? 이 노드 안에서 고친 내용은 사라집니다 (실행 취소 가능).`)) return;
                replaceSubgraph(id, preset.graph, { preset: { id: preset.id, name: preset.name, updatedAt: preset.updated_at || undefined, ...(preset.source === "market" ? { market: true } : {}) } });
                setNotice({ kind: "ok", text: `'${preset.name}' 프리셋 내용으로 갱신했습니다.` });
              }}
            >
              <RefreshCw className="h-3.5 w-3.5" /> 프리셋에서 다시 불러오기
            </button>
          )}
          {d.preset && (
            <button className={btn} onClick={() => updateNode(id, { preset: undefined })}>
              <Unlink className="h-3.5 w-3.5" /> 연결 해제
            </button>
          )}
        </div>
      </div>

      <button
        className={cn(btn, "w-full")}
        onClick={() => {
          const err = ungroup(id);
          if (err) setNotice({ kind: "error", text: err });
          else setNotice({ kind: "ok", text: `'${d.name}' 를 풀어 내부 노드를 현재 그래프에 배치했습니다.` });
        }}
        title="Sub-agent 를 없애고 안쪽 노드를 현재 그래프로 꺼냅니다"
      >
        <Ungroup className="h-3.5 w-3.5" /> 펼치기 (서브그래프 해제)
      </button>
    </>
  );
}

function CustomToolsEditor() {
  const { settings, setSettings } = usePlayground();
  const tools = settings.customTools ?? [];
  const [open, setOpen] = useState<number | null>(null);
  const update = (i: number, patch: Partial<CustomTool>) => setSettings({ customTools: tools.map((t, k) => (k === i ? { ...t, ...patch } : t)) });
  return (
    <div>
      <div className="mb-1.5 flex items-center">
        <label className={cn(labelCls, "mb-0")}>커스텀 도구</label>
        <button
          onClick={() => {
            const taken = new Set([...Object.keys(toolCatalog(settings))]);
            let name = "my_tool";
            for (let i = 2; taken.has(name); i++) name = `my_tool_${i}`;
            setSettings({ customTools: [...tools, { name, description: "", code: CUSTOM_TOOL_TEMPLATE(name) }] });
            setOpen(tools.length);
          }}
          className="ml-auto flex items-center gap-1 text-[11px] font-medium text-accent hover:underline"
        >
          <Plus className="h-3 w-3" /> 추가
        </button>
      </div>
      {tools.length === 0 && <p className="text-[11px] leading-relaxed text-muted">직접 작성한 @tool 함수를 Tools/Agent 노드에서 쓸 수 있습니다. 서브 에이전트 안에서도 공유됩니다.</p>}
      <div className="space-y-1.5">
        {tools.map((t, i) => (
          <div key={i} className="rounded-lg border border-border">
            <button onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left">
              <Wrench className="h-3.5 w-3.5 text-amber-500" />
              <span className="font-mono text-[12px]">{t.name}</span>
              {t.sensitive && <span className="text-[10px] text-danger">민감</span>}
              <ChevronDown className={cn("ml-auto h-3.5 w-3.5 text-muted transition", open === i && "rotate-180")} />
            </button>
            {open === i && (
              <div className="space-y-2 border-t border-border p-2.5">
                <input
                  className={cn(field, "font-mono")}
                  value={t.name}
                  onChange={(e) => {
                    const name = e.target.value.replace(/\W/g, "_");
                    // 함수 이름과 노드에서 고른 도구 이름을 함께 바꾼다
                    const code = t.code.replace(new RegExp(`(def\\s+)${t.name}(\\s*\\()`), `$1${name}$2`);
                    update(i, { name, code });
                    const st = usePlayground.getState();
                    st.nodes.forEach((n) => n.data.tools?.includes(t.name) && st.updateNode(n.id, { tools: n.data.tools.map((x) => (x === t.name ? name : x)) }));
                  }}
                />
                <input className={field} placeholder="설명 (목록 표시용)" value={t.description} onChange={(e) => update(i, { description: e.target.value })} />
                <textarea spellCheck={false} className={cn(field, "min-h-44 resize-y font-mono text-[12px] leading-relaxed")} value={t.code} onChange={(e) => update(i, { code: e.target.value })} />
                <label className="flex items-center gap-2 text-[12px]">
                  <input type="checkbox" checked={!!t.sensitive} onChange={(e) => update(i, { sensitive: e.target.checked })} className="accent-[var(--accent)]" />
                  민감한 작업 (승인 없이 쓰이면 경고)
                </label>
                <button
                  onClick={() => confirm(`'${t.name}' 도구를 삭제할까요?`) && setSettings({ customTools: tools.filter((_, k) => k !== i) })}
                  className="flex items-center gap-1 text-[11px] text-muted hover:text-danger"
                >
                  <Trash2 className="h-3 w-3" /> 삭제
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
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
      <CustomToolsEditor />
    </div>
  );
}

export type RightTab = "palette" | "props" | "graph" | "trace";

export function RightPanel({
  onAdd,
  onAddPreset,
  tab,
  onTab,
  trace,
  traceCount,
  running,
}: {
  onAdd: (k: NodeKind) => void;
  onAddPreset: (p: AgentPreset) => void;
  tab: RightTab;
  onTab: (t: RightTab) => void;
  trace: ReactNode;
  traceCount: number;
  running: boolean;
}) {
  const selectedId = usePlayground((s) => s.selectedId);
  const active = selectedId && tab === "palette" ? "props" : tab;
  const setTab = onTab;
  const tabs = [
    { id: "palette", label: "컴포넌트", icon: Shapes },
    { id: "props", label: "속성", icon: SlidersHorizontal },
    { id: "graph", label: "그래프", icon: Settings2 },
    { id: "trace", label: "트레이스", icon: Activity },
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
              "flex min-w-0 flex-1 items-center justify-center gap-1 border-b-2 px-1 text-xs font-medium whitespace-nowrap transition-colors",
              active === id ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
            )}
          >
            <I className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{label}</span>
            {id === "trace" && (running ? <Loader2 className="h-3 w-3 shrink-0 animate-spin text-accent" /> : traceCount > 0 && <span className="rounded-full bg-surface-2 px-1 text-[10px] text-muted">{traceCount}</span>)}
          </button>
        ))}
      </div>
      {active === "trace" ? (
        <div className="min-h-0 flex-1">{trace}</div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          {active === "palette" ? <Palette onAdd={onAdd} onAddPreset={onAddPreset} /> : active === "props" ? <Inspector /> : <GraphSettingsPanel />}
        </div>
      )}
    </div>
  );
}
