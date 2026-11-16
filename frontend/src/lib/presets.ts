"use client";

// 에이전트 프리셋: 만들어 둔 에이전트(그래프)를 저장해 두었다가 다른 그래프에서 Sub-agent 로 불러온다.
// 로그인하면 Supabase(agent_presets 테이블)에, 아니면 이 브라우저(localStorage)에 저장한다.
import { create } from "zustand";
import type { SubGraph } from "@/lib/playground/types";
import { PATTERNS } from "@/lib/playground/patterns";
import { pyIdent } from "@/lib/playground/subgraph";
import { useAuth } from "./auth";
import { supabase, SUPABASE_ENABLED } from "./supabase";

export type PresetSource = "cloud" | "local" | "builtin";

export type AgentPreset = {
  id: string;
  name: string; // 표시 이름
  node_name: string; // Sub-agent 로 넣을 때 기본 노드 이름 (파이썬 식별자)
  description: string; // 역할 설명 — Supervisor 가 워커를 고를 때 참고한다
  graph: SubGraph;
  updated_at: string;
  source: PresetSource;
  category?: string;
};

export type PresetDraft = { name: string; node_name: string; description: string; graph: SubGraph };

const LOCAL_KEY = "agentlab-presets";
const COLUMNS = "id, name, node_name, description, graph, updated_at";

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

const missingTable = (msg: string) => /agent_presets|relation .* does not exist|schema cache/i.test(msg);
const cloudEnabled = () => SUPABASE_ENABLED && !!useAuth.getState().user;

type PresetState = {
  items: AgentPreset[]; // 내 프리셋 (클라우드 + 브라우저)
  loading: boolean;
  error: string;
  load: () => Promise<void>;
  save: (draft: PresetDraft, overwriteId?: string) => Promise<AgentPreset>;
  remove: (p: AgentPreset) => Promise<void>;
  find: (id: string) => AgentPreset | undefined;
};

export const usePresets = create<PresetState>()((set, get) => ({
  items: [],
  loading: false,
  error: "",
  find: (id) => get().items.find((p) => p.id === id) ?? BUILTIN_PRESETS.find((p) => p.id === id),

  load: async () => {
    const local = readLocal();
    if (!cloudEnabled()) return set({ items: local, error: "" });
    set({ loading: true });
    try {
      const { data, error } = await supabase().from("agent_presets").select(COLUMNS).order("updated_at", { ascending: false });
      if (error) throw new Error(error.message);
      set({ items: [...(data ?? []).map((p) => ({ ...(p as Omit<AgentPreset, "source">), source: "cloud" as const })), ...local], error: "" });
    } catch (e) {
      const msg = (e as Error).message;
      set({ items: local, error: missingTable(msg) ? "계정 저장소(agent_presets 테이블)가 아직 없어 이 브라우저에 저장합니다. supabase/schema.sql 을 다시 실행하세요." : msg });
    } finally {
      set({ loading: false });
    }
  },

  save: async (draft, overwriteId) => {
    const body = { name: draft.name.trim().slice(0, 80) || "이름 없는 에이전트", node_name: pyIdent(draft.node_name), description: draft.description.trim().slice(0, 500), graph: draft.graph };
    const target = overwriteId ? get().items.find((p) => p.id === overwriteId) : undefined;
    const toLocal = () => {
      const now = new Date().toISOString();
      const all = readLocal();
      const made: AgentPreset = { ...body, id: target?.source === "local" ? target.id : `local:${Math.random().toString(36).slice(2, 10)}`, updated_at: now, source: "local" };
      writeLocal([made, ...all.filter((p) => p.id !== made.id)]);
      return made;
    };
    let made: AgentPreset;
    if (cloudEnabled() && target?.source !== "local" && !get().error) {
      try {
        const q = target ? supabase().from("agent_presets").update(body).eq("id", target.id) : supabase().from("agent_presets").insert(body);
        const { data, error } = await q.select(COLUMNS).single();
        if (error) throw new Error(error.message);
        made = { ...(data as Omit<AgentPreset, "source">), source: "cloud" };
      } catch (e) {
        if (!missingTable((e as Error).message)) throw e;
        made = toLocal();
      }
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
}));
