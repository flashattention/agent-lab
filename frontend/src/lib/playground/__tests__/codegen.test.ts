import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { generateProject, normalizeGraph } from "../codegen";
import { buildPatternFixture, FIXTURE_PATH } from "../fixture";
import { PATTERNS } from "../patterns";

describe("generateProject", () => {
  it.each(PATTERNS.map((p) => [p.id, p] as const))("패턴 %s 의 생성 결과가 스냅샷과 같다", (_, p) => {
    expect(generateProject(p.graph)).toMatchSnapshot();
  });

  it.each(PATTERNS.map((p) => [p.id, p] as const))("패턴 %s 는 실행 가능한 프로젝트 구조를 만든다", (_, p) => {
    const files = generateProject(p.graph);
    for (const f of ["main.py", "agent/__init__.py", "agent/graph.py", "agent/state.py", "agent/config.py", "requirements.txt", "langgraph.json"]) {
      expect(files).toHaveProperty([f]);
    }
    // 실제 노드마다 파일이 하나씩 생긴다
    for (const n of p.graph.nodes) {
      if (["start", "end", "router", "evaluator", "map"].includes(n.kind)) continue;
      expect(Object.keys(files).some((f) => f.includes(n.data.name))).toBe(true);
    }
    expect(files["agent/graph.py"]).toContain("StateGraph(");
    expect(files["agent/graph.py"]).toMatch(/\.compile\(/);
  });

  it("프롬프트의 따옴표·줄바꿈·삼중따옴표를 안전하게 문자열로 넣는다 (코드 주입 방지)", () => {
    const p = structuredClone(PATTERNS[0]);
    const llm = p.graph.nodes.find((n) => n.kind === "llm" || n.kind === "agent")!;
    const evil = 'x"""\nimport os; os.system("rm -rf /")\n"""';
    llm.data.prompt = evil;
    const code = Object.values(generateProject(p.graph)).join("\n");
    expect(code).not.toContain('\nimport os; os.system("rm -rf /")\n');
    expect(code).toContain(JSON.stringify(evil));
  });

  it("좌표와 임의 id 는 캐시 키(normalizeGraph)에 영향을 주지 않는다", () => {
    const a = structuredClone(PATTERNS[0].graph);
    const b = structuredClone(PATTERNS[0].graph);
    b.nodes.forEach((n, i) => (n.position = { x: i * 999, y: -i }));
    expect(JSON.stringify(normalizeGraph(a))).toBe(JSON.stringify(normalizeGraph(b)));
  });
});

describe("pattern fixture", () => {
  it("백엔드 통합 테스트용 fixture 가 최신이다 (다르면 node scripts/export-patterns.ts)", () => {
    const committed = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
    expect(committed).toEqual(JSON.parse(JSON.stringify(buildPatternFixture())));
  });
});

describe("customCodeNodes", () => {
  it("기본·내장 패턴 코드는 무시하고, 직접 고친 Function 노드만 찾는다", async () => {
    const { customCodeNodes } = await import("../custom-code");
    for (const p of PATTERNS) expect(customCodeNodes(p.graph)).toEqual([]);
    const p = structuredClone(PATTERNS.find((x) => x.graph.nodes.some((n) => n.kind === "function"))!);
    const fn = p.graph.nodes.find((n) => n.kind === "function")!;
    fn.data.code = "import os\nreturn {}";
    expect(customCodeNodes(p.graph)).toEqual([fn.data.name]);
  });
});
