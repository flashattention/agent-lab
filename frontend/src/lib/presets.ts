"use client";

// 에이전트 프리셋: 만들어 둔 에이전트(그래프)를 저장해 두었다가 다른 그래프에서 Sub-agent 로 불러온다.
// 로그인하면 Supabase(agent_presets 테이블)에, 아니면 이 브라우저(localStorage)에 저장한다.
import { create } from "zustand";
import type { SubGraph } from "@/lib/playground/types";
import { PATTERNS } from "@/lib/playground/patterns";
import { TOOL_LIBRARY } from "@/lib/playground/catalog";
import { allNodes, pyIdent } from "@/lib/playground/subgraph";
import { useAuth } from "./auth";
import { supabase, SUPABASE_ENABLED } from "./supabase";

export type PresetSource = "cloud" | "local" | "builtin" | "market";
export type Visibility = "private" | "link" | "public";

export const MARKET_CATEGORIES = ["리서치", "고객지원", "글쓰기", "데이터 분석", "RAG", "코딩", "업무 자동화", "기타"] as const;

export type AgentPreset = {
  id: string;
  name: string; // 표시 이름
  node_name: string; // Sub-agent 로 넣을 때 기본 노드 이름 (파이썬 식별자)
  description: string; // 역할 설명 — Supervisor 가 워커를 고를 때 참고한다
  graph: SubGraph;
  updated_at: string;
  source: PresetSource;
  category?: string;
  // 계정·마켓 프리셋에만 있는 값
  owner?: string;
  visibility?: Visibility;
  author_name?: string;
  tags?: string[];
  installs?: number;
  declarative?: boolean;
  forked_from?: string | null;
  published_at?: string | null;
};

export type PresetDraft = { name: string; node_name: string; description: string; graph: SubGraph; category?: string; forked_from?: string | null };

const LOCAL_KEY = "agentlab-presets";
// string 으로 두어 supabase-js 가 열 목록마다 다른 행 타입을 추론하지 않게 한다
const BASE_COLUMNS: string = "id, name, node_name, description, graph, updated_at";
const COLUMNS: string = `${BASE_COLUMNS}, owner, visibility, author_name, category, tags, installs, declarative, forked_from, published_at`;
const SCHEMA_HINT = "에이전트 마켓을 쓰려면 supabase/schema.sql 을 다시 실행해 주세요.";

/** 패턴 갤러리의 설계를 그대로 Sub-agent 로 쓸 수 있게 기본 제공한다. */
export const BUILTIN_PRESETS: AgentPreset[] = PATTERNS.map((p) => ({
  id: `builtin:${p.id}`,
  name: p.title,
  node_name: pyIdent(p.id.replace(/-/g, "_"), "sub_agent"),
  description: p.summary,
  graph: { nodes: p.graph.nodes, edges: p.graph.edges },
  updated_at: "",
  source: "builtin",
  category: p.category,
}));

function readLocal(): AgentPreset[] {
  try {
    const raw = JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]") as Omit<AgentPreset, "source">[];
    return raw.map((p) => ({ ...p, source: "local" as const }));
  } catch {
    return [];
  }
}
function writeLocal(items: AgentPreset[]) {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(items.map(({ source, ...p }) => (void source, p))));
  } catch {}
}

// 스키마 누락은 메시지 단어가 아니라 오류 코드로만 판정한다 (권한·로그인·RLS 오류를 '스키마 다시 실행'으로 덮지 않도록)
type PgError = { code?: string; message: string };
const MISSING_TABLE = new Set(["42P01", "PGRST205"]); // 테이블 없음 (Postgres / PostgREST 스키마 캐시)
const MISSING_SCHEMA = new Set([...MISSING_TABLE, "42703", "42883", "PGRST202", "PGRST204"]); // + 열·함수 없음
export const isMissingTable = (e?: PgError | null) => !!e && MISSING_TABLE.has(e.code ?? "");
export const isMissingSchema = (e?: PgError | null) => !!e && MISSING_SCHEMA.has(e.code ?? "");
/** 화면에 보일 오류: 스키마 누락이면 안내와 원래 메시지를 함께, 아니면 원래 메시지 그대로 */
export const explainError = (e: PgError) => (isMissingSchema(e) ? `${SCHEMA_HINT} (원인: ${e.message})` : e.message);
const toCloud = (p: unknown, source: PresetSource = "cloud") => ({ ...(p as Omit<AgentPreset, "source">), source }) as AgentPreset;
const cloudEnabled = () => SUPABASE_ENABLED && !!useAuth.getState().user;

