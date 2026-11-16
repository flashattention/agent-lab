"use client";

import { useMemo, useState } from "react";
import { BadgeCheck, Boxes, Copy, Download, Flag, GitFork, Loader2, OctagonAlert, ShieldCheck, Workflow, X } from "lucide-react";
import { analyze } from "@/lib/playground/analyze";
import { allNodes, summarize } from "@/lib/playground/subgraph";
import { DEFAULT_SETTINGS } from "@/lib/playground/types";
import { isDeclarative, reportPreset, shareLink, type AgentPreset } from "@/lib/presets";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { GraphThumb } from "@/components/projects/graph-thumb";
import { arrangedSub } from "@/components/playground/store";

/** 보는 사람의 브라우저에서 직접 계산하는 신뢰 신호 (서버나 작성자가 주장하는 값이 아니다) */
export function trustOf(p: AgentPreset) {
  const declarative = isDeclarative(p.graph);
  const a = analyze({ nodes: p.graph.nodes, edges: p.graph.edges, settings: DEFAULT_SETTINGS });
  const models = [...new Set(allNodes(p.graph).map((n) => n.data.model).filter(Boolean))] as string[];
  return { declarative, structureOk: a.ok, errors: a.issues.filter((i) => i.level === "error").length, models };
}

export function TrustBadges({ p, compact }: { p: AgentPreset; compact?: boolean }) {
  const t = useMemo(() => trustOf(p), [p]);
  return (
    <span className="flex flex-wrap items-center gap-1">
      {t.declarative ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold text-success" title="Function 노드·커스텀 도구가 없어 실행되는 코드는 템플릿뿐입니다">
          <ShieldCheck className="h-3 w-3" /> 코드 없음
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning" title="작성자가 직접 쓴 코드가 들어 있습니다">
          <OctagonAlert className="h-3 w-3" /> 코드 포함
        </span>
      )}
      {t.structureOk ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent" title="내 브라우저에서 구조 분석기를 돌려 통과했습니다">
          <BadgeCheck className="h-3 w-3" /> 구조 검사 통과
        </span>
      ) : (
        !compact && <span className="rounded-full bg-danger/10 px-2 py-0.5 text-[10px] font-semibold text-danger">구조 오류 {t.errors}</span>
      )}
    </span>
  );
}

