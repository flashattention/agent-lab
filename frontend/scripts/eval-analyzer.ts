// 구조 분석기 eval: 정상 패턴에 결함을 주입했을 때 실행 전에 잡아내는지(검출률),
// 동작에 영향 없는 변경을 오류로 잘못 잡지 않는지(오탐률)를 잰다.
//   npx vite-node scripts/eval-analyzer.ts [out.json]
import { writeFileSync } from "node:fs";
import { analyze } from "../src/lib/playground/analyze.ts";
import { generateProject } from "../src/lib/playground/codegen.ts";
import { PATTERNS } from "../src/lib/playground/patterns.ts";
import type { Graph } from "../src/lib/playground/types.ts";

type Mutation = { id: string; label: string; defect: boolean; apply: (g: Graph) => boolean };

const real = (g: Graph) => g.nodes.filter((n) => n.kind !== "start" && n.kind !== "end");
const endId = (g: Graph) => g.nodes.find((n) => n.kind === "end")?.id;
const startId = (g: Graph) => g.nodes.find((n) => n.kind === "start")?.id;

const MUTATIONS: Mutation[] = [
  { id: "cut-end", label: "END 로 가는 엣지를 모두 끊음 (출구 없음)", defect: true, apply: (g) => { const e = endId(g); const before = g.edges.length; g.edges = g.edges.filter((x) => x.target !== e); return g.edges.length < before; } },
  { id: "self-loop", label: "노드가 자기 자신으로 무조건 돌아감 (무한 루프)", defect: true, apply: (g) => { const n = real(g).find((x) => !["router", "evaluator", "supervisor", "map", "human"].includes(x.kind)); if (!n) return false; g.edges.push({ id: "m-self", source: n.id, target: n.id }); return true; } },
  { id: "bad-ident", label: "노드 이름을 잘못된 Python 식별자로 (코드 주입·문법 오류)", defect: true, apply: (g) => { const n = real(g)[0]; n.data.name = "bad-name; import os"; return true; } },
  { id: "dup-name", label: "두 노드 이름이 중복", defect: true, apply: (g) => { const r = real(g); if (r.length < 2) return false; r[1].data.name = r[0].data.name; return true; } },
  { id: "unreachable", label: "START 에서 나가는 엣지 제거 (도달 불가)", defect: true, apply: (g) => { const s = startId(g); const before = g.edges.length; g.edges = g.edges.filter((x) => x.source !== s); return g.edges.length < before; } },
  { id: "no-start", label: "START 노드 삭제", defect: true, apply: (g) => { const s = startId(g); g.nodes = g.nodes.filter((n) => n.id !== s); g.edges = g.edges.filter((x) => x.source !== s); return true; } },
  { id: "empty-tools", label: "Tools 노드의 도구를 모두 제거", defect: true, apply: (g) => { const t = g.nodes.find((n) => n.kind === "tools"); if (!t) return false; t.data.tools = []; return true; } },
  { id: "end-out", label: "END 에서 나가는 엣지 추가", defect: true, apply: (g) => { const e = endId(g); const n = real(g)[0]; if (!e || !n) return false; g.edges.push({ id: "m-endout", source: e, target: n.id }); return true; } },
  { id: "dangling", label: "어디에도 연결되지 않은 노드 추가", defect: true, apply: (g) => { const base = real(g)[0]; g.nodes.push({ ...structuredClone(base), id: "m-orphan", data: { ...structuredClone(base.data), name: "orphan_node" } }); return true; } },
  { id: "no-checkpointer", label: "Human 노드가 있는데 Checkpointer 끔", defect: true, apply: (g) => { if (!g.nodes.some((n) => n.kind === "human")) return false; g.settings.checkpointer = "none"; return true; } },
  // 동작에 영향 없는 변경 (오류가 나오면 오탐)
  { id: "move", label: "노드 위치 이동", defect: false, apply: (g) => { g.nodes.forEach((n, i) => (n.position = { x: i * 333, y: -i * 77 })); return true; } },
  { id: "rename", label: "노드 이름을 다른 올바른 이름으로", defect: false, apply: (g) => { const n = real(g)[0]; n.data.name = `${n.data.name}_v2`; return true; } },
  { id: "prompt", label: "프롬프트에 따옴표·줄바꿈 추가", defect: false, apply: (g) => { const n = real(g).find((x) => x.data.prompt !== undefined); if (!n) return false; n.data.prompt += '\n"인용" \'작은따옴표\' """삼중"""'; return true; } },
  { id: "demo-input", label: "데모 입력 변경", defect: false, apply: (g) => { g.settings.demoInput = "다른 질문입니다"; return true; } },
];

const errorsOf = (g: Graph) => analyze(g).issues.filter((i) => i.level === "error");

const cases: { pattern: string; mutation: string; defect: boolean; flagged: boolean; first?: string }[] = [];
// 분석기가 막지 않았다면 어떻게 됐을지 보기 위해, 결함 그래프로도 코드를 생성해 둔다 (백엔드 eval_defects.py 가 실행)
const defectProjects: { pattern: string; mutation: string; files?: Record<string, string>; codegenError?: string }[] = [];
for (const p of PATTERNS) {
  for (const m of MUTATIONS) {
    const g = structuredClone(p.graph);
    if (!m.apply(g)) continue; // 이 패턴에 적용할 수 없는 변형
    const errs = errorsOf(g);
    cases.push({ pattern: p.id, mutation: m.id, defect: m.defect, flagged: errs.length > 0, first: errs[0]?.message });
    if (m.defect) {
      try {
        defectProjects.push({ pattern: p.id, mutation: m.id, files: generateProject(g) });
      } catch (e) {
        defectProjects.push({ pattern: p.id, mutation: m.id, codegenError: String(e) });
      }
    }
  }
}

const byMutation = MUTATIONS.map((m) => {
  const cs = cases.filter((c) => c.mutation === m.id);
  const hit = cs.filter((c) => c.flagged === m.defect).length;
  return { id: m.id, label: m.label, defect: m.defect, cases: cs.length, correct: hit, rate: cs.length ? hit / cs.length : null, misses: cs.filter((c) => c.flagged !== m.defect).map((c) => c.pattern) };
});
const defects = cases.filter((c) => c.defect);
const benign = cases.filter((c) => !c.defect);
const summary = {
  patterns: PATTERNS.length,
  defect_cases: defects.length,
  detected: defects.filter((c) => c.flagged).length,
  recall: defects.filter((c) => c.flagged).length / defects.length,
  benign_cases: benign.length,
  false_positives: benign.filter((c) => c.flagged).length,
  false_positive_rate: benign.filter((c) => c.flagged).length / benign.length,
};

for (const m of byMutation) console.log(`${m.defect ? "결함" : "정상"}  ${m.id.padEnd(16)} ${m.correct}/${m.cases}  ${m.misses.length ? "놓침: " + m.misses.join(", ") : ""}`);
console.log(`\n검출률 ${summary.detected}/${summary.defect_cases} (${(summary.recall * 100).toFixed(1)}%) · 오탐 ${summary.false_positives}/${summary.benign_cases}`);
if (process.argv[2]) writeFileSync(process.argv[2], JSON.stringify({ summary, byMutation, cases }, null, 2) + "\n");
if (process.argv[3]) writeFileSync(process.argv[3], JSON.stringify(defectProjects) + "\n");
