/** 샌드박스 트레이서(backend/sandbox/agentlab_trace.py)가 보내는 실행 이벤트와, 이를 트리로 묶는 로직. */

export type SpanKind = "graph" | "node" | "chain" | "llm" | "tool" | "retriever";

export type TraceUsage = { input: number; output: number; total: number; cached?: number; reasoning?: number };

export type TraceToolCall = { id?: string; name: string; args: unknown };

export type TraceMessage = {
  role: string;
  content: unknown;
  name?: string;
  tool_call_id?: string;
  tool_calls?: TraceToolCall[];
  usage?: TraceUsage;
  status?: string;
};

export type TraceMeta = {
  langgraph_node?: string;
  langgraph_step?: number;
  langgraph_triggers?: string[];
  ls_model_name?: string;
  ls_provider?: string;
  ls_temperature?: number;
};

export type TraceEvent =
  | {
      ev: "start";
      id: string;
      parent: string | null;
      kind: SpanKind;
      name: string;
      meta?: TraceMeta;
      inputs?: unknown;
      model?: string;
      tools?: string[];
      tool_choice?: unknown;
      messages?: TraceMessage[];
      t: number;
    }
  | {
      ev: "end";
      id: string;
      outputs?: unknown;
      message?: TraceMessage | null;
      usage?: TraceUsage | null;
      status?: "error" | "interrupted";
      error?: string;
      t: number;
    };

export type SpanStatus = "running" | "ok" | "error" | "interrupted" | "aborted";

export type Span = {
  id: string;
  parent: string | null;
  kind: SpanKind;
  name: string;
  meta: TraceMeta;
  start: number;
  end?: number;
  status: SpanStatus;
  inputs?: unknown;
  outputs?: unknown;
  model?: string;
  tools?: string[];
  toolChoice?: unknown;
  messages?: TraceMessage[];
  message?: TraceMessage | null;
  usage?: TraceUsage | null;
  error?: string;
  children: string[];
  depth: number;
};

export type TraceSummary = {
  llmCalls: number;
  toolCalls: number;
  nodeRuns: number;
  errors: number;
  tokens: TraceUsage;
  duration: number;
};

export type TraceTree = { spans: Map<string, Span>; roots: string[]; order: string[]; summary: TraceSummary };

/** 이벤트 목록을 트리로 묶는다. live 가 false 이면 끝나지 않은 항목은 aborted 로 표시한다. */
export function buildTrace(events: TraceEvent[], live: boolean): TraceTree {
  const spans = new Map<string, Span>();
  const roots: string[] = [];
  const order: string[] = [];
  const tokens: TraceUsage = { input: 0, output: 0, total: 0 };
  let llmCalls = 0;
  let toolCalls = 0;
  let nodeRuns = 0;
  let errors = 0;
  let lastT = 0;

  for (const e of events) {
    lastT = Math.max(lastT, e.t);
    if (e.ev === "start") {
      const parent = e.parent && spans.has(e.parent) ? spans.get(e.parent)! : null;
      const span: Span = {
        id: e.id,
        parent: parent ? parent.id : null,
        kind: e.kind,
        name: e.name,
        meta: e.meta ?? {},
        start: e.t,
        status: "running",
        inputs: e.inputs,
        model: e.model ?? e.meta?.ls_model_name,
        tools: e.tools,
        toolChoice: e.tool_choice,
        messages: e.messages,
        children: [],
        depth: parent ? parent.depth + 1 : 0,
      };
      spans.set(e.id, span);
      order.push(e.id);
      if (parent) parent.children.push(e.id);
      else roots.push(e.id);
      if (e.kind === "llm") llmCalls++;
      else if (e.kind === "tool") toolCalls++;
      else if (e.kind === "node") nodeRuns++;
    } else {
      const span = spans.get(e.id);
      if (!span) continue;
      span.end = e.t;
      span.status = e.status ?? "ok";
      if (e.outputs !== undefined) span.outputs = e.outputs;
      if (e.message !== undefined) span.message = e.message;
      if (e.usage) {
        span.usage = e.usage;
        tokens.input += e.usage.input;
        tokens.output += e.usage.output;
        tokens.total += e.usage.total;
        if (e.usage.cached) tokens.cached = (tokens.cached ?? 0) + e.usage.cached;
        if (e.usage.reasoning) tokens.reasoning = (tokens.reasoning ?? 0) + e.usage.reasoning;
      }
      if (e.error) span.error = e.error;
      if (span.status === "error") errors++;
    }
  }
  if (!live) for (const s of spans.values()) if (s.status === "running") s.status = "aborted";

  const first = events[0]?.t ?? 0;
  return { spans, roots, order, summary: { llmCalls, toolCalls, nodeRuns, errors, tokens, duration: lastT - first } };
}

/** 노드 이름별 최근 상태 (캔버스 강조용). */
export function nodeStates(tree: TraceTree): Map<string, { status: SpanStatus; runs: number }> {
  const out = new Map<string, { status: SpanStatus; runs: number }>();
  for (const id of tree.order) {
    const s = tree.spans.get(id)!;
    if (s.kind !== "node") continue;
    const prev = out.get(s.name);
    out.set(s.name, { status: s.status, runs: (prev?.runs ?? 0) + 1 });
  }
  return out;
}

export const fmtMs = (ms: number) => (ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`);
export const fmtNum = (n: number) => n.toLocaleString("en-US");
