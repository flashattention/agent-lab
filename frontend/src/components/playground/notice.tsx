"use client";

import { Loader2, X } from "lucide-react";
import { SignInButton } from "@/components/auth/auth-menu";
import { cn } from "@/lib/utils";

export type Notice = { kind: "ok" | "error" | "info" | "login"; text: string };

/** 캔버스 아래쪽에 떠 있는 알림. */
export function NoticeToast({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  return (
    <div
      role="status"
      className={cn(
        "fade-in absolute bottom-4 left-1/2 z-20 flex max-w-[92%] -translate-x-1/2 items-center gap-2 rounded-full border bg-surface px-4 py-1.5 text-xs shadow-soft",
        notice.kind === "ok" && "border-success/40 text-success",
        notice.kind === "error" && "border-danger/40 text-danger",
        (notice.kind === "info" || notice.kind === "login") && "border-accent/40 text-accent",
      )}
    >
      {notice.kind === "info" && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />}
      <span className="min-w-0">{notice.text}</span>
      {notice.kind === "login" && <SignInButton />}
      <button onClick={onClose} className="shrink-0 opacity-70 hover:opacity-100" aria-label="닫기">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
