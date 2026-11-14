import { describe, expect, it } from "vitest";
import { buildTrace, fmtMs, nodeStates, type SpanKind, type TraceEvent } from "../trace";

const start = (id: string, parent: string | null, kind: SpanKind, name: string, t: number, extra = {}): TraceEvent => ({
  ev: "start",
  id,
  parent,
  kind,
  name,
  t,
  ...extra,
});
const end = (id: string, t: number, extra = {}): TraceEvent => ({ ev: "end", id, t, ...extra });

const events: TraceEvent[] = [
  start("g", null, "graph", "LangGraph", 0),
  start("n1", "g", "node", "agent", 1, { meta: { langgraph_step: 1 } }),
  start("l1", "n1", "llm", "ChatOpenAI", 2, { model: "gpt-5-mini" }),
  end("l1", 10, { usage: { input: 10, output: 5, total: 15 }, message: { role: "ai", content: "", tool_calls: [{ name: "f", args: {} }] } }),
  end("n1", 11),
  start("n2", "g", "node", "tools", 12, { meta: { langgraph_step: 2 } }),
  start("t1", "n2", "tool", "f", 13),
  end("t1", 14, { status: "error", error: "ValueError: x" }),
  end("n2", 15, { status: "error" }),
  start("n3", "g", "node", "agent", 16, { meta: { langgraph_step: 3 } }),
  start("l2", "n3", "llm", "ChatOpenAI", 17),
  end("l2", 30, { usage: { input: 20, output: 7, total: 27, cached: 4 } }),
];

describe("buildTrace", () => {
  it("부모-자식 트리와 깊이를 만든다", () => {
    const t = buildTrace(events, true);
    expect(t.roots).toEqual(["g"]);
    expect(t.spans.get("g")!.children).toEqual(["n1", "n2", "n3"]);
    expect(t.spans.get("l1")!.depth).toBe(2);
    expect(t.order).toHaveLength(7);
  });

  it("요약: 호출 수, 토큰 합계, 오류 수, 전체 시간", () => {
    const { summary } = buildTrace(events, true);
    expect(summary).toMatchObject({ llmCalls: 2, toolCalls: 1, nodeRuns: 3, errors: 2, duration: 30 });
    expect(summary.tokens).toEqual({ input: 30, output: 12, total: 42, cached: 4 });
  });

  it("끝나지 않은 항목은 실행 중이었다가, 실행이 끝나면 중단(aborted)으로 표시한다", () => {
    expect(buildTrace(events, true).spans.get("n3")!.status).toBe("running");
    expect(buildTrace(events, false).spans.get("n3")!.status).toBe("aborted");
    expect(buildTrace(events, false).spans.get("l2")!.status).toBe("ok");
  });

  it("오류와 응답 메시지를 담는다", () => {
    const t = buildTrace(events, false);
    expect(t.spans.get("t1")).toMatchObject({ status: "error", error: "ValueError: x" });
    expect(t.spans.get("l1")!.message?.tool_calls?.[0].name).toBe("f");
  });

  it("부모를 모르는 이벤트는 루트로 둔다", () => {
    const t = buildTrace([start("x", "missing", "llm", "m", 0)], true);
    expect(t.roots).toEqual(["x"]);
  });
});

describe("nodeStates", () => {
  it("노드 이름별 마지막 상태와 실행 횟수", () => {
    const s = nodeStates(buildTrace(events, false));
    expect(s.get("agent")).toEqual({ status: "aborted", runs: 2 });
    expect(s.get("tools")).toEqual({ status: "error", runs: 1 });
  });
});

describe("fmtMs", () => {
  it.each([
    [12.4, "12ms"],
    [1500, "1.50s"],
    [12_345, "12.3s"],
  ])("%s → %s", (ms, out) => expect(fmtMs(ms)).toBe(out));
});
