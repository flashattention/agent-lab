import { describe, expect, it } from "vitest";
import { analyze } from "../analyze";
import { defaultData } from "../catalog";
import { PATTERNS } from "../patterns";
import { DEFAULT_SETTINGS, type GEdge, type GNode, type Graph, type NodeData, type NodeKind } from "../types";

// 작은 그래프를 만드는 도우미: node("llm", "agent"), edge("start", "agent")
const node = (kind: NodeKind, name: string, data: Partial<NodeData> = {}): GNode => ({
  id: kind === "start" ? "start" : kind === "end" ? "end" : name,
  kind,
  data: { ...defaultData(kind), name, ...data },
  position: { x: 0, y: 0 },
});
const edge = (source: string, target: string, sourceHandle: string | null = null): GEdge => ({ id: `${source}-${target}-${sourceHandle ?? ""}`, source, target, sourceHandle });
const graph = (nodes: GNode[], edges: GEdge[], settings = {}): Graph => ({ nodes, edges, settings: { ...DEFAULT_SETTINGS, ...settings } });
const errors = (g: Graph) => analyze(g).issues.filter((i) => i.level === "error").map((i) => i.message);
const warnings = (g: Graph) => analyze(g).issues.filter((i) => i.level === "warning").map((i) => i.message);

const linear = () => graph([node("start", "__start__"), node("llm", "assistant"), node("end", "__end__")], [edge("start", "assistant"), edge("assistant", "end")]);

describe("analyze", () => {
  it.each(PATTERNS.map((p) => [p.id, p] as const))("패턴 %s 은 구조 오류가 없다", (_, p) => {
    const a = analyze(p.graph);
    expect(a.issues.filter((i) => i.level === "error")).toEqual([]);
    expect(a.ok).toBe(true);
  });

  it("단순 선형 그래프는 통과한다", () => {
    expect(errors(linear())).toEqual([]);
  });

  it("START / END 가 없으면 오류", () => {
    const g = graph([node("llm", "a")], []);
    expect(errors(g)).toEqual(expect.arrayContaining([expect.stringContaining("START 노드가 없습니다"), expect.stringContaining("END 노드가 없습니다")]));
    expect(analyze(g).ok).toBe(false);
  });

  it("나가는 엣지가 없는 노드(dead end)를 찾는다", () => {
    const g = graph([node("start", "__start__"), node("llm", "a"), node("llm", "b"), node("end", "__end__")], [edge("start", "a"), edge("a", "b"), edge("a", "end")]);
    expect(errors(g).some((m) => m.includes("'b' 에서 나가는 엣지가 없습니다"))).toBe(true);
  });

  it("START 에서 도달할 수 없는 노드를 찾는다", () => {
    const g = graph(
      [node("start", "__start__"), node("llm", "a"), node("llm", "island"), node("end", "__end__")],
      [edge("start", "a"), edge("a", "end"), edge("island", "end")],
    );
    expect(errors(g).join("\n")).toMatch(/island/);
  });

  it("자기 자신으로 무조건 돌아가는 무한 루프를 찾는다", () => {
    const g = linear();
    g.edges.push(edge("assistant", "assistant"));
    expect(errors(g).some((m) => m.includes("무한 루프"))).toBe(true);
  });

  it("종료 조건 없는 사이클을 찾는다", () => {
    const g = graph(
      [node("start", "__start__"), node("llm", "a"), node("llm", "b"), node("end", "__end__")],
      [edge("start", "a"), edge("a", "b"), edge("b", "a")],
    );
    expect(errors(g).length).toBeGreaterThan(0);
  });

  it.each([["1abc"], ["my-node"], ["class"], ["한글"], ["x y"]])("잘못된 Python 식별자 %s 를 막는다 (코드 주입 방지)", (name) => {
    const g = linear();
    g.nodes[1].data.name = name;
    expect(errors(g).some((m) => m.includes("올바른 Python 식별자가 아닙니다"))).toBe(true);
  });

  it("예약어와 중복 이름을 막는다", () => {
    const g = linear();
    g.nodes[1].data.name = "graph";
    expect(errors(g).some((m) => m.includes("예약된 이름"))).toBe(true);

    const dup = graph(
      [node("start", "__start__"), node("llm", "same"), { ...node("llm", "same"), id: "same2" }, node("end", "__end__")],
      [edge("start", "same"), edge("same", "same2"), edge("same2", "end")],
    );
    expect(errors(dup).some((m) => m.includes("중복"))).toBe(true);
  });

  it("END 에서 나가거나 START 로 들어가는 엣지를 막는다", () => {
    const g = linear();
    g.edges.push(edge("end", "assistant"), edge("assistant", "start"));
    const m = errors(g).join("\n");
    expect(m).toMatch(/END 에서 나가는 엣지/);
    expect(m).toMatch(/START 로 들어가는 엣지/);
  });

  it("도구가 없는 Tools 노드는 오류, tools_condition 없이 붙은 Tools 노드는 경고", () => {
    const g = graph(
      [node("start", "__start__"), node("llm", "agent"), node("tools", "tools", { tools: [] }), node("end", "__end__")],
      [edge("start", "agent"), edge("agent", "tools"), edge("tools", "end")],
    );
    expect(errors(g).some((m) => m.includes("도구가 하나도 없습니다"))).toBe(true);
    expect(warnings(g).some((m) => m.includes("tools_condition 라우터가 없습니다"))).toBe(true);
  });

  it("Human 노드는 Checkpointer 가 필요하다", () => {
    const g = graph(
      [node("start", "__start__"), node("human", "approve"), node("end", "__end__")],
      [edge("start", "approve"), edge("approve", "end", "approve"), edge("approve", "end", "reject")],
      { checkpointer: "none" },
    );
    expect(errors(g).some((m) => m.includes("Checkpointer"))).toBe(true);
  });
});
