"use client";

import type { Graph } from "@/lib/playground/types";
import { supabase } from "./supabase";

export type Project = {
  id: string;
  owner: string;
  name: string;
  graph: Graph;
  overrides: Record<string, string>;
  pattern_id: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectDraft = { name: string; graph: Graph; overrides?: Record<string, string>; pattern_id?: string | null };

const COLUMNS = "id, owner, name, graph, overrides, pattern_id, is_public, created_at, updated_at";

function fail(error: { message: string } | null): asserts error is null {
  if (error) throw new Error(error.message);
}

/** 내 프로젝트 목록 (최근 수정 순). 공개된 남의 프로젝트는 섞이지 않도록 owner 로 거른다. */
export async function listProjects(owner: string): Promise<Project[]> {
  const { data, error } = await supabase().from("projects").select(COLUMNS).eq("owner", owner).order("updated_at", { ascending: false });
  fail(error);
  return (data ?? []) as Project[];
}

/** 프로젝트 하나. 내 것이 아니고 공개도 아니면 null. */
export async function getProject(id: string): Promise<Project | null> {
  const { data, error } = await supabase().from("projects").select(COLUMNS).eq("id", id).maybeSingle();
  if (error && /invalid input syntax for type uuid/i.test(error.message)) return null;
  fail(error);
  return (data as Project | null) ?? null;
}

export async function createProject(draft: ProjectDraft): Promise<Project> {
  const { data, error } = await supabase()
    .from("projects")
    .insert({ name: draft.name, graph: draft.graph, overrides: draft.overrides ?? {}, pattern_id: draft.pattern_id ?? null })
    .select(COLUMNS)
    .single();
  fail(error);
  return data as Project;
}

export async function saveProject(id: string, patch: Partial<Pick<Project, "name" | "graph" | "overrides" | "pattern_id" | "is_public">>): Promise<void> {
  const { error } = await supabase().from("projects").update(patch).eq("id", id);
  fail(error);
}

export async function deleteProject(id: string): Promise<void> {
  const { error } = await supabase().from("projects").delete().eq("id", id);
  fail(error);
}

/** 프로젝트를 내 작업 공간에 복제한다. 공유받은 프로젝트에도 쓴다. */
export function duplicateProject(p: Pick<Project, "name" | "graph" | "overrides" | "pattern_id">): Promise<Project> {
  return createProject({ name: `${p.name} 사본`, graph: p.graph, overrides: p.overrides, pattern_id: p.pattern_id });
}

export function shareUrl(id: string) {
  return `${window.location.origin}/playground?p=${id}`;
}
