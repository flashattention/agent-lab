"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleX,
  Coins,
  Crosshair,
  GitBranch,
  Hammer,
  Loader2,
  Pause,
  Search,
  Square,
  Timer,
  Workflow,
  Box,
} from "lucide-react";
import { useDefaultLayout } from "react-resizable-panels";
import { cn } from "@/lib/utils";
import { SplitGroup, SplitHandle, SplitPanel } from "@/components/ui/split";
import { buildTrace, fmtMs, fmtNum, type Span, type SpanKind, type TraceEvent, type TraceMessage, type TraceTree } from "@/lib/trace";

const KIND: Record<SpanKind, { icon: typeof Bot; label: string; color: string }> = {
  graph: { icon: Workflow, label: "그래프", color: "text-accent" },
  node: { icon: Box, label: "노드", color: "text-sky-500" },
  chain: { icon: GitBranch, label: "분기·체인", color: "text-muted" },
  llm: { icon: Bot, label: "LLM", color: "text-violet-500" },
  tool: { icon: Hammer, label: "도구", color: "text-amber-500" },
  retriever: { icon: Search, label: "검색", color: "text-emerald-500" },
};

function StatusIcon({ s }: { s: Span }) {
  if (s.status === "running") return <Loader2 className="h-3 w-3 shrink-0 animate-spin text-accent" />;
  if (s.status === "error") return <CircleX className="h-3 w-3 shrink-0 text-danger" />;
  if (s.status === "interrupted") return <Pause className="h-3 w-3 shrink-0 text-warning" />;
  if (s.status === "aborted") return <Square className="h-2.5 w-2.5 shrink-0 text-muted" />;
  return <CircleCheck className="h-3 w-3 shrink-0 text-success/80" />;
}

const duration = (s: Span, now: number) => (s.end ?? now) - s.start;

