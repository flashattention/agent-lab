import { describe, expect, it } from "vitest";
import { analyze, highlightAt } from "../analyze";
import { generateProject, normalizeGraph } from "../codegen";
import { customCodeNodes } from "../custom-code";
import { exportGraphJson, parseGraphJson } from "../graph-file";
import { PATTERNS } from "../patterns";
import { defaultSubGraph, flattenNode, groupNodes } from "../subgraph";
import type { Graph } from "../types";

const pattern = (id: string): Graph => structuredClone(PATTERNS.find((p) => p.id === id)!.graph);
const errors = (g: Graph) => analyze(g).issues.filter((i) => i.level === "error");

describe("서브그래프 분석", () => {
  it("안쪽 문제는 경로와 함께 보고되고, 바깥에서는 그 Sub-agent 노드에 표시된다", () => {
    const g = pattern("hierarchical-team");
    const team = g.nodes.find((n) => n.id === "research_team")!;
    team.data.graph!.edges = team.data.graph!.edges.filter((e) => e.target !== "end"); // END 로 가는 길을 끊는다
    const errs = errors(g);
    expect(errs.length).toBeGreaterThan(0);
    expect(errs.every((e) => e.path?.[0] === "research_team")).toBe(true);
    expect(errs[0].message).toMatch(/^\[research_team\]/);
    const a = analyze(g);
    expect(highlightAt(a, []).errorNodes.has("research_team")).toBe(true);
    expect(highlightAt(a, ["research_team"]).errorNodes.size).toBeGreaterThan(0);
  });

  it("안쪽 Human 노드도 최상위 체크포인터를 요구한다", () => {
    const hitl = pattern("hitl");
    const g = pattern("react-agent");
    g.settings.checkpointer = "none";
    g.nodes.push({ id: "sub", kind: "subgraph", data: { name: "approval_flow", description: "승인", graph: { nodes: hitl.nodes, edges: hitl.edges } }, position: { x: 0, y: 0 } });
    expect(errors(g).some((e) => e.message.includes("Checkpointer"))).toBe(true);
  });
});

describe("묶기 · 펼치기", () => {
  it("입구·출구가 하나인 구간은 묶었다가 풀어도 구조 오류가 없다", () => {
    const g = pattern("agentic-rag");
    const grouped = groupNodes(g, ["retrieve", "generate"], "rag_team");
    expect(grouped.ok).toBe(true);
    if (!grouped.ok) return;
    expect(errors({ ...grouped.graph, settings: g.settings })).toEqual([]);
    const flat = flattenNode(grouped.graph, grouped.nodeId);
    expect(flat.ok).toBe(true);
    if (!flat.ok) return;
    expect(errors({ ...flat.graph, settings: g.settings })).toEqual([]);
    expect(flat.graph.nodes.filter((n) => n.kind !== "start" && n.kind !== "end")).toHaveLength(g.nodes.length - 2);
  });

  it("입구가 둘 이상이면 이유와 함께 거부한다", () => {
    const r = groupNodes(pattern("support-system"), ["retrieve", "faq_answer"], "x");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toContain("들어오는 지점");
  });
});

describe("서브그래프 코드 생성", () => {
  const files = generateProject(pattern("hierarchical-team"));

  it("서브 에이전트마다 패키지를 만들고 langgraph.json 에 등록한다", () => {
    for (const team of ["research_team", "writing_team"]) {
      expect(files[`agent/subagents/${team}/graph.py`]).toContain(`name="${team}"`);
      expect(files[`agent/subagents/${team}/state.py`]).toContain("class State");
    }
    expect(JSON.parse(files["langgraph.json"]).graphs).toMatchObject({ research_team: "./agent/subagents/research_team/graph.py:graph" });
    expect(files["tests/test_graph.py"]).toContain("def test_subagent_research_team");
    expect(files["main.py"]).toContain("subgraphs=True");
  });

  it("격리 모드는 최종 답변만, 공유 모드는 컴파일된 그래프를 그대로 노드로 쓴다", () => {
    expect(files["agent/nodes/research_team.py"]).toContain('AIMessage(content=answer.text, name="research_team")');
    const g = pattern("hierarchical-team");
    g.nodes.find((n) => n.id === "research_team")!.data.io = "shared";
    expect(generateProject(g)["agent/nodes/research_team.py"]).toContain("from agent.subagents.research_team.graph import graph as research_team");
  });

  it("노드별 모델과 커스텀 도구가 코드에 반영된다", () => {
    const g = pattern("hierarchical-team");
    const inner = g.nodes.find((n) => n.id === "research_team")!.data.graph!;
    inner.nodes.find((n) => n.data.name === "researcher")!.data.model = "anthropic:claude-sonnet-5-5";
    inner.nodes.find((n) => n.kind === "tools")!.data.tools = ["web_search", "lookup_stock"];
    g.settings.customTools = [{ name: "lookup_stock", description: "재고", code: '@tool\ndef lookup_stock(sku: str) -> str:\n    """재고 조회"""\n    return sku' }];
    const out = generateProject(g);
    expect(out["agent/subagents/research_team/nodes/researcher.py"]).toContain('os.getenv("LAB_MODEL__RESEARCH_TEAM__RESEARCHER", "anthropic:claude-sonnet-5-5")');
    expect(out["requirements.txt"]).toContain("langchain-anthropic");
    expect(out["agent/tools.py"]).toContain("def lookup_stock");
    expect(customCodeNodes(g)).toContain("@tool lookup_stock");
  });

  it("좌표·출처 정보는 캐시 키에 영향을 주지 않는다", () => {
    const a = pattern("hierarchical-team");
    const b = pattern("hierarchical-team");
    const inner = b.nodes.find((n) => n.id === "research_team")!;
    inner.data.preset = { id: "p1", name: "리서처" };
    inner.data.graph!.nodes[1].position = { x: 999, y: 999 };
    expect(normalizeGraph(a)).toEqual(normalizeGraph(b));
  });
});

describe("agentlab.json", () => {
  it("내보낸 그래프를 그대로 다시 읽는다", () => {
    const g = pattern("hierarchical-team");
    expect(parseGraphJson(exportGraphJson(g))).toEqual(g);
  });

  it("모르는 노드 종류나 끊긴 엣지는 거부한다", () => {
    expect(() => parseGraphJson('{"nodes":[{"id":"a","kind":"virus","data":{"name":"a"}}],"edges":[]}')).toThrow();
    const sub = defaultSubGraph();
    sub.edges.push({ id: "x", source: "nowhere", target: "end" });
    expect(() => parseGraphJson(JSON.stringify(sub))).toThrow();
  });
});
