"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { FolderOpen, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { SUPABASE_ENABLED } from "@/lib/supabase";

export function GoogleMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 18 18" className={className} aria-hidden>
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
    </svg>
  );
}

export function SignInButton({ label = "Google로 로그인", className }: { label?: string; className?: string }) {
  const signIn = useAuth((s) => s.signIn);
  return (
    <button
      onClick={signIn}
      className={className ?? "flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium hover:border-border-strong hover:bg-surface-2"}
    >
      <GoogleMark className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

export function AuthMenu() {
  const { ready, user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const key = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", key);
    };
  }, [open]);

  if (!SUPABASE_ENABLED) return null;
  if (!ready) return <span className="h-8 w-20 animate-pulse rounded-lg bg-surface-2" />;
  if (!user) return <SignInButton label="로그인" />;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="계정 메뉴"
        className="grid h-8 w-8 place-items-center overflow-hidden rounded-full border border-border bg-surface-2 text-xs font-semibold hover:border-accent"
      >
        {user.avatar ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatar} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        ) : (
          user.name.slice(0, 1).toUpperCase()
        )}
      </button>
      {open && (
        <div role="menu" className="fade-in absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-xl border border-border bg-surface shadow-soft">
          <div className="border-b border-border px-3.5 py-3">
            <div className="truncate text-sm font-medium">{user.name}</div>
            <div className="truncate text-xs text-muted">{user.email}</div>
          </div>
          <Link role="menuitem" href="/projects" onClick={() => setOpen(false)} className="flex items-center gap-2 px-3.5 py-2.5 text-sm hover:bg-surface-2">
            <FolderOpen className="h-4 w-4 text-muted" /> 내 프로젝트
          </Link>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              signOut();
            }}
            className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm hover:bg-surface-2"
          >
            <LogOut className="h-4 w-4 text-muted" /> 로그아웃
          </button>
        </div>
      )}
    </div>
  );
}