/** 실행 트레이스: 왼쪽(또는 위) 실행 트리, 오른쪽(또는 아래) 선택한 항목의 상세. */
export function TracePanel({ events, live }: { events: TraceEvent[]; live: boolean }) {
  const tree = useMemo(() => buildTrace(events, live), [events, live]);
  const [picked, setPicked] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);
  // 패널 폭에 따라 위/아래(좁을 때) 또는 좌/우(넓을 때)로 나누고, 구분선 위치는 방향별로 기억한다
  const boxRef = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  const hasEvents = events.length > 0;
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWide(e.contentRect.width >= 576));
    ro.observe(el);
    return () => ro.disconnect();
  }, [hasEvents]);
  const orientation = wide ? "horizontal" : "vertical";
  const layout = useDefaultLayout({
    id: `agentlab-trace-${orientation}`,
    panelIds: ["tree", "detail"],
    storage: typeof window === "undefined" ? undefined : localStorage,
  });
  const now = events.length ? events[events.length - 1].t : 0;

  // 새 실행이 시작되면 선택을 초기화하고 따라가기를 켠다 (렌더 중 상태 조정)
  const firstId = events[0]?.ev === "start" ? events[0].id : null;
  const [runKey, setRunKey] = useState(firstId);
  if (runKey !== firstId) {
    setRunKey(firstId);
    setPicked(null);
    setFollow(true);
    setCollapsed(new Set());
  }

  // 따라가기: 가장 최근에 시작한 LLM·도구·노드를 선택
  const latest = useMemo(() => {
    for (let i = tree.order.length - 1; i >= 0; i--) {
      const s = tree.spans.get(tree.order[i])!;
      if (s.kind === "llm" || s.kind === "tool" || s.kind === "node" || s.kind === "retriever") return s.id;
    }
    return null;
  }, [tree]);
  const selected = follow ? latest : picked;
  const setSelected = (id: string) => {
    setPicked(id);
    setFollow(false);
  };

  useEffect(() => {
    if (!follow || !selected) return;
    listRef.current?.querySelector(`[data-span="${selected}"]`)?.scrollIntoView({ block: "nearest" });
  }, [selected, follow]);

  const rows = useMemo(() => {
    const out: Span[] = [];
    const walk = (ids: string[]) => {
      for (const id of ids) {
        const s = tree.spans.get(id)!;
        out.push(s);
        if (!collapsed.has(id)) walk(s.children);
      }
    };
    walk(tree.roots);
    return out;
  }, [tree, collapsed]);

  if (!events.length) {
    return (
      <div className="grid h-full place-items-center bg-surface p-4 text-center text-[12.5px] text-muted">
        <div>
          {live ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> 실행 이벤트를 기다리는 중…
            </span>
          ) : (
            <>
              ▶ 실행하면 그래프·노드·LLM·도구 호출이
              <br />
              입력, state, 결과, 토큰 사용량과 함께 실시간으로 표시됩니다.
              <span className="mt-2 block text-[11px]">LangChain / LangGraph 실행만 기록됩니다.</span>
            </>
          )}
        </div>
      </div>
    );
  }

  const sel = selected ? tree.spans.get(selected) : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface text-[12px]">
      <Summary
        tree={tree}
        live={live}
        follow={follow}
        onFollow={() => {
          if (follow) setPicked(selected);
          setFollow(!follow);
        }}
      />
      <div ref={boxRef} className="min-h-0 flex-1">
        <SplitGroup key={orientation} orientation={orientation} className="h-full" defaultLayout={layout.defaultLayout} onLayoutChanged={layout.onLayoutChanged}>
          <SplitPanel id="tree" defaultSize="42" minSize="12">
            <div ref={listRef} className="h-full overflow-auto py-1">
              {rows.map((s) => {
                const K = KIND[s.kind];
                const open = !collapsed.has(s.id);
                return (
                  <div
                    key={s.id}
                    data-span={s.id}
                    onClick={() => setSelected(s.id)}
                    className={cn(
                      "flex cursor-pointer items-center gap-1.5 py-[3px] pr-2 hover:bg-surface-2",
                      selected === s.id && "bg-accent-soft hover:bg-accent-soft",
                      s.kind === "chain" && "opacity-75",
                    )}
                    style={{ paddingLeft: 6 + s.depth * 14 }}
                  >
                    {s.children.length ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setCollapsed((c) => {
                            const n = new Set(c);
                            if (n.has(s.id)) n.delete(s.id);
                            else n.add(s.id);
                            return n;
                          });
                        }}
                        className="rounded text-muted hover:text-fg"
                        aria-label={open ? "접기" : "펼치기"}
                      >
                        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      </button>
                    ) : (
                      <span className="w-3" />
                    )}
                    <K.icon className={cn("h-3.5 w-3.5 shrink-0", K.color)} />
                    <span className={cn("truncate", s.kind === "node" || s.kind === "graph" ? "font-medium text-fg" : "text-fg-2")}>{s.name}</span>
                    {s.kind === "node" && s.meta.langgraph_step != null && <span className="shrink-0 font-mono text-[10px] text-muted">#{s.meta.langgraph_step}</span>}
                    {s.kind === "llm" && s.message?.tool_calls?.length ? (
                      <span title="도구 호출 요청" className="flex shrink-0 items-center gap-0.5 rounded bg-amber-500/15 px-1 text-[10px] text-amber-600 dark:text-amber-400">
                        <Hammer className="h-2.5 w-2.5" />
                        {s.message.tool_calls.length}
                      </span>
                    ) : null}
                    <span className="ml-auto flex shrink-0 items-center gap-1.5 pl-2">
                      {s.usage && <span className="font-mono text-[10px] text-violet-500">{fmtNum(s.usage.total)}t</span>}
                      <span className="w-11 text-right font-mono text-[10px] text-muted">{fmtMs(duration(s, now))}</span>
                      <StatusIcon s={s} />
                    </span>
                  </div>
                );
              })}
            </div>
          </SplitPanel>
          <SplitHandle vertical={!wide} />
          <SplitPanel id="detail" defaultSize="58" minSize="15">
            <div className="h-full min-w-0 overflow-auto">
              {sel ? <Detail s={sel} now={now} /> : <div className="p-4 text-muted">{wide ? "왼쪽" : "위"}에서 항목을 선택하세요.</div>}
            </div>
          </SplitPanel>
        </SplitGroup>
      </div>
    </div>
  );
}

