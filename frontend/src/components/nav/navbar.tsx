"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { BookOpen, Boxes, FileText, KeyRound, Moon, Settings2, Sun, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettings } from "@/lib/settings";
import { health } from "@/lib/api";
import { SettingsDialog } from "./settings-dialog";

const LINKS = [
  { href: "/learn", label: "학습", icon: BookOpen },
  { href: "/playground", label: "플레이그라운드", icon: Workflow },
  { href: "/docs", label: "Docs", icon: FileText },
];

export function Navbar() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const { apiKey, setOpen } = useSettings();
  const [backend, setBackend] = useState<"unknown" | "up" | "down">("unknown");

  useEffect(() => {
    setMounted(true);
    let alive = true;
    const ping = () => health().then((h) => alive && setBackend(h ? "up" : "down"));
    ping();
    const t = setInterval(ping, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <>
      <header className="sticky top-0 z-40 h-14 shrink-0 border-b border-border bg-bg/80 backdrop-blur-xl">
        <div className="flex h-full items-center gap-6 px-4 md:px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent-2 text-accent-fg">
              <Boxes className="h-4 w-4" />
            </span>
            <span className="text-[15px]">AgentLab</span>
          </Link>
          <nav className="flex items-center gap-1">
            {LINKS.map(({ href, label, icon: Icon }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors",
                    active ? "bg-surface-2 text-fg" : "text-muted hover:bg-surface-2 hover:text-fg",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
            <span
              title={backend === "up" ? "실행 서버 연결됨" : backend === "down" ? "실행 서버에 연결할 수 없음" : "확인 중"}
              className="hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-muted md:flex"
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  backend === "up" ? "bg-success" : backend === "down" ? "bg-danger" : "bg-muted",
                )}
              />
              {backend === "up" ? "Runtime" : backend === "down" ? "Offline" : "…"}
            </span>
            <button
              onClick={() => setOpen(true)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
                mounted && apiKey
                  ? "border-border text-muted hover:text-fg"
                  : "border-accent/40 bg-accent-soft text-accent hover:border-accent",
              )}
            >
              {mounted && apiKey ? <Settings2 className="h-3.5 w-3.5" /> : <KeyRound className="h-3.5 w-3.5" />}
              <span className="hidden sm:inline">{mounted && apiKey ? "설정" : "API Key"}</span>
            </button>
            <button
              aria-label="테마 전환"
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-fg"
            >
              {mounted && resolvedTheme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>
      <SettingsDialog />
    </>
  );
}
