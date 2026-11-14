import { describe, expect, it } from "vitest";
import { edgeLabel, toViewEdges, toViewNodes } from "../view-model";
import type { FlowNode } from "../store";

const n = (id: string, kind: string, name = id) => ({ id, type: "agent", position: { x: 0, y: 0 }, data: { kind, name } }) as unknown as FlowNode;
const empty = { errorNodes: new Set<string>(), warnNodes: new Set<string>(), errorEdges: new Set<string>(), warnEdges: new Set<string>() };

describe("edgeLabel", () => {
  it.each([
    [n("r", "router"), n("a", "llm", "writer"), null, "writer"],
    [n("r", "router"), n("end", "end"), null, "END"],
    [n("e", "evaluator"), n("a", "llm"), "pass", "pass"],
    [n("h", "human"), n("a", "llm"), "approve", "승인"],
    [n("h", "human"), n("a", "llm"), "reject", "거절"],
    [n("m", "map"), n("w", "llm"), null, "Send(…)"],
    [n("a", "llm"), n("b", "llm"), null, undefined],
  ])("%o → %o (%s) = %s", (src, tgt, handle, label) => {
    expect(edgeLabel(src, tgt, handle)).toBe(label);
  });
});

describe("toViewEdges / toViewNodes", () => {
  const nodes = [n("r", "router"), n("a", "llm"), n("end", "end")];
  const edges = [
    { id: "e1", source: "r", target: "a" },
    { id: "e2", source: "a", target: "end" },
  ];

  it("조건부 엣지는 애니메이션, 오류 엣지는 빨간 화살표", () => {
    const v = toViewEdges(nodes, edges, { ...empty, errorEdges: new Set(["e2"]) });
    expect(v[0]).toMatchObject({ animated: true, label: "a", className: "edge-conditional" });
    expect(v[1]).toMatchObject({ animated: true, className: "edge-error" });
    expect((v[1].markerEnd as { color: string }).color).toBe("var(--danger)");
  });

  it("노드에 구조 상태와 실행 상태를 붙인다", () => {
    const v = toViewNodes(nodes, { ...empty, errorNodes: new Set(["a"]) }, new Map([["a", { status: "running" as const, runs: 1 }]]));
    expect(v[1].data).toMatchObject({ __status: "error", __run: { status: "running", runs: 1 } });
    expect(v[0].data).toMatchObject({ __status: "ok" });
  });
});