function Summary({ tree, live, follow, onFollow }: { tree: TraceTree; live: boolean; follow: boolean; onFollow: () => void }) {
  const { summary: m } = tree;
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-1.5 text-[11px] text-muted">
      <span className="flex items-center gap-1">
        <Timer className="h-3 w-3" />
        {fmtMs(m.duration)}
      </span>
      <span>노드 {m.nodeRuns}</span>
      <span className="text-violet-500">LLM {m.llmCalls}</span>
      <span className="text-amber-600 dark:text-amber-400">도구 {m.toolCalls}</span>
      <span className="flex items-center gap-1" title={`입력 ${fmtNum(m.tokens.input)} · 출력 ${fmtNum(m.tokens.output)}${m.tokens.cached ? ` · 캐시 ${fmtNum(m.tokens.cached)}` : ""}${m.tokens.reasoning ? ` · 추론 ${fmtNum(m.tokens.reasoning)}` : ""}`}>
        <Coins className="h-3 w-3" />
        {fmtNum(m.tokens.total)} 토큰
        <span className="opacity-70">
          ({fmtNum(m.tokens.input)} → {fmtNum(m.tokens.output)})
        </span>
      </span>
      {m.errors > 0 && <span className="text-danger">오류 {m.errors}</span>}
      <button
        onClick={onFollow}
        title="가장 최근 항목을 자동으로 선택"
        className={cn("ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5", follow ? "bg-accent-soft text-accent" : "hover:bg-surface-2 hover:text-fg")}
      >
        <Crosshair className="h-3 w-3" /> 따라가기
        {live && follow && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ 상세 */

function Detail({ s, now }: { s: Span; now: number }) {
  const K = KIND[s.kind];
  return (
    <div className="space-y-3 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <K.icon className={cn("h-4 w-4", K.color)} />
        <span className="text-[13px] font-semibold text-fg">{s.name}</span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">{K.label}</span>
        {s.meta.langgraph_step != null && <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">step {s.meta.langgraph_step}</span>}
        <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px] text-muted">
          {fmtMs(duration(s, now))} <StatusIcon s={s} />
        </span>
      </div>
      {s.error && <pre className="rounded-lg bg-danger/10 p-2 font-mono text-[11px] whitespace-pre-wrap text-danger">{s.error}</pre>}

      {s.kind === "llm" ? (
        <LlmDetail s={s} />
      ) : s.kind === "tool" ? (
        <>
          <Section title="인자">
            <Json value={s.inputs} />
          </Section>
          <Section title="결과">{s.status === "running" ? <Pending /> : <Json value={s.outputs} />}</Section>
        </>
      ) : s.kind === "retriever" ? (
        <>
          <Section title="쿼리">
            <Json value={s.inputs} />
          </Section>
          <Section title={`검색된 문서${Array.isArray(s.outputs) ? ` (${s.outputs.length})` : ""}`}>{s.status === "running" ? <Pending /> : <Json value={s.outputs} />}</Section>
        </>
      ) : (
        <>
          {s.meta.langgraph_triggers?.length ? <div className="text-[11px] text-muted">트리거: {s.meta.langgraph_triggers.join(", ")}</div> : null}
          <Section title={s.kind === "node" ? "입력 State" : s.kind === "graph" ? "입력" : "입력"}>
            <Json value={s.inputs} />
          </Section>
          <Section title={s.kind === "node" ? "State 업데이트 (반환값)" : s.kind === "chain" ? "결과 (다음 경로)" : "최종 State"}>
            {s.status === "running" ? <Pending /> : <Json value={s.outputs} />}
          </Section>
        </>
      )}
    </div>
  );
}

function LlmDetail({ s }: { s: Span }) {
  const u = s.usage;
  return (
    <>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        {s.model && (
          <span>
            모델 <b className="font-mono font-medium text-fg-2">{s.model}</b>
          </span>
        )}
        {s.meta.ls_temperature != null && <span>temperature {s.meta.ls_temperature}</span>}
        {s.tools?.length ? (
          <span>
            바인딩된 도구 <b className="font-mono font-medium text-fg-2">{s.tools.join(", ")}</b>
          </span>
        ) : null}
        {s.toolChoice != null && <span>tool_choice {typeof s.toolChoice === "string" ? s.toolChoice : JSON.stringify(s.toolChoice)}</span>}
      </div>
      {u && (
        <div className="grid grid-cols-3 gap-1.5 text-center">
          {[
            ["입력", u.input, u.cached ? `캐시 ${fmtNum(u.cached)}` : ""],
            ["출력", u.output, u.reasoning ? `추론 ${fmtNum(u.reasoning)}` : ""],
            ["합계", u.total, ""],
          ].map(([label, v, sub]) => (
            <div key={label as string} className="rounded-lg bg-surface-2 px-2 py-1.5">
              <div className="text-[10px] text-muted">{label} 토큰</div>
              <div className="font-mono text-[13px] font-semibold text-violet-500">{fmtNum(v as number)}</div>
              {sub && <div className="text-[10px] text-muted">{sub}</div>}
            </div>
          ))}
        </div>
      )}
      <Section title={`입력 메시지 (${s.messages?.length ?? 0})`} defaultOpen={false}>
        <div className="space-y-1.5">
          {s.messages?.map((m, i) => <Message key={i} m={m} />)}
        </div>
      </Section>
      <Section title="응답">{s.status === "running" ? <Pending /> : s.message ? <Message m={s.message} /> : <span className="text-muted">없음</span>}</Section>
    </>
  );
}

const ROLE: Record<string, string> = {
  system: "bg-surface-3 text-fg-2",
  human: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  ai: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  AIMessageChunk: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  tool: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
};

function Message({ m }: { m: TraceMessage }) {
  const empty = m.content === "" || m.content == null || (Array.isArray(m.content) && m.content.length === 0);
  return (
    <div className="rounded-lg border border-border bg-bg/40 p-2">
      <div className="mb-1 flex items-center gap-1.5">
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", ROLE[m.role] ?? "bg-surface-2 text-muted")}>{m.role}</span>
        {m.name && <span className="font-mono text-[10px] text-muted">{m.name}</span>}
        {m.tool_call_id && <span className="truncate font-mono text-[10px] text-muted">← {m.tool_call_id}</span>}
        {m.status && <span className="text-[10px] text-danger">{m.status}</span>}
      </div>
      {!empty && (typeof m.content === "string" ? <div className="text-[12px] break-words whitespace-pre-wrap text-fg-2">{m.content}</div> : <Json value={m.content} />)}
      {m.tool_calls?.map((c, i) => (
        <div key={i} className="mt-1.5 rounded-md bg-amber-500/10 p-1.5">
          <div className="flex items-center gap-1.5 text-[11px]">
            <Hammer className="h-3 w-3 text-amber-500" />
            <b className="font-mono font-semibold text-fg">{c.name}</b>
            {c.id && <span className="truncate font-mono text-[10px] text-muted">{c.id}</span>}
          </div>
          <Json value={c.args} />
        </div>
      ))}
    </div>
  );
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="mb-1 flex items-center gap-1 text-[11px] font-semibold tracking-wide text-muted uppercase hover:text-fg">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {title}
      </button>
      {open && children}
    </div>
  );
}

const Pending = () => (
  <span className="flex items-center gap-1.5 text-muted">
    <Loader2 className="h-3 w-3 animate-spin" /> 실행 중…
  </span>
);

/* ------------------------------------------------------------------ JSON 뷰어 */

function Json({ value }: { value: unknown }) {
  if (value === undefined) return <span className="text-muted">—</span>;
  return (
    <div className="overflow-x-auto rounded-md bg-code px-2 py-1.5 font-mono text-[11.5px] leading-relaxed">
      <JsonNode value={value} depth={0} />
    </div>
  );
}

function JsonNode({ value, depth, name }: { value: unknown; depth: number; name?: string }) {
  const [open, setOpen] = useState(depth < 3);
  const label = name !== undefined ? <span className="text-sky-600 dark:text-sky-400">{name}: </span> : null;

  if (value === null || typeof value !== "object") {
    let v: React.ReactNode;
    if (typeof value === "string") {
      v = value.includes("\n") ? (
        <span className="break-words whitespace-pre-wrap text-emerald-600 dark:text-emerald-400">{value}</span>
      ) : (
        <span className="break-words text-emerald-600 dark:text-emerald-400">&quot;{value}&quot;</span>
      );
    } else if (typeof value === "number") v = <span className="text-amber-600 dark:text-amber-400">{value}</span>;
    else v = <span className="text-violet-500">{String(value)}</span>;
    return (
      <div>
        {label}
        {v}
      </div>
    );
  }

  const isArr = Array.isArray(value);
  const entries = isArr ? (value as unknown[]).map((v, i) => [String(i), v] as const) : Object.entries(value as Record<string, unknown>).filter(([k]) => k !== "__type__");
  const type = !isArr ? (value as Record<string, unknown>).__type__ : undefined;
  const [o, c] = isArr ? ["[", "]"] : ["{", "}"];
  if (!entries.length)
    return (
      <div>
        {label}
        <span className="text-muted">
          {typeof type === "string" && `${type} `}
          {o}
          {c}
        </span>
      </div>
    );
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="text-left hover:opacity-80">
        {label}
        <span className="text-muted">
          {typeof type === "string" && <span className="text-accent">{type} </span>}
          {o}
          {!open && ` ${entries.length}${isArr ? "개" : "개 키"} ${c}`}
        </span>
      </button>
      {open && (
        <>
          <div className="border-l border-border/70 pl-3">
            {entries.map(([k, v]) => (
              <JsonNode key={k} name={isArr ? undefined : k} value={v} depth={depth + 1} />
            ))}
          </div>
          <span className="text-muted">{c}</span>
        </>
      )}
    </div>
  );
}
