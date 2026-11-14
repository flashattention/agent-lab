"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

/** 환경 변수가 없으면(로컬 개발) 로그인·프로젝트 저장 없이 동작한다. */
export const SUPABASE_ENABLED = Boolean(URL && KEY);

let client: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (!SUPABASE_ENABLED) throw new Error("로그인 기능이 설정되지 않았습니다.");
  client ??= createClient(URL, KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
  return client;
}
