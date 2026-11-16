import Link from "next/link";
import { getCurriculum, getDocsIndex } from "@/lib/content";
import { Icon } from "@/components/ui/icon";
import { HeroCanvas } from "@/components/home/hero-canvas";
import { PatternStrip } from "@/components/home/pattern-strip";
import { SubagentFigure } from "@/components/home/subagent-figure";
import { PATTERNS } from "@/lib/playground/patterns";

const STEPS = [
  { title: "그립니다", desc: "Supervisor, 조건 분기, Send, interrupt, Sub-agent 같은 요소를 끌어다 선으로 잇습니다. 패턴이나 내 프리셋에서 시작해도 됩니다." },
  { title: "실행 전에 확인합니다", desc: "닿지 않는 노드, 출구 없는 루프, 체크포인터 없는 interrupt를 그리는 동안 빨갛게 표시합니다. 서브 에이전트 안쪽까지 검사합니다." },
  { title: "코드를 받아 실행합니다", desc: "그래프가 바뀔 때마다 LangGraph 프로젝트가 다시 생성됩니다. 브라우저에서 바로 실행하고, 구조 테스트까지 든 ZIP으로 내려받습니다." },
  { title: "저장하고 재사용합니다", desc: "프로젝트는 계정에 자동 저장되고 링크로 공유합니다. 잘 만든 에이전트는 프리셋으로 저장해 다른 그래프에 그대로 넣습니다." },
];

const SUBAGENT_POINTS = [
  { title: "열어서 고칩니다", desc: "Sub-agent 노드를 더블클릭하면 안쪽 그래프가 열립니다. 몇 단계든 중첩되고, 위쪽 경로를 눌러 바깥으로 돌아옵니다." },
  { title: "묶고 풉니다", desc: "노드 몇 개를 골라 Sub-agent 하나로 묶거나, 반대로 풀어서 바깥 그래프에 펼칩니다." },
  { title: "주고받는 방식을 고릅니다", desc: "최종 답변만 돌려받는 격리 모드와 상태를 그대로 나누는 공유 모드, 호출마다 새로 시작할지 이전 대화를 기억할지 정합니다." },
  { title: "프리셋으로 다시 씁니다", desc: "만든 에이전트를 계정에 저장해 두고 다른 그래프에 끌어다 놓습니다. 원본이 바뀌면 알려 주고, JSON으로 팀원과 주고받습니다." },
];

const DAILY = [
  { icon: "cpu", title: "노드별 모델", desc: "라우터는 작은 모델, 작성자는 큰 모델. 배포할 때 환경 변수로 바꿉니다." },
  { icon: "wrench", title: "커스텀 도구", desc: "@tool 함수를 직접 쓰고 서브 에이전트와 프리셋에서 함께 씁니다." },
  { icon: "copy", title: "복사 · 붙여넣기", desc: "⌘C, ⌘V, ⌘D로 노드를 옮깁니다. 서브그래프와 프로젝트를 넘나듭니다." },
  { icon: "search", title: "⌘K 노드 검색", desc: "중첩된 서브 에이전트 안까지 이름, 프롬프트, 도구로 찾아 바로 이동합니다." },
  { icon: "file-json", title: "agentlab.json", desc: "그래프 원본을 저장소에 커밋해 리뷰하고, 다시 가져와 이어서 고칩니다." },
  { icon: "flask-conical", title: "구조 테스트", desc: "생성 프로젝트에 LLM 호출 없는 pytest가 들어 있어 CI에 바로 넣습니다." },
];

