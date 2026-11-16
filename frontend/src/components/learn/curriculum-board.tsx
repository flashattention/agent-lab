"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, Circle, Clock } from "lucide-react";
import type { Module } from "@/lib/content";
import { cn } from "@/lib/utils";
import { useProgress } from "@/lib/settings";
import { Icon } from "@/components/ui/icon";
import { LEVEL_STYLE } from "./lesson-view";
import { useMounted } from "@/lib/use-mounted";

export function CurriculumBoard({ curriculum }: { curriculum: Module[] }) {
  const done = useProgress((s) => s.done);
  const mounted = useMounted();
  const all = curriculum.flatMap((m) => m.lessons);
  const doneCount = mounted ? all.filter((l) => done[l.id]).length : 0;
  const nextLesson = all.find((l) => !(mounted && done[l.id]));
  const pct = all.length ? Math.round((doneCount / all.length) * 100) : 0;

  return (
    <>
      <div className="mb-10 flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5 sm:flex-row sm:items-center">
        <div className="flex-1">
          <div className="mb-2 flex items-baseline justify-between text-sm">
            <span className="font-medium">전체 진도</span>
            <span className="text-muted">
              {doneCount} / {all.length} 강의 · {pct}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
        {nextLesson && (
          <Link
            href={`/learn/${nextLesson.id}`}
            className="flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg hover:brightness-110"
          >
            {doneCount ? "이어서 학습" : "첫 강의 시작"} <ArrowRight className="h-4 w-4" />
          </Link>
        )}
      </div>

      <div className="space-y-6">
        {curriculum.map((m) => {
          const mDone = mounted ? m.lessons.filter((l) => done[l.id]).length : 0;
          const minutes = m.lessons.reduce((a, l) => a + l.duration, 0);
          return (
            <section key={m.slug} className="overflow-hidden rounded-2xl border border-border bg-surface">
              <div className="flex items-start gap-4 border-b border-border p-5">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
                  <Icon name={m.icon} className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-muted">MODULE {String(m.index).padStart(2, "0")}</div>
                  <h2 className="text-lg font-semibold tracking-tight">{m.title}</h2>
                  <p className="mt-0.5 text-sm text-muted">{m.description}</p>
                </div>
                <div className="hidden shrink-0 text-right text-xs text-muted sm:block">
                  <div>
                    {mDone}/{m.lessons.length} 완료
                  </div>
                  <div className="mt-0.5">약 {Math.round(minutes / 6) / 10}시간</div>
                </div>
              </div>
              <ul className="divide-y divide-border">
                {m.lessons.map((l, i) => (
                  <li key={l.id}>
                    <Link href={`/learn/${l.id}`} className="group flex items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2">
                      {mounted && done[l.id] ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                      ) : (
                        <Circle className="h-4 w-4 shrink-0 text-border-strong" />
                      )}
                      <span className="w-8 shrink-0 font-mono text-xs text-muted">
                        {m.index}.{i + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14.5px] font-medium group-hover:text-accent">{l.title}</span>
                        <span className="block truncate text-xs text-muted">{l.summary}</span>
                      </span>
                      <span className={cn("hidden rounded-full px-2 py-0.5 text-[11px] font-medium md:inline", LEVEL_STYLE[l.level])}>
                        {l.level}
                      </span>
                      <span className="hidden w-14 items-center justify-end gap-1 text-xs text-muted sm:flex">
                        <Clock className="h-3 w-3" />
                        {l.duration}분
                      </span>
                    </Link>
                  </li>
                ))}
                {m.lessons.length === 0 && <li className="px-5 py-4 text-sm text-muted">강의 준비 중…</li>}
              </ul>
            </section>
          );
        })}
      </div>
    </>
  );
}
