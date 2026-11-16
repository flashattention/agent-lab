// 패턴의 생성 결과(백엔드 통합 테스트·eval 입력). 스크립트와 테스트에서만 쓴다.
import { analyze } from "./analyze.ts";
import { GENERATOR_VERSION, generateProject, normalizeGraph } from "./codegen.ts";
import { PATTERNS } from "./patterns.ts";

export const FIXTURE_PATH = new URL("../../../../backend/tests/fixtures/patterns.json", import.meta.url).pathname;

export function buildPatternFixture() {
  return {
    generator: GENERATOR_VERSION,
    patterns: PATTERNS.map((p) => {
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
    }),
  };
}
