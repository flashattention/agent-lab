import type { LucideIcon } from "lucide-react";

/** 아이콘만 있는 작은 툴바 버튼. 이름은 title/aria-label 로 제공한다. */
export function ToolButton({ icon: I, label, title, onClick, disabled }: { icon: LucideIcon; label: string; title?: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} title={title ?? label} aria-label={label} className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40">
      <I className="h-3.5 w-3.5" />
    </button>
  );
}
