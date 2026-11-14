"use client";

import { create } from "zustand";
import type { Session } from "@supabase/supabase-js";
import { supabase, SUPABASE_ENABLED } from "./supabase";

export type AuthUser = { id: string; email: string; name: string; avatar: string | null };

type AuthState = {
  ready: boolean; // 저장된 로그인 정보를 확인했는지
  user: AuthUser | null;
  token: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
};

function toUser(session: Session | null): AuthUser | null {
  const u = session?.user;
  if (!u) return null;
  const meta = (u.user_metadata ?? {}) as Record<string, string | undefined>;
  return { id: u.id, email: u.email ?? "", name: meta.full_name || meta.name || u.email?.split("@")[0] || "사용자", avatar: meta.avatar_url || meta.picture || null };
}

export const useAuth = create<AuthState>()(() => ({
  ready: !SUPABASE_ENABLED,
  user: null,
  token: null,
  signIn: async () => {
    if (!SUPABASE_ENABLED) return;
    // 로그인 후 보고 있던 화면으로 돌아온다
    await supabase().auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.href } });
  },
  signOut: async () => {
    if (!SUPABASE_ENABLED) return;
    await supabase().auth.signOut();
  },
}));

let started = false;

/** 앱 시작 시 한 번 호출한다. 로그인 상태가 바뀔 때마다 스토어를 갱신한다. */
export function startAuth() {
  if (started || !SUPABASE_ENABLED || typeof window === "undefined") return;
  started = true;
  const apply = (session: Session | null) => useAuth.setState({ ready: true, user: toUser(session), token: session?.access_token ?? null });
  supabase()
    .auth.getSession()
    .then(({ data }) => apply(data.session))
    .catch(() => apply(null));
  supabase().auth.onAuthStateChange((_event, session) => apply(session));
}