type PresetState = {
  items: AgentPreset[]; // 내 프리셋 (클라우드 + 브라우저)
  loading: boolean;
  error: string;
  tableMissing: boolean; // 계정 저장소(agent_presets)가 없어 이 브라우저에 저장하는 중
  load: () => Promise<void>;
  save: (draft: PresetDraft, overwriteId?: string) => Promise<AgentPreset>;
  remove: (p: AgentPreset) => Promise<void>;
  find: (id: string) => AgentPreset | undefined;
  setVisibility: (p: AgentPreset, visibility: Visibility, category?: string) => Promise<AgentPreset>;
  fork: (p: AgentPreset) => Promise<AgentPreset>;
};

export const usePresets = create<PresetState>()((set, get) => ({
  items: [],
  loading: false,
  error: "",
  tableMissing: false,
  find: (id) => get().items.find((p) => p.id === id) ?? BUILTIN_PRESETS.find((p) => p.id === id),

  load: async () => {
    const local = readLocal();
    if (!cloudEnabled()) return set({ items: local, error: "", tableMissing: false });
    set({ loading: true });
    // 공개 프리셋도 읽을 수 있으므로 내 것만 거른다
    const owner = useAuth.getState().user!.id;
    let res = await supabase().from("agent_presets").select(COLUMNS).eq("owner", owner).order("updated_at", { ascending: false });
    if (isMissingSchema(res.error) && !isMissingTable(res.error)) res = await supabase().from("agent_presets").select(BASE_COLUMNS).eq("owner", owner).order("updated_at", { ascending: false });
    if (!res.error) set({ items: [...(res.data ?? []).map((p) => toCloud(p)), ...local], error: "", tableMissing: false });
    else if (isMissingTable(res.error))
      set({ items: local, tableMissing: true, error: `계정 저장소(agent_presets 테이블)가 없어 이 브라우저에 저장합니다. supabase/schema.sql 을 실행하세요. (원인: ${res.error.message})` });
    else set({ items: local, tableMissing: false, error: `계정 프리셋을 불러오지 못했습니다: ${res.error.message}` });
    set({ loading: false });
  },

  save: async (draft, overwriteId) => {
    const body = { name: draft.name.trim().slice(0, 80) || "이름 없는 에이전트", node_name: pyIdent(draft.node_name), description: draft.description.trim().slice(0, 500), graph: draft.graph };
    const extra = { ...(draft.category ? { category: draft.category } : {}), ...(draft.forked_from ? { forked_from: draft.forked_from } : {}) };
    const target = overwriteId ? get().items.find((p) => p.id === overwriteId) : undefined;
    const toLocal = () => {
      const now = new Date().toISOString();
      const all = readLocal();
      const made: AgentPreset = { ...body, id: target?.source === "local" ? target.id : `local:${Math.random().toString(36).slice(2, 10)}`, updated_at: now, source: "local" };
      writeLocal([made, ...all.filter((p) => p.id !== made.id)]);
      return made;
    };
    let made: AgentPreset;
    if (cloudEnabled() && target?.source !== "local" && !get().tableMissing) {
      const send = (withExtra: boolean, cols: string) => {
        const b = withExtra ? { ...body, ...extra } : body;
        const q = target ? supabase().from("agent_presets").update(b).eq("id", target.id) : supabase().from("agent_presets").insert(b);
        return q.select(cols).single();
      };
      let res = await send(true, COLUMNS);
      // 마켓 열이 아직 없는 DB(이전 스키마)에서는 기본 열만으로 저장한다
      if (isMissingSchema(res.error) && !isMissingTable(res.error)) res = await send(false, BASE_COLUMNS);
      if (isMissingTable(res.error)) made = toLocal();
      else if (res.error) throw new Error(explainError(res.error));
      else made = toCloud(res.data);
    } else made = toLocal();
    set({ items: [made, ...get().items.filter((p) => p.id !== made.id)] });
    return made;
  },

  remove: async (p) => {
    if (p.source === "builtin") return;
    if (p.source === "cloud") {
      const { error } = await supabase().from("agent_presets").delete().eq("id", p.id);
      if (error) throw new Error(error.message);
    } else writeLocal(readLocal().filter((x) => x.id !== p.id));
    set({ items: get().items.filter((x) => x.id !== p.id) });
  },

  setVisibility: async (p, visibility, category) => {
    if (p.source !== "cloud") throw new Error("공유하려면 로그인한 뒤 계정에 저장된 프리셋이어야 합니다.");
    if (visibility === "public" && !isDeclarative(p.graph))
      throw new Error("Function 노드나 커스텀 도구가 들어 있는 프리셋은 공개 갤러리에 올릴 수 없습니다. 링크 공유는 가능합니다.");
    const patch = { visibility, ...(category ? { category } : {}) };
    const { data, error } = await supabase().from("agent_presets").update(patch).eq("id", p.id).select(COLUMNS).single();
    if (error) throw new Error(/public_declarative/.test(error.message) ? "선언형 프리셋만 공개할 수 있습니다." : explainError(error));
    const made = toCloud(data);
    set({ items: get().items.map((x) => (x.id === made.id ? made : x)) });
    return made;
  },

  /** 남의 (공유·공개) 프리셋을 내 프리셋으로 복제한다 */
  fork: async (p) => {
    const made = await get().save({ name: p.name, node_name: p.node_name, description: p.description, graph: p.graph, category: p.category, forked_from: p.source === "market" ? p.id : null });
    if (p.source === "market") recordInstall(p.id);
    return made;
  },
}));