export function PresetDetail({
  preset: p,
  onClose,
  onUse,
  onFork,
  useLabel = "플레이그라운드에서 쓰기",
}: {
  preset: AgentPreset;
  onClose: () => void;
  onUse: (p: AgentPreset) => void;
  onFork?: (p: AgentPreset) => Promise<void>;
  useLabel?: string;
}) {
  const user = useAuth((x) => x.user);
  const sum = summarize(p.graph);
  const t = useMemo(() => trustOf(p), [p]);
  const tools = useMemo(() => (p.graph.tools ?? []).map((x) => x.name), [p]);
  const functions = useMemo(() => allNodes(p.graph).filter((n) => n.kind === "function").map((n) => n.data.name), [p]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState("");

  const copy = async () => {
    await navigator.clipboard.writeText(shareLink(p.id));
    setMsg({ ok: true, text: "링크를 복사했습니다." });
  };
  const exportJson = () => {
    const body = { format: "agentlab.preset", version: 1, preset: { name: p.name, node_name: p.node_name, description: p.description, graph: p.graph } };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
    a.download = `${p.node_name}.agentlab-preset.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={p.name} className="fade-in flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
        <div className="flex items-start gap-3 border-b border-border px-6 py-4">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-white" style={{ background: "#7c3aed" }}>
            <Boxes className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold">{p.name}</h2>
            <p className="text-xs text-muted">
              <span className="font-mono">{p.node_name}</span>
              {p.author_name && <> · {p.author_name}</>}
              {p.category && <> · {p.category}</>}
              {typeof p.installs === "number" && <> · 설치 {p.installs.toLocaleString()}</>}
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="닫기">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="bg-grid h-56 border-b border-border p-4">
            <GraphThumb graph={arrangedSub(p.graph)} className="h-full w-full" />
          </div>
          <div className="grid gap-6 p-6 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <div className="min-w-0 space-y-4">
              <TrustBadges p={p} />
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-fg-2">{p.description || "설명이 없습니다."}</p>
              {!t.declarative && (
                <div className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-[12.5px] leading-relaxed text-warning">
                  작성자가 직접 쓴 코드가 들어 있습니다{functions.length ? ` (Function 노드: ${functions.join(", ")})` : ""}
                  {tools.length ? ` (커스텀 도구: ${tools.join(", ")})` : ""}. 넣은 뒤 코드를 확인하고, 처음에는 Mock 모드로 실행해 보세요.
                </div>
              )}
            </div>
            <dl className="space-y-3 text-[12.5px]">
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">구성</dt>
                <dd className="mt-1">
                  노드 {sum.count}개{sum.nested ? ` · 서브 에이전트 ${sum.nested}개` : ""}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {sum.names.map((n) => (
                      <span key={n} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-2">
                        {n}
                      </span>
                    ))}
                  </div>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">도구</dt>
                <dd className="mt-1 font-mono text-[11.5px] text-fg-2">{sum.tools.length ? sum.tools.join(", ") : "없음"}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">모델</dt>
                <dd className="mt-1 font-mono text-[11.5px] text-fg-2">{t.models.length ? t.models.join(", ") : "기본 모델 (LAB_MODEL)"}</dd>
              </div>
              {p.updated_at && (
                <div>
                  <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">마지막 수정</dt>
                  <dd className="mt-1 text-fg-2">{new Date(p.updated_at).toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </div>

          {reporting && (
            <div className="mx-6 mb-4 rounded-xl border border-border p-3">
              <label className="mb-1 block text-[11px] font-semibold tracking-wide text-muted uppercase">신고 사유</label>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-16 w-full resize-y rounded-lg border border-border bg-bg px-2.5 py-1.5 text-[13px] outline-none focus:border-accent" placeholder="스팸, 악성 프롬프트, 저작권 침해 등" />
              <div className="mt-2 flex justify-end gap-2">
                <button onClick={() => setReporting(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-surface-2">
                  취소
                </button>
                <button
                  disabled={!reason.trim() || busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await reportPreset(p.id, reason);
                      setReporting(false);
                      setMsg({ ok: true, text: "신고가 접수되었습니다. 여러 명이 신고하면 자동으로 숨겨집니다." });
                    } catch (e) {
                      setMsg({ ok: false, text: (e as Error).message });
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                >
                  신고하기
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-border px-6 py-3">
          {msg && <span className={cn("mr-auto text-xs", msg.ok ? "text-success" : "text-danger")}>{msg.text}</span>}
          {!msg && (
            <span className="mr-auto flex gap-1">
              <button onClick={copy} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-fg" title="공유 링크 복사">
                <Copy className="h-3.5 w-3.5" /> 링크
              </button>
              <button onClick={exportJson} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-fg" title="JSON 으로 내려받기">
                <Download className="h-3.5 w-3.5" /> JSON
              </button>
              {user && p.owner !== user.id && (
                <button onClick={() => setReporting(true)} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-muted hover:bg-danger/10 hover:text-danger" title="신고">
                  <Flag className="h-3.5 w-3.5" /> 신고
                </button>
              )}
            </span>
          )}
          {onFork && (
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onFork(p);
                  setMsg({ ok: true, text: "내 프리셋에 복제했습니다. 플레이그라운드의 프리셋 목록에서 바로 쓸 수 있습니다." });
                } catch (e) {
                  setMsg({ ok: false, text: (e as Error).message });
                } finally {
                  setBusy(false);
                }
              }}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2 disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitFork className="h-3.5 w-3.5" />} 내 프리셋에 복제
            </button>
          )}
          <button onClick={() => onUse(p)} className="flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
            <Workflow className="h-3.5 w-3.5" /> {useLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
