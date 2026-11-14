import Link from "next/link";
import { getCurriculum, getDocsIndex } from "@/lib/content";
import { Icon } from "@/components/ui/icon";
import { HeroCanvas } from "@/components/home/hero-canvas";
import { PatternStrip } from "@/components/home/pattern-strip";

const STEPS = [
  { title: "그립니다", desc: "Supervisor, 조건 분기, Send, interrupt 같은 요소를 끌어다 선으로 잇습니다. 패턴 예시에서 시작해도 됩니다." },
  { title: "실행 전에 확인합니다", desc: "닿지 않는 노드, 출구 없는 루프, 체크포인터 없는 interrupt를 그리는 동안 빨갛게 표시합니다." },
  { title: "코드를 받아 실행합니다", desc: "그래프가 바뀔 때마다 LangGraph 프로젝트가 다시 생성됩니다. 브라우저에서 바로 실행하고, ZIP으로 내려받습니다." },
  { title: "저장하고 공유합니다", desc: "프로젝트는 계정에 자동 저장됩니다. 링크를 보내면 받은 사람이 열어 보고 자기 사본으로 복제합니다." },
];

export default async function Home() {
  const [curriculum, docs] = await Promise.all([getCurriculum(), getDocsIndex()]);
  const lessonCount = curriculum.reduce((a, m) => a + m.lessons.length, 0);
  const docCount = docs.reduce((a, c) => a + c.docs.length, 0);

  return (
    <main className="flex-1">
      <section className="border-b border-border">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:py-24">
          <div className="min-w-0">
            <h1 className="text-4xl leading-[1.2] font-bold tracking-tight text-balance md:text-5xl md:leading-[1.15]">에이전트를 그리면 실행되는 LangGraph 코드가 됩니다</h1>
            <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-muted">
              AgentLab은 AI 에이전트를 설계하는 작업 공간입니다. 노드를 잇는 동안 코드가 만들어지고, 구조 오류는 실행하기 전에 드러납니다.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/playground" className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-fg hover:brightness-110">
                플레이그라운드 열기
              </Link>
              <Link href="/learn" className="rounded-xl border border-border bg-surface px-5 py-3 text-sm font-semibold hover:border-border-strong">
                강의부터 보기
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted">로그인 없이 그려 볼 수 있습니다. 저장과 코드 실행은 Google 로그인 후 사용합니다.</p>
          </div>
          <div className="min-w-0">
            <HeroCanvas />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="max-w-2xl text-2xl font-bold tracking-tight md:text-3xl">그림에서 실행까지 한 화면에서</h2>
        <ol className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="border-t-2 border-fg pt-4">
              <span className="font-mono text-xs text-muted">{i + 1}단계</span>
              <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.desc}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight md:text-3xl">검증된 패턴에서 시작하세요</h2>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">ReAct부터 Supervisor, RAG, 사람 승인까지. 불러온 뒤 노드를 바꿔 가며 내 에이전트로 만듭니다.</p>
            </div>
            <Link href="/playground" className="text-sm font-medium text-accent hover:underline">
              플레이그라운드에서 불러오기
            </Link>
          </div>
          <PatternStrip />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight md:text-3xl">처음이라면 강의로</h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
              강의 {lessonCount}개가 기초부터 프로덕션까지 이어집니다. 모든 강의 옆에 실행되는 IDE가 있고, 막히면 한국어 API 레퍼런스 {docCount}편을 찾아봅니다.
            </p>
          </div>
          <div className="flex gap-4 text-sm font-medium text-accent">
            <Link href="/learn" className="hover:underline">
              전체 커리큘럼
            </Link>
            <Link href="/docs" className="hover:underline">
              Docs
            </Link>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {curriculum.map((m) => (
            <Link key={m.slug} href={m.lessons[0] ? `/learn/${m.lessons[0].id}` : "/learn"} className="rounded-xl border border-border bg-surface p-5 transition hover:border-accent">
              <div className="mb-3 flex items-center justify-between">
                <Icon name={m.icon} className="h-5 w-5 text-accent" />
                <span className="text-xs text-muted">강의 {m.lessons.length}개</span>
              </div>
              <div className="mb-1 font-semibold">{m.title}</div>
              <p className="line-clamp-2 text-[13px] leading-relaxed text-muted">{m.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <footer className="border-t border-border px-6 py-8 text-center text-xs leading-relaxed text-muted">
        AgentLab. 코드는 격리된 샌드박스에서 실행되고, OpenAI API Key는 이 브라우저에만 저장됩니다.
      </footer>
    </main>
  );
}
