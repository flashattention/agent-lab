import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { TOOL_LIBRARY } from "../playground/catalog";
import { PATTERNS } from "../playground/patterns";
import type { SubGraph } from "../playground/types";
import { explainError, isDeclarative, isMissingSchema, isMissingTable } from "../presets";

const tools = (names: string[]): SubGraph => ({ nodes: [{ id: "t", kind: "tools", data: { name: "t", tools: names }, position: { x: 0, y: 0 } }], edges: [] });

describe("isDeclarative (공개 갤러리 조건)", () => {
  it("기본 도구만 쓰면 선언형, Function·커스텀 도구·모르는 도구가 있으면 아니다", () => {
    expect(isDeclarative(tools(["web_search", "calculator"]))).toBe(true);
    expect(isDeclarative(tools(["rm_rf"]))).toBe(false);
    expect(isDeclarative({ ...tools(["my_tool"]), tools: [{ name: "my_tool", description: "", code: "@tool" }] })).toBe(false);
    const nested: SubGraph = {
      nodes: [{ id: "s", kind: "subgraph", data: { name: "s", graph: { nodes: [{ id: "f", kind: "function", data: { name: "f", code: "return {}" }, position: { x: 0, y: 0 } }], edges: [] } }, position: { x: 0, y: 0 } }],
      edges: [],
    };
    expect(isDeclarative(nested)).toBe(false);
  });

  it("Function 노드가 없는 기본 패턴은 공개할 수 있다", () => {
    for (const p of PATTERNS) expect(isDeclarative(p.graph)).toBe(!p.graph.nodes.some((n) => n.kind === "function"));
  });

  it("DB 함수(agentlab_is_declarative)의 기본 도구 목록이 catalog.ts 와 같다", () => {
    const sql = readFileSync(join(__dirname, "../../../../supabase/schema.sql"), "utf8");
    const fn = sql.slice(sql.indexOf("function public.agentlab_is_declarative"), sql.indexOf("$$;", sql.indexOf("function public.agentlab_is_declarative")));
    const inSql = [...fn.matchAll(/@ == "([a-z_]+)"/g)].map((m) => m[1]).filter((t) => t !== "function");
    expect(new Set(inSql)).toEqual(new Set(Object.keys(TOOL_LIBRARY)));
  });
});

describe("스키마 누락 판정 (오류 코드 기준)", () => {
  it("권한·RLS·로그인 오류는 '스키마 다시 실행' 안내로 덮지 않고 원래 메시지를 보여 준다", () => {
    for (const e of [
      { code: "42501", message: "permission denied for table agent_presets" },
      { code: "42501", message: 'new row violates row-level security policy for table "agent_presets"' },
      { code: "PGRST301", message: "JWT expired" },
      { code: "23514", message: 'new row for relation "agent_presets" violates check constraint "agent_presets_public_declarative"' },
    ]) {
      expect(isMissingSchema(e)).toBe(false);
      expect(explainError(e)).toBe(e.message);
    }
  });

  it("열·함수·테이블이 정말 없을 때만 안내하고, 원인도 함께 보여 준다", () => {
    const col = { code: "PGRST204", message: "Could not find the 'visibility' column of 'agent_presets' in the schema cache" };
    expect(isMissingSchema(col)).toBe(true);
    expect(isMissingTable(col)).toBe(false);
    expect(explainError(col)).toContain("schema.sql");
    expect(explainError(col)).toContain(col.message);
    expect(isMissingTable({ code: "42P01", message: 'relation "public.agent_presets" does not exist' })).toBe(true);
    expect(isMissingSchema({ code: "PGRST202", message: "Could not find the function public.get_shared_preset(p_id)" })).toBe(true);
  });
});
