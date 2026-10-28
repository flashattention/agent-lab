import Link from "next/link";
import type { Metadata } from "next";
import { getDocsIndex, getDocsSearchIndex } from "@/lib/content";
import { DocsSearch } from "@/components/docs/docs-sidebar";
import { Icon } from "@/components/ui/icon";

export const metadata: Metadata = { title: "Docs" };

export default async function DocsHome() {
  const [index, search] = await Promise.all([getDocsIndex(), getDocsSearchIndex()]);
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="mb-2 text-4xl font-bold tracking-tight">레퍼런스 문서</h1>
      <p className="mb-6 text-muted">
        LangChain · LangGraph · Vector DB · 통합 도구의 핵심 API를 한국어로 정리했습니다. 실제 설치 버전의 시그니처를 기준으로 작성했습니다.
      </p>
      <div className="mb-10 max-w-2xl">
        <DocsSearch search={search} large />
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        {index.map((c) => (
          <section key={c.slug} className="rounded-2xl border border-border bg-surface p-5">
            <div className="mb-3 flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft text-accent">
                <Icon name={c.icon} className="h-[18px] w-[18px]" />
              </span>
              <div>
                <h2 className="font-semibold">{c.title}</h2>
                <p className="text-xs text-muted">{c.description}</p>
              </div>
              <span className="ml-auto text-xs text-muted">{c.docs.length}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {c.docs.map((d) => (
                <Link
                  key={d.slug}
                  href={`/docs/${c.slug}/${d.slug}`}
                  className="rounded-lg border border-border px-2.5 py-1 text-[13px] text-fg-2 transition-colors hover:border-accent hover:text-accent"
                >
                  {d.title}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
