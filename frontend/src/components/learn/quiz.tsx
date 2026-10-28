"use client";

import { useState } from "react";
import { CheckCircle2, CircleHelp, RotateCcw, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProgress } from "@/lib/settings";
import type { QuizItem } from "@/lib/content";

export function Quiz({ lessonId, items }: { lessonId: string; items: QuizItem[] }) {
  const [picked, setPicked] = useState<(number | null)[]>(() => items.map(() => null));
  const setQuiz = useProgress((s) => s.setQuiz);
  const answered = picked.filter((p) => p !== null).length;
  const correct = picked.filter((p, i) => p === items[i].answer).length;

  if (!items.length) return null;

  const choose = (qi: number, oi: number) => {
    if (picked[qi] !== null) return;
    const next = picked.map((p, i) => (i === qi ? oi : p));
    setPicked(next);
    if (next.every((p) => p !== null)) setQuiz(lessonId, next.filter((p, i) => p === items[i].answer).length);
  };

  return (
    <section className="mt-14 rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex items-center gap-2">
        <CircleHelp className="h-5 w-5 text-accent" />
        <h2 className="text-lg font-semibold">이해도 체크</h2>
        <span className="ml-auto text-xs text-muted">
          {answered}/{items.length} · 정답 {correct}
        </span>
        {answered > 0 && (
          <button onClick={() => setPicked(items.map(() => null))} className="rounded p-1 text-muted hover:text-fg" title="다시 풀기">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <ol className="space-y-6">
        {items.map((item, qi) => (
          <li key={qi}>
            <p className="mb-2.5 text-[15px] font-medium">
              <span className="mr-1.5 text-accent">Q{qi + 1}.</span>
              {item.q}
            </p>
            <div className="grid gap-2">
              {item.options.map((opt, oi) => {
                const chosen = picked[qi] === oi;
                const reveal = picked[qi] !== null;
                const isAnswer = oi === item.answer;
                return (
                  <button
                    key={oi}
                    onClick={() => choose(qi, oi)}
                    className={cn(
                      "flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-left text-sm transition-colors",
                      !reveal && "border-border hover:border-accent/60 hover:bg-surface-2",
                      reveal && isAnswer && "border-success/60 bg-success/10",
                      reveal && chosen && !isAnswer && "border-danger/60 bg-danger/10",
                      reveal && !chosen && !isAnswer && "border-border opacity-60",
                    )}
                  >
                    {reveal && isAnswer ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                    ) : reveal && chosen ? (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
                    ) : (
                      <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border border-border-strong text-[10px] text-muted">
                        {String.fromCharCode(65 + oi)}
                      </span>
                    )}
                    <span>{opt}</span>
                  </button>
                );
              })}
            </div>
            {picked[qi] !== null && item.explain && (
              <p className="fade-in mt-2.5 rounded-lg bg-surface-2 px-3 py-2 text-[13px] leading-relaxed text-fg-2">💡 {item.explain}</p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
