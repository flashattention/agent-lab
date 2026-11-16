import type { ReactNode } from "react";

export const LEGAL_UPDATED = "2026년 11월 14일";
export const CONTACT_URL = "https://github.com/flashattention/agent-lab/issues";

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <h1 className="mb-2 text-3xl font-bold tracking-tight">{title}</h1>
      <p className="mb-10 text-sm text-muted">시행일: {LEGAL_UPDATED}</p>
      <div className="space-y-8 leading-7 text-fg-2 [&_a]:text-accent [&_a]:underline [&_h2]:mb-3 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-fg [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-1.5">
        {children}
      </div>
    </main>
  );
}
