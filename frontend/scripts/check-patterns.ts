// 모든 패턴에 대해: 구조 분석 → 코드 생성 → 백엔드 /api/validate (ruff + Mock 실행)
import { PATTERNS } from "../src/lib/playground/patterns.ts";
import { generateProject } from "../src/lib/playground/codegen.ts";
import { analyze } from "../src/lib/playground/analyze.ts";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

const API = process.env.API ?? "http://localhost:8000";
const only = process.argv[2];
let fails = 0;
for (const p of PATTERNS.filter((x) => !only || x.id === only)) {
  const a = analyze(p.graph);
  const files = generateProject(p.graph);
  const out = join(process.env.OUT ?? join(tmpdir(), "agentlab-patterns"), p.id);
  for (const [f, c] of Object.entries(files)) { mkdirSync(dirname(join(out, f)), { recursive: true }); writeFileSync(join(out, f), c); }
  const res = await fetch(`${API}/api/validate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ files }) });
  const r = await res.json();
  const errs = a.issues.filter((i) => i.level === "error");
  const ok = r.ok && errs.length === 0;
  if (!ok) fails++;
  console.log(`${ok ? "✅" : "❌"} ${p.id}  analysis: ${errs.length} err / ${a.issues.filter((i) => i.level === "warning").length} warn  validate: ${r.ok ? "ok" : "FAIL"} (${r.run?.duration_ms ?? "-"}ms)`);
  for (const i of a.issues.filter((i) => i.level !== "info")) console.log(`     ${i.level}: ${i.message}`);
  if (!r.ok) console.log(JSON.stringify(r.lint).slice(0, 800), "\n", (r.run?.stderr ?? "").slice(-1500));
}
process.exit(fails ? 1 : 0);
