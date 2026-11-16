"use client";

import { useMemo, useState } from "react";
import { ArrowDown, Bot, CheckCircle2, CircleAlert, CircleMinus, CornerDownLeft, PackageOpen, X } from "lucide-react";
import { MODEL_SUGGESTIONS, toolCatalog } from "@/lib/playground/catalog";
import { ejectAgent } from "@/lib/playground/subgraph";
import type { AgentMiddleware, PiiType } from "@/lib/playground/types";
import { cn } from "@/lib/utils";
import { usePlayground } from "./store";
import { usePlaygroundUI } from "./ui-store";

const field = "w-full rounded-lg border border-border bg-bg px-2.5 py-1.5 text-[13px] outline-none focus:border-accent";
const PII_TYPES: [PiiType, string][] = [
  ["email", "이메일"],
  ["credit_card", "카드 번호"],
  ["ip", "IP 주소"],
  ["mac_address", "MAC 주소"],
  ["url", "URL"],
];

/** Agent(create_agent) 노드: 내부 루프 도식 + 미들웨어 설정 + 고급 '그래프로 꺼내기' */
export function AgentLoopDialog() {
  const id = usePlaygroundUI((x) => x.agentDialog);
  return id ? <Dialog key={id} id={id} /> : null;
}

function Dialog({ id }: { id: string }) {
  const close = () => usePlaygroundUI.getState().setAgentDialog(null);
  const node = usePlayground((s) => s.nodes.find((n) => n.id === id));
  const settings = usePlayground((s) => s.settings);
  const [ejecting, setEjecting] = useState(false);
  const catalog = toolCatalog(settings);
  const report = useMemo(() => {
    if (!node) return [];
    const { kind, ...data } = node.data;
    void kind;
    return ejectAgent({ id: node.id, kind: "agent", data, position: node.position }).report;
  }, [node]);
  if (!node || node.data.kind !== "agent") return null;
  const d = node.data;
  const mw: AgentMiddleware = d.middleware ?? {};
  const tools = d.tools ?? [];
  const set = (patch: Partial<AgentMiddleware>) => {
    const next = { ...mw, ...patch };
    for (const k of Object.keys(next) as (keyof AgentMiddleware)[]) if (next[k] === undefined) delete next[k];
    usePlayground.getState().updateNode(id, { middleware: Object.keys(next).length ? next : undefined });
  };
  const on = (k: keyof AgentMiddleware) => mw[k] !== undefined;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div role="dialog" aria-modal="true" aria-label={`${d.name} 루프와 미들웨어`} className="fade-in flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
        <div className="flex items-start gap-3 border-b border-border px-6 py-4">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-white" style={{ background: "#6366f1" }}>
            <Bot className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate font-mono text-lg font-semibold">{d.name}</h2>
            <p className="text-xs text-muted">create_agent 의 루프는 라이브러리가 관리합니다. 루프 안에 끼어드는 동작은 미들웨어로 바꿉니다.</p>
          </div>
          <button onClick={close} className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="닫기">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 overflow-y-auto md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          {/* 루프 도식 (읽기 전용) */}
          <div className="bg-grid border-b border-border p-6 md:border-r md:border-b-0">
            <div className="mx-auto flex max-w-xs flex-col items-center gap-1.5 text-[12px]">
              <Box label="입력 메시지" muted />
              <ArrowDown className="h-3.5 w-3.5 text-muted" />
              <Hooks title="모델 호출 전" items={[["대화 요약", on("summarization")], ["PII 마스킹", on("pii")], ["모델 호출 상한", on("modelCallLimit")]]} />
              <Box label="모델" sub={d.model || "기본 모델 (LAB_MODEL)"} color="#8b5cf6" chips={[["재시도", on("retry")], ["대체 모델", on("fallback")]]} />
              <ArrowDown className="h-3.5 w-3.5 text-muted" />
              <div className="rounded-full border border-dashed border-border-strong bg-surface px-3 py-1 text-[11px] text-muted">도구를 호출했나?</div>
              <div className="grid w-full grid-cols-2 gap-2">
                <div className="flex flex-col items-center gap-1.5">
                  <span className="text-[10px] text-muted">예</span>
                  <Hooks title="도구 실행 전" items={[["사람 승인", on("hitl")], ["도구 호출 상한", on("toolCallLimit")]]} />
                  <Box label="도구" sub={tools.length ? tools.join(", ") : "없음"} color="#f59e0b" chips={[["재시도", on("retry")]]} />
                  <span className="flex items-center gap-1 text-[10px] text-muted">
                    <CornerDownLeft className="h-3 w-3" /> 결과를 들고 모델로
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1.5">
                  <span className="text-[10px] text-muted">아니오</span>
                  <Box label="최종 답변" sub="부모 그래프로 반환" muted />
                </div>
              </div>
            </div>
          </div>

          {/* 미들웨어 설정 */}
          <div className="space-y-2.5 p-6">
            <Toggle
              title="도구 실행 전 사람 승인"
              api="HumanInTheLoopMiddleware"
              desc="고른 도구를 실행하기 직전에 멈추고 승인·수정·거절을 받습니다."
              on={on("hitl")}
              onChange={(v) => set({ hitl: v ? { tools: tools.filter((t) => catalog[t]?.sensitive) } : undefined })}
            >
              <div className="flex flex-wrap gap-1.5">
                {tools.map((t) => (
                  <label key={t} className={cn("flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[11px]", catalog[t]?.sensitive ? "border-danger/40 text-danger" : "border-border")}>
                    <input
                      type="checkbox"
                      checked={mw.hitl?.tools.includes(t) ?? false}
                      onChange={(e) => set({ hitl: { tools: e.target.checked ? [...(mw.hitl?.tools ?? []), t] : (mw.hitl?.tools ?? []).filter((x) => x !== t) } })}
                      className="accent-[var(--accent)]"
                    />
                    {t}
                  </label>
                ))}
                {!tools.length && <span className="text-[11px] text-muted">이 Agent 에 도구가 없습니다.</span>}
              </div>
              {settings.checkpointer === "none" && (
                <p className="mt-2 flex items-center gap-1.5 text-[11px] text-warning">
                  <CircleAlert className="h-3.5 w-3.5" /> 승인을 기다리려면 체크포인터가 필요합니다.
                  <button onClick={() => usePlayground.getState().setSettings({ checkpointer: "memory" })} className="font-semibold underline">
                    InMemorySaver 켜기
                  </button>
                </p>
              )}
            </Toggle>
            <Toggle title="호출 상한" api="ModelCallLimitMiddleware · ToolCallLimitMiddleware" desc="실행 한 번에 모델·도구를 부르는 횟수를 제한해 비용 폭주와 무한 루프를 막습니다." on={on("modelCallLimit") || on("toolCallLimit")} onChange={(v) => set(v ? { modelCallLimit: 10, toolCallLimit: 20 } : { modelCallLimit: undefined, toolCallLimit: undefined })}>
              <div className="grid grid-cols-2 gap-2 text-[11px] text-muted">
                <label>
                  모델 호출 최대
                  <input type="number" min={1} className={cn(field, "mt-1")} value={mw.modelCallLimit ?? ""} onChange={(e) => set({ modelCallLimit: e.target.value ? Number(e.target.value) : undefined })} />
                </label>
                <label>
                  도구 호출 최대
                  <input type="number" min={1} className={cn(field, "mt-1")} value={mw.toolCallLimit ?? ""} onChange={(e) => set({ toolCallLimit: e.target.value ? Number(e.target.value) : undefined })} />
                </label>
              </div>
            </Toggle>
            <Toggle title="대화 요약" api="SummarizationMiddleware" desc="대화가 길어지면 오래된 메시지를 요약으로 바꿔 컨텍스트를 줄입니다." on={on("summarization")} onChange={(v) => set({ summarization: v ? { tokens: 4000 } : undefined })}>
              <label className="text-[11px] text-muted">
                요약을 시작할 토큰 수
                <input type="number" min={500} step={500} className={cn(field, "mt-1")} value={mw.summarization?.tokens ?? 4000} onChange={(e) => set({ summarization: { tokens: Number(e.target.value) } })} />
              </label>
            </Toggle>
            <Toggle title="재시도" api="ModelRetryMiddleware · ToolRetryMiddleware" desc="모델·도구 호출이 일시적으로 실패하면 지수 백오프로 다시 시도합니다." on={on("retry")} onChange={(v) => set({ retry: v ? { maxRetries: 2 } : undefined })}>
              <label className="text-[11px] text-muted">
                최대 재시도
                <input type="number" min={1} max={10} className={cn(field, "mt-1")} value={mw.retry?.maxRetries ?? 2} onChange={(e) => set({ retry: { maxRetries: Number(e.target.value) } })} />
              </label>
            </Toggle>
            <Toggle title="대체 모델" api="ModelFallbackMiddleware" desc="기본 모델이 실패하면 다른 모델로 다시 시도합니다." on={on("fallback")} onChange={(v) => set({ fallback: v ? "openai:gpt-5-mini" : undefined })}>
              <input list="fallback-models" className={cn(field, "font-mono")} value={mw.fallback ?? ""} onChange={(e) => set({ fallback: e.target.value.trim() })} />
              <datalist id="fallback-models">
                {MODEL_SUGGESTIONS.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </Toggle>
            <Toggle title="PII 마스킹" api="PIIMiddleware" desc="모델에 보내기 전 사용자 입력에서 개인정보를 찾아 처리합니다." on={on("pii")} onChange={(v) => set({ pii: v ? { types: ["email", "credit_card"], strategy: "redact" } : undefined })}>
              <div className="flex flex-wrap items-center gap-1.5">
                {PII_TYPES.map(([t, label]) => (
                  <label key={t} className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px]">
                    <input
                      type="checkbox"
                      checked={mw.pii?.types.includes(t) ?? false}
                      onChange={(e) => set({ pii: { strategy: mw.pii?.strategy ?? "redact", types: e.target.checked ? [...(mw.pii?.types ?? []), t] : (mw.pii?.types ?? []).filter((x) => x !== t) } })}
                      className="accent-[var(--accent)]"
                    />
                    {label}
                  </label>
                ))}
                <select className="rounded-md border border-border bg-bg px-1.5 py-1 text-[11px]" value={mw.pii?.strategy ?? "redact"} onChange={(e) => set({ pii: { types: mw.pii?.types ?? [], strategy: e.target.value as "redact" } })}>
                  <option value="redact">가리기 [REDACTED]</option>
                  <option value="mask">일부만 보이기</option>
                  <option value="hash">해시로 바꾸기</option>
                  <option value="block">발견하면 중단</option>
                </select>
              </div>
            </Toggle>
          </div>
        </div>

        {/* 고급: 그래프로 꺼내기 */}
        <div className="border-t border-border px-6 py-3">
          {!ejecting ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="mr-auto text-[11.5px] leading-relaxed text-muted">
                미들웨어로 안 되는 구조 변경(분기 추가, 상태 필드, 병렬 작업)이 필요하면 루프를 그래프로 꺼낼 수 있습니다. 꺼낸 뒤에는 루프를 직접 관리합니다.
              </p>
              <button onClick={() => setEjecting(true)} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2">
                <PackageOpen className="h-3.5 w-3.5" /> 고급: 그래프로 꺼내기
              </button>
              <button onClick={close} className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
                완료
              </button>
            </div>
          ) : (
            <div>
              <p className="mb-2 text-[12.5px] font-semibold">꺼내면 이렇게 바뀝니다 (Ctrl/⌘+Z 로 되돌릴 수 있음)</p>
              <ul className="mb-3 space-y-1">
                {report.map((r) => (
                  <li key={r.label} className="flex gap-2 text-[12px]">
                    {r.status === "kept" ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                    ) : r.status === "approx" ? (
                      <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                    ) : (
                      <CircleMinus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
                    )}
                    <span>
                      <b className="font-medium">{r.label}</b> <span className="text-muted">— {{ kept: "유지", approx: "근사", lost: "사라짐" }[r.status]}: {r.note}</span>
                    </span>
                  </li>
                ))}
              </ul>
              <div className="flex justify-end gap-2">
                <button onClick={() => setEjecting(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-surface-2">
                  취소
                </button>
                <button
                  onClick={() => {
                    const st = usePlayground.getState();
                    if (!st.ejectAgent(id)) return;
                    close();
                    st.enter(id);
                    usePlaygroundUI.getState().setNotice({ kind: "ok", text: `'${d.name}' 를 그래프로 꺼냈습니다. 이제 안쪽 루프를 직접 고칠 수 있습니다. (되돌리기: Ctrl/⌘+Z)` });
                  }}
                  className="flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110"
                >
                  <PackageOpen className="h-3.5 w-3.5" /> 꺼내서 안으로 들어가기
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Box({ label, sub, color, muted, chips = [] }: { label: string; sub?: string; color?: string; muted?: boolean; chips?: [string, boolean][] }) {
  return (
    <div className={cn("w-full rounded-xl border bg-surface px-3 py-2 text-center", muted ? "border-dashed border-border-strong text-muted" : "border-border-strong")} style={color ? { borderColor: color } : undefined}>
      <div className="font-semibold">{label}</div>
      {sub && <div className="truncate font-mono text-[10px] text-muted">{sub}</div>}
      {chips.length > 0 && (
        <div className="mt-1 flex flex-wrap justify-center gap-1">
          {chips.map(([c, active]) => (
            <Chip key={c} label={c} active={active} />
          ))}
        </div>
      )}
    </div>
  );
}

function Hooks({ title, items }: { title: string; items: [string, boolean][] }) {
  return (
    <div className="w-full rounded-lg border border-dashed border-border px-2 py-1.5 text-center">
      <div className="text-[9.5px] tracking-wide text-muted uppercase">{title}</div>
      <div className="mt-1 flex flex-wrap justify-center gap-1">
        {items.map(([c, active]) => (
          <Chip key={c} label={c} active={active} />
        ))}
      </div>
    </div>
  );
}

const Chip = ({ label, active }: { label: string; active: boolean }) => (
  <span className={cn("rounded-full px-1.5 py-0.5 text-[10px]", active ? "bg-accent text-accent-fg" : "bg-surface-2 text-muted line-through decoration-muted/40")}>{label}</span>
);

function Toggle({ title, api, desc, on, onChange, children }: { title: string; api: string; desc: string; on: boolean; onChange: (v: boolean) => void; children?: React.ReactNode }) {
  return (
    <div className={cn("rounded-xl border p-3 transition-colors", on ? "border-accent/50 bg-accent-soft/40" : "border-border")}>
      <label className="flex cursor-pointer items-start gap-2.5">
        <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 accent-[var(--accent)]" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold">{title}</span>
          <span className="block font-mono text-[10px] text-muted">{api}</span>
          <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted">{desc}</span>
        </span>
      </label>
      {on && children && <div className="mt-2.5 pl-6">{children}</div>}
    </div>
  );
}