const SAFETY = [
  { title: "샌드박스는 OpenAI에만 연결됩니다", desc: "실행 코드는 허용된 주소 밖으로 나갈 수 없고, 외부 프로그램을 띄울 수 없습니다. 키 없이 실행하면 네트워크가 완전히 막힙니다." },
  { title: "고도화 코드는 검사를 통과해야 공유됩니다", desc: "LLM이 다듬은 코드는 네트워크, 파일, 비밀 환경 변수 접근을 찾아내는 검사를 통과해야 캐시에 남고, 자동으로 적용되지 않습니다." },
  { title: "API Key는 이 탭에만 둡니다", desc: "탭을 닫으면 지워집니다. 계속 기억할지는 설정에서 직접 고릅니다. 서버는 키를 저장하지 않습니다." },
  { title: "남이 쓴 코드는 실행 전에 묻습니다", desc: "공유받은 프로젝트에 직접 작성된 코드가 있으면, 내 키로 실행하기 전에 무엇이 들어 있는지 보여 주고 확인을 받습니다." },
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
            <h1 className="text-4xl leading-[1.2] font-bold tracking-tight text-balance md:text-5xl md:leading-[1.15]">
              에이전트를 <span className="hl-pink">그리면</span> 실행되는 <span className="hl">LangGraph 코드</span>가 됩니다
            </h1>
            <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-muted">
              AgentLab은 AI 에이전트를 설계하는 작업 공간입니다. 노드를 잇는 동안 코드가 만들어지고, 구조 오류는 실행하기 전에 드러납니다. 큰 시스템은 서브 에이전트로 나눠 만들고, 잘 만든 에이전트는 프리셋으로 다시 씁니다.
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
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <div className="min-w-0">
            <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">Sub-agent · 프리셋</span>
            <h2 className="mt-4 text-2xl font-bold tracking-tight text-balance md:text-3xl">큰 에이전트는 나눠서 만들고, 만든 것은 다시 씁니다</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              팀 단위 멀티 에이전트도 한 화면에서 다룹니다. 생성 코드에서는 서브 에이전트마다 패키지가 따로 생겨, 단독으로 테스트하고 LangGraph Server에서도 별도 그래프로 열립니다.
            </p>
            <dl className="mt-8 space-y-5">
              {SUBAGENT_POINTS.map((p) => (
                <div key={p.title} className="border-l-2 border-accent pl-4">
                  <dt className="font-semibold">{p.title}</dt>
                  <dd className="mt-1 text-sm leading-relaxed text-muted">{p.desc}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="min-w-0">
            <SubagentFigure />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="max-w-2xl text-2xl font-bold tracking-tight md:text-3xl">매일 쓰는 도구로</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">설계에서 끝나지 않고, 생성된 코드를 그대로 저장소에 넣어 운영할 수 있게 만들었습니다.</p>
        <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {DAILY.map((f) => (
            <div key={f.title} className="bg-surface p-6">
              <Icon name={f.icon} className="h-5 w-5 text-accent" />
              <h3 className="mt-3 font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight md:text-3xl">검증된 패턴에서 시작하세요</h2>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
                ReAct부터 계층형 팀, RAG, 사람 승인까지 {PATTERNS.length}종. 불러와서 고치거나, 다른 그래프에 Sub-agent로 바로 넣습니다.
              </p>
            </div>
            <Link href="/playground" className="text-sm font-medium text-accent hover:underline">
              플레이그라운드에서 불러오기
            </Link>
          </div>
          <PatternStrip />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="max-w-2xl text-2xl font-bold tracking-tight md:text-3xl">남이 만든 코드와 내 키를 안전하게</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">공유 링크, 공용 캐시, 브라우저 실행이 모두 있는 서비스라서 처음부터 그 경로를 막았습니다.</p>
        <ul className="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-2">
          {SAFETY.map((x) => (
            <li key={x.title} className="flex gap-3">
              <Icon name="shield-check" className="mt-0.5 h-5 w-5 shrink-0 text-success" />
              <div>
                <h3 className="font-semibold">{x.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted">{x.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-border bg-surface">
      <div className="mx-auto max-w-6xl px-6 py-20">
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
            <Link key={m.slug} href={m.lessons[0] ? `/learn/${m.lessons[0].id}` : "/learn"} className="rounded-xl border border-border bg-bg p-5 transition hover:border-accent">
              <div className="mb-3 flex items-center justify-between">
                <Icon name={m.icon} className="h-5 w-5 text-accent" />
                <span className="text-xs text-muted">강의 {m.lessons.length}개</span>
              </div>
              <div className="mb-1 font-semibold">{m.title}</div>
              <p className="line-clamp-2 text-[13px] leading-relaxed text-muted">{m.description}</p>
            </Link>
          ))}
        </div>
      </div>
      </section>

      <footer className="border-t border-border px-6 py-8 text-center text-xs leading-relaxed text-muted">
        AgentLab. 코드는 네트워크가 제한된 샌드박스에서 실행되고, OpenAI API Key는 브라우저에만 보관되며 서버에 저장되지 않습니다.
        <div className="mt-2 flex justify-center gap-4">
          <Link href="/privacy" className="hover:text-fg">
            개인정보처리방침
          </Link>
          <Link href="/terms" className="hover:text-fg">
            서비스 약관
          </Link>
        </div>
      </footer>
    </main>
  );
}
