"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Circle, Clock, Gauge, KeyRound, List, Target, X } from "lucide-react";
import type { Lesson, Module } from "@/lib/content";
import { cn } from "@/lib/utils";
import { useProgress } from "@/lib/settings";
import { Markdown } from "@/components/markdown/markdown";
import { SplitGroup, SplitHandle, SplitPanel } from "@/components/ui/split";
import { LessonIDE, type LessonIDEHandle } from "./lesson-ide";
import { Quiz } from "./quiz";
import { useMounted } from "@/lib/use-mounted";

export const LEVEL_STYLE: Record<string, string> = {
  입문: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  초급: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  중급: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
  고급: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  전문가: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
};

export function LessonView({ lesson, curriculum }: { lesson: Lesson; curriculum: Module[] }) {
  const ide = useRef<LessonIDEHandle>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const { done, toggle } = useProgress();
  const mounted = useMounted();
  const [toc, setToc] = useState(false);
  useEffect(() => scroller.current?.scrollTo({ top: 0 }), [lesson.id]);
  const isDone = mounted && !!done[lesson.id];

  return (
    <div className="relative flex h-[calc(100dvh-3.5rem)] min-h-0">
      {/* 커리큘럼 드로어 */}
      {toc && (
        <div className="absolute inset-0 z-30 flex" onClick={() => setToc(false)}>
          <aside
            className="fade-in h-full w-80 overflow-y-auto border-r border-border bg-surface p-4 shadow-soft"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">커리큘럼</span>
              <button onClick={() => setToc(false)} className="rounded p-1 text-muted hover:text-fg">
                <X className="h-4 w-4" />
              </button>
            </div>
            {curriculum.map((m) => (
              <div key={m.slug} className="mb-4">
                <div className="mb-1 text-[11px] font-semibold tracking-wide text-muted uppercase">
                  {String(m.index).padStart(2, "0")} · {m.title}
                </div>
                {m.lessons.map((l) => (
                  <Link
                    key={l.id}
                    href={`/learn/${l.id}`}
                    onClick={() => setToc(false)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13px]",
                      l.id === lesson.id ? "bg-accent-soft text-accent" : "text-fg-2 hover:bg-surface-2",
                    )}
                  >
                    {mounted && done[l.id] ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success" />
                    ) : (
                      <Circle className="h-3.5 w-3.5 shrink-0 text-border-strong" />
                    )}
                    <span className="truncate">{l.title}</span>
                  </Link>
                ))}
              </div>
            ))}
          </aside>
        </div>
      )}

      <SplitGroup orientation="horizontal" className="min-h-0 flex-1">
        <SplitPanel defaultSize="50" minSize="28">
          <div ref={scroller} className="h-full overflow-y-auto">
            <div className="sticky top-0 z-10 flex h-11 items-center gap-2 border-b border-border bg-bg/85 px-5 backdrop-blur">
              <button
                onClick={() => setToc(true)}
                className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-fg"
              >
                <List className="h-4 w-4" /> 목차
              </button>
              <span className="truncate text-xs text-muted">{lesson.moduleTitle}</span>
              <div className="ml-auto flex items-center gap-1">
                {lesson.prev && (
                  <Link href={`/learn/${lesson.prev.id}`} className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" title={lesson.prev.title}>
                    <ArrowLeft className="h-4 w-4" />
                  </Link>
                )}
                {lesson.next && (
                  <Link href={`/learn/${lesson.next.id}`} className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" title={lesson.next.title}>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                )}
              </div>
            </div>

            <article className="mx-auto max-w-3xl px-6 pt-8 pb-24 lg:px-10">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
                <span className={cn("rounded-full px-2.5 py-0.5 font-medium", LEVEL_STYLE[lesson.level] ?? LEVEL_STYLE["초급"])}>
                  <Gauge className="mr-1 inline h-3 w-3" />
                  {lesson.level}
                </span>
                <span className="flex items-center gap-1 text-muted">
                  <Clock className="h-3 w-3" /> {lesson.duration}분
                </span>
                {lesson.requiresKey && (
                  <span className="flex items-center gap-1 text-muted">
                    <KeyRound className="h-3 w-3" /> 실제 LLM 권장
                  </span>
                )}
                {lesson.tags.slice(0, 4).map((t) => (
                  <span key={t} className="rounded-full border border-border px-2 py-0.5 text-muted">
                    #{t}
                  </span>
                ))}
              </div>
              <h1 className="mb-3 text-[2rem] leading-tight font-bold tracking-tight">{lesson.title}</h1>
              <p className="mb-6 text-[15px] leading-relaxed text-muted">{lesson.summary}</p>

              {lesson.objectives.length > 0 && (
                <div className="mb-8 rounded-2xl border border-border bg-surface p-4">
                  <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                    <Target className="h-4 w-4 text-accent" /> 학습 목표
                  </div>
                  <ul className="space-y-1 text-sm text-fg-2">
                    {lesson.objectives.map((o) => (
                      <li key={o} className="flex gap-2">
                        <span className="text-accent">•</span>
                        {o}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Markdown source={lesson.body} onRunSnippet={(code) => ide.current?.openSnippet(code)} />

              <Quiz key={lesson.id} lessonId={lesson.id} items={lesson.quiz} />

              <div className="mt-10 flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:items-center">
                <button
                  onClick={() => toggle(lesson.id)}
                  className={cn(
                    "flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition",
                    isDone ? "bg-success/15 text-success" : "border border-border hover:border-accent hover:text-accent",
                  )}
                >
                  <CheckCircle2 className="h-4 w-4" /> {isDone ? "완료한 강의" : "완료로 표시"}
                </button>
                {lesson.next && (
                  <Link
                    href={`/learn/${lesson.next.id}`}
                    className="group flex flex-1 items-center justify-between rounded-xl border border-border bg-surface px-4 py-2.5 text-sm hover:border-accent sm:ml-auto sm:max-w-sm"
                  >
                    <span>
                      <span className="block text-[11px] text-muted">다음 강의</span>
                      <span className="font-medium">{lesson.next.title}</span>
                    </span>
                    <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
                  </Link>
                )}
              </div>
            </article>
          </div>
        </SplitPanel>
        <SplitHandle />
        <SplitPanel defaultSize="50" minSize="25">
          <LessonIDE key={lesson.id} ref={ide} lessonId={lesson.id} files={lesson.files} requiresKey={lesson.requiresKey} />
        </SplitPanel>
      </SplitGroup>
    </div>
  );
}
