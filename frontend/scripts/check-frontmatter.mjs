import matter from "gray-matter";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : [join(d, f)]));
let bad = 0;
for (const f of walk("content").filter((f) => f.endsWith(".md"))) {
  try { matter(readFileSync(f, "utf8"), { cache: false }); } catch (e) { bad++; console.log("BAD", f, e.reason, "line", e.mark?.line); }
}
console.log("bad:", bad);
