import { describe, expect, it } from "vitest";
import { analyze } from "../analyze";
import { generateProject } from "../codegen";
import { PATTERNS } from "../patterns";
import { ejectAgent } from "../subgraph";
import type { AgentMiddleware, GNode, Graph } from "../types";

const hitlPattern = (): Graph => structuredClone(PATTERNS.find((p) => p.id === "hitl")!.graph);
const withMiddleware = (g: Graph, name: string, middleware: AgentMiddleware): Graph => ({
  ...g,
  nodes: g.nodes.map((n) => (n.data.name === name ? { ...n, data: { ...n.data, middleware } } : n)),
});
const levels = (g: Graph, level: "error" | "warning") => analyze(g).issues.filter((i) => i.level === level).map((i) => i.message);

describe("Agent 미들웨어 코드 생성", () => {
  it("켠 미들웨어만 create_agent(middleware=[...]) 에 들어간다", () => {
    const g = withMiddleware(hitlPattern(), "support_agent", {
      summarization: { tokens: 3000 },
      pii: { types: ["email"], strategy: "mask" },
      modelCallLimit: 8,
      toolCallLimit: 12,
      retry: { maxRetries: 3 },
      fallback: "openai:gpt-5-nano",
    });
    const src = generateProject(g)["agent/nodes/support_agent.py"];
    expect(src).toContain(
      "from langchain.agents.middleware import ModelCallLimitMiddleware, ModelFallbackMiddleware, ModelRetryMiddleware, PIIMiddleware, SummarizationMiddleware, ToolCallLimitMiddleware, ToolRetryMiddleware",
    );
    for (const line of ['SummarizationMiddleware(MODEL, trigger=("tokens", 3000))', 'PIIMiddleware("email", strategy="mask")', "ModelCallLimitMiddleware(run_limit=8)", "ToolCallLimitMiddleware(run_limit=12)", "ModelRetryMiddleware(max_retries=3)", 'ModelFallbackMiddleware("openai:gpt-5-nano")'])
      expect(src).toContain(line);
    expect(src).not.toContain("HumanInTheLoopMiddleware");
    expect(generateProject(hitlPattern())["agent/nodes/support_agent.py"]).not.toContain("middleware=");
  });

  it("승인 미들웨어는 이 Agent 의 도구만 대상으로 하고, main.py 가 decisions 로 재개한다", () => {
    const g = withMiddleware(hitlPattern(), "executor", { hitl: { tools: ["issue_refund", "web_search"] } });
    const files = generateProject(g);
    expect(files["agent/nodes/executor.py"]).toContain('HumanInTheLoopMiddleware(interrupt_on={"issue_refund": True})');
    expect(files["main.py"]).toContain('"action_requests" in value');
    expect(files["main.py"]).toContain("Command(resume=approve(interrupted[0]))");
  });
});

describe("Agent 미들웨어 분석", () => {
  it("승인 미들웨어는 체크포인터를 요구하고, 민감한 도구 경고를 해소한다", () => {
    const g = withMiddleware(hitlPattern(), "executor", { hitl: { tools: ["issue_refund"] } });
    const noHuman = { ...g, nodes: g.nodes.filter((n) => n.kind !== "human"), edges: [...g.edges.filter((e) => e.source !== "approval" && e.target !== "approval"), { id: "x", source: "support_agent", target: "executor" }] };
    expect(levels(noHuman, "warning").some((m) => m.includes("민감한 도구"))).toBe(false);
    const unguarded = { ...noHuman, nodes: noHuman.nodes.map((n) => ({ ...n, data: { ...n.data, middleware: undefined } })) };
    expect(levels(unguarded, "warning").some((m) => m.includes("민감한 도구"))).toBe(true);
    expect(levels({ ...noHuman, settings: { ...noHuman.settings, checkpointer: "none" } }, "error").some((m) => m.includes("Checkpointer"))).toBe(true);
  });

  it("잘못된 값은 오류로 알린다", () => {
    const g = withMiddleware(hitlPattern(), "support_agent", { modelCallLimit: 0, fallback: "gpt5", summarization: { tokens: 10 } });
    const errs = levels(g, "error");
    expect(errs.some((m) => m.includes("모델 호출 상한"))).toBe(true);
    expect(errs.some((m) => m.includes("대체 모델"))).toBe(true);
    expect(errs.some((m) => m.includes("요약 기준"))).toBe(true);
  });
});

describe("Agent → 그래프로 꺼내기", () => {
  const agent = (middleware?: AgentMiddleware): GNode => ({
    id: "a1",
    kind: "agent",
    data: { name: "support", prompt: "도와주세요", tools: ["get_order_status", "issue_refund"], model: "openai:gpt-5", middleware },
    position: { x: 0, y: 0 },
  });
  const asRoot = (g: { nodes: GNode[]; edges: Graph["edges"] }): Graph => ({ ...g, settings: hitlPattern().settings });

  it("프롬프트·도구·모델을 옮긴 LLM ↔ 도구 루프가 되고, 구조 오류가 없다", () => {
    const { graph, report } = ejectAgent(agent());
    const model = graph.nodes.find((n) => n.id === "model")!;
    expect(model.data).toMatchObject({ prompt: "도와주세요", model: "openai:gpt-5" });
    expect(graph.nodes.find((n) => n.kind === "tools")!.data.tools).toEqual(["get_order_status", "issue_refund"]);
    expect(levels(asRoot(graph), "error")).toEqual([]);
    expect(report.every((r) => r.status !== "lost")).toBe(true);
    expect(generateProject(asRoot(graph))["agent/nodes/model.py"]).toContain(".bind_tools(");
  });

  it("승인은 Human 노드로 근사하고, 옮길 수 없는 미들웨어는 '사라짐'으로 보고한다", () => {
    const { graph, report } = ejectAgent(agent({ hitl: { tools: ["issue_refund"] }, summarization: { tokens: 4000 }, modelCallLimit: 5, retry: { maxRetries: 2 } }));
    expect(graph.nodes.some((n) => n.kind === "human")).toBe(true);
    expect(levels(asRoot(graph), "error")).toEqual([]);
    const status = Object.fromEntries(report.map((r) => [r.label, r.status]));
    expect(status).toMatchObject({ "도구 실행 전 승인": "approx", 재시도: "approx", "대화 요약": "lost", "호출 상한": "lost" });
  });

  it("승인할 도구를 고르지 않았으면 Human 노드를 넣지 않고 그렇다고 보고한다", () => {
    const { graph, report } = ejectAgent(agent({ hitl: { tools: [] } }));
    expect(graph.nodes.some((n) => n.kind === "human")).toBe(false);
    expect(report.find((r) => r.label === "도구 실행 전 승인")?.status).toBe("lost");
  });

  it("도구가 없는 Agent 는 단순 LLM 노드가 된다", () => {
    const { graph } = ejectAgent({ ...agent(), data: { name: "plain", prompt: "hi" } });
    expect(graph.nodes.map((n) => n.kind).sort()).toEqual(["end", "llm", "start"]);
    expect(levels(asRoot(graph), "error")).toEqual([]);
  });
});
