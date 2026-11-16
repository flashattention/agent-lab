// 패턴의 생성 결과(백엔드 통합 테스트·eval 입력). 스크립트와 테스트에서만 쓴다.
import { analyze } from "./analyze.ts";
import { GENERATOR_VERSION, generateProject, normalizeGraph } from "./codegen.ts";
import { PATTERNS } from "./patterns.ts";
import type { Graph } from "./types.ts";

export const FIXTURE_PATH = new URL("../../../../backend/tests/fixtures/patterns.json", import.meta.url).pathname;

/** 패턴 외에 실행까지 검증할 그래프: 승인 미들웨어만으로 환불을 승인하는 Agent (interrupt → decisions 재개) */
function extraCases(): { id: string; title: string; category: string; graph: Graph }[] {
  const hitl = PATTERNS.find((p) => p.id === "hitl")!.graph;
  const nodes = hitl.nodes
    .filter((n) => n.kind !== "human")
    .map((n) => (n.data.name === "executor" ? { ...n, data: { ...n.data, middleware: { hitl: { tools: ["issue_refund"] } } } } : n));
  const edges = [...hitl.edges.filter((e) => e.source !== "approval" && e.target !== "approval"), { id: "e-direct", source: "support_agent", target: "executor", sourceHandle: null }];
  return [{ id: "hitl-middleware", title: "승인 미들웨어 Agent", category: "프로덕션", graph: { ...hitl, nodes, edges } }];
}

const entry = (p: { id: string; title: string; category: string; graph: Graph }) => {
  const a = analyze(p.graph);
  return {
    id: p.id,
    title: p.title,
    category: p.category,
    nodes: p.graph.nodes.filter((n) => n.kind !== "start" && n.kind !== "end").map((n) => ({ name: n.data.name, kind: n.kind })),
    analysis: { errors: a.issues.filter((i) => i.level === "error").length, warnings: a.issues.filter((i) => i.level === "warning").length },
    files: generateProject(p.graph),
    graph: normalizeGraph(p.graph), // 고도화 요청과 같은 형태 (eval_refine.py 입력)
  };
};

export function buildPatternFixture() {
  return {
    generator: GENERATOR_VERSION,
    patterns: PATTERNS.map(entry),
    cases: extraCases().map(entry), // eval 은 patterns 만 쓰고, 통합 테스트는 둘 다 실행한다
  };
}
