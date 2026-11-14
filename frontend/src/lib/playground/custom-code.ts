// 그래프 안에 사용자가 직접 쓴 Python 코드가 있는 Function 노드를 찾는다.
// 공유받은 프로젝트를 내 API 키로 실행하기 전에 확인을 받는 데 쓴다.
import { defaultData } from "./catalog.ts";
import { PATTERNS } from "./patterns.ts";
import type { Graph } from "./types.ts";

const norm = (code?: string) => (code ?? "").trim();

/** 기본값이나 내장 패턴에 들어 있는 코드는 안전한 것으로 본다. */
const KNOWN = new Set([norm(defaultData("function").code), ...PATTERNS.flatMap((p) => p.graph.nodes.filter((n) => n.kind === "function").map((n) => norm(n.data.code)))]);

export function customCodeNodes(graph: Graph): string[] {
  return graph.nodes.filter((n) => n.kind === "function" && !KNOWN.has(norm(n.data.code))).map((n) => n.data.name);
}