/* ------------------------------------------------------------------ 마켓 */

const BUILTIN_TOOLS = new Set(Object.keys(TOOL_LIBRARY));

/** 실행되는 사용자 코드가 없는 그래프인지 (DB 의 agentlab_is_declarative 와 같은 규칙) */
export function isDeclarative(g: SubGraph): boolean {
  if (g.tools?.length) return false;
  return allNodes(g).every((n) => n.kind !== "function" && (n.data.tools ?? []).every((t) => BUILTIN_TOOLS.has(t)));
}

export const shareLink = (id: string) => `${window.location.origin}/agents?id=${id}`;

export type MarketQuery = { sort: "popular" | "recent"; category?: string };

/** 공개 갤러리 목록. 검색은 화면에서 거른다 (수가 많아지면 서버 검색으로 옮긴다). */
export async function listMarket(q: MarketQuery): Promise<AgentPreset[]> {
  let req = supabase().from("agent_presets").select(COLUMNS).eq("visibility", "public").eq("hidden", false);
  if (q.category) req = req.eq("category", q.category);
  req = q.sort === "popular" ? req.order("installs", { ascending: false }).order("published_at", { ascending: false }) : req.order("published_at", { ascending: false });
  const { data, error } = await req.limit(200);
  if (error) throw new Error(explainError(error));
  return (data ?? []).map((p) => toCloud(p, "market"));
}

/** 링크로 공유된(또는 공개된) 프리셋 하나. 로그인 없이도 읽는다. */
export async function getSharedPreset(id: string): Promise<AgentPreset | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const { data, error } = await supabase().rpc("get_shared_preset", { p_id: id });
  if (error) throw new Error(explainError(error));
  const row = (data as unknown[] | null)?.[0];
  return row ? toCloud(row, "market") : null;
}

/** 설치 수 기록 (로그인 사용자당 한 번, 실패해도 무시) */
export function recordInstall(id: string) {
  if (!cloudEnabled() || !/^[0-9a-f-]{36}$/i.test(id)) return;
  supabase()
    .rpc("record_preset_install", { p_id: id })
    .then(
      () => {},
      () => {},
    );
}

export async function reportPreset(id: string, reason: string) {
  const { error } = await supabase().from("agent_preset_reports").insert({ preset_id: id, reason: reason.trim().slice(0, 500) });
  if (error && !/duplicate key/i.test(error.message)) throw new Error(error.message);
}

/** 마켓에서 고른 프리셋을 플레이그라운드로 넘길 때 쓰는 임시 보관함 */
const PENDING_KEY = "agentlab-pending-preset";
export function setPendingPreset(p: AgentPreset) {
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(p));
  } catch {}
}
export function takePendingPreset(): AgentPreset | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    sessionStorage.removeItem(PENDING_KEY);
    return raw ? (JSON.parse(raw) as AgentPreset) : null;
  } catch {
    return null;
  }
}
