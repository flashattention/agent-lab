import Link from "next/link";
import { ArrowRight, BookOpen, Bot, FileText, GitFork, Play, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { getCurriculum, getDocsIndex } from "@/lib/content";
import { PATTERNS } from "@/lib/playground/patterns";
import { Icon } from "@/components/ui/icon";

export default async function Home() {
  const [curriculum, docs] = await Promise.all([getCurriculum(), getDocsIndex()]);
  const lessonCount = curriculum.reduce((a, m) => a + m.lessons.length, 0);
  const hours = Math.round(curriculum.reduce((a, m) => a + m.lessons.reduce((b, l) => b + l.duration, 0), 0) / 60);
  const docCount = docs.reduce((a, c) => a + c.docs.length, 0);

  return (
    <main className="flex-1">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <div className="absolute -top-40 left-1/2 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-gradient-to-r from-accent/20 via-accent-2/15 to-transparent blur-3xl" />
        <div className="relative mx-auto max-w-6xl px-6 pt-24 pb-20 text-center">
          <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3.5 py-1 text-xs text-muted backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-accent" /> LangChain 1.4 · LangGraph 1.2 · 2026.10 기준
          </span>
          <h1 className="mx-auto max-w-4xl text-5xl leading-[1.1] font-bold tracking-tight md:text-6xl">
            처음부터 <span className="text-gradient">현업 AI Agent 엔지니어</span>까지
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted">
            개념 강의와 실제로 돌아가는 IDE, 그래프를 그리면 LangGraph 코드가 생성되는 비주얼 플레이그라운드, 한국어 API 레퍼런스를 한곳에서 제공합니다.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link href="/learn" className="flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-fg shadow-soft hover:brightness-110">
              학습 시작하기 <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/playground" className="flex items-center gap-2 rounded-xl border border-border bg-surface px-5 py-3 text-sm font-semibold hover:border-accent">
              <Workflow className="h-4 w-4" /> 플레이그라운드 열기
            </Link>
          </div>
          <div className="mx-auto mt-14 grid max-w-3xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-4">
            {[
              [lessonCount, "실습 강의"],
              [`${hours}h+`, "학습 분량"],
              [PATTERNS.length, "에이전트 패턴"],
              [docCount, "레퍼런스 문서"],
            ].map(([v, l]) => (
              <div key={l as string} className="bg-surface px-4 py-5">
                <div className="text-2xl font-bold tracking-tight">{v}</div>
                <div className="text-xs text-muted">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3 spaces */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-5 md:grid-cols-3">
          {[
            {
              href: "/learn",
              icon: BookOpen,
              title: "학습",
              desc: "이론과 실습을 나란히. 모든 강의의 오른쪽 IDE에서 코드를 고치고 실행하고, traceback을 클릭해 바로 디버깅합니다. 자동 채점 과제와 퀴즈도 있습니다.",
              points: ["8개 모듈 · 기초→프로덕션", "실행·디버깅 가능한 IDE", "자동 채점 과제 + 퀴즈"],
            },
            {
              href: "/playground",
              icon: GitFork,
              title: "플레이그라운드",
              desc: "Supervisor, Conditional Edge, Send, interrupt 같은 요소를 끌어다 연결하면 파일 구조와 코드가 실시간으로 생성됩니다. 잘못된 구조는 실행 전에 빨갛게 표시됩니다.",
              points: ["실시간 LangGraph 코드 생성", "병목·무한루프 사전 감지", "LLM 고도화 + 검증 캐싱"],
            },
            {
              href: "/docs",
              icon: FileText,
              title: "Docs",
              desc: "LangChain, LangGraph, 주요 Vector DB(Qdrant, Chroma, pgvector, Pinecone 등)의 핵심 API를 설치된 버전의 실제 시그니처 기준으로 정리했습니다.",
              points: ["⌘K 빠른 검색", "파라미터 표 + 예제", "흔한 실수와 주의사항"],
            },
          ].map(({ href, icon: I, title, desc, points }) => (
            <Link key={href} href={href} className="group rounded-2xl border border-border bg-surface p-6 transition hover:-translate-y-0.5 hover:border-accent hover:shadow-soft">
              <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent">
                <I className="h-5 w-5" />
              </span>
              <h3 className="mb-2 flex items-center gap-1.5 text-lg font-semibold">
                {title} <ArrowRight className="h-4 w-4 opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
              </h3>
              <p className="mb-4 text-sm leading-relaxed text-muted">{desc}</p>
              <ul className="space-y-1.5 text-[13px] text-fg-2">
                {points.map((p) => (
                  <li key={p} className="flex items-center gap-2">
                    <span className="h-1 w-1 rounded-full bg-accent" />
                    {p}
                  </li>
                ))}
              </ul>
            </Link>
          ))}
        </div>
      </section>

      {/* Curriculum roadmap */}
      <section className="border-y border-border bg-surface/50">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-10 flex items-end justify-between gap-4">
            <div>
              <p className="mb-2 text-sm font-medium text-accent">Roadmap</p>
              <h2 className="text-3xl font-bold tracking-tight">AI Agent 전문가 로드맵</h2>
            </div>
            <Link href="/learn" className="hidden text-sm text-muted hover:text-accent sm:block">
              전체 커리큘럼 →
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {curriculum.map((m) => (
              <Link key={m.slug} href={m.lessons[0] ? `/learn/${m.lessons[0].id}` : "/learn"} className="group rounded-2xl border border-border bg-surface p-5 transition hover:border-accent">
                <div className="mb-3 flex items-center justify-between">
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-surface-2 text-accent group-hover:bg-accent-soft">
                    <Icon name={m.icon} className="h-[18px] w-[18px]" />
                  </span>
                  <span className="font-mono text-xs text-muted">{String(m.index).padStart(2, "0")}</span>
                </div>
                <div className="mb-1 font-semibold">{m.title}</div>
                <p className="line-clamp-2 text-[12.5px] leading-relaxed text-muted">{m.description}</p>
                <div className="mt-3 text-[11px] text-muted">{m.lessons.length}개 강의</div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-8 md:grid-cols-3">
          {[
            { icon: Play, title: "진짜로 실행됩니다", desc: "격리된 Python 샌드박스에서 최신 langgraph/langchain이 그대로 실행됩니다. API Key가 없으면 Mock LLM으로 흐름을 확인할 수 있습니다." },
            { icon: ShieldCheck, title: "실행 전에 잡아냅니다", desc: "도달 불가 노드, 출구 없는 루프, 체크포인터 없는 interrupt, 승인 없는 민감 도구, fan-in 병목을 정적 분석으로 찾아 빨간색으로 표시합니다." },
            { icon: Bot, title: "한 번 생성, 계속 재사용", desc: "고성능 LLM으로 다듬은 코드는 ruff 검사와 실제 실행 검증을 통과해야만 그래프 구조 해시로 캐싱되고, 같은 구조라면 누구에게나 바로 제공됩니다." },
          ].map(({ icon: I, title, desc }) => (
            <div key={title}>
              <I className="mb-3 h-6 w-6 text-accent" />
              <h3 className="mb-2 font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-border py-8 text-center text-xs text-muted">
        AgentLab · LangChain {"&"} LangGraph 학습 플랫폼 · 코드 실행은 격리된 샌드박스에서 이루어지며 API Key는 브라우저에만 저장됩니다.
      </footer>
    </main>
  );
}
