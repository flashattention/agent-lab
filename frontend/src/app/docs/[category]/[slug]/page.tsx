import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";
import { getDoc, getDocsIndex } from "@/lib/content";
import { Markdown } from "@/components/markdown/markdown";
import { DocToc } from "@/components/docs/doc-toc";

export async function generateStaticParams() {
  const index = await getDocsIndex();
  return index.flatMap((c) => c.docs.map((d) => ({ category: c.slug, slug: d.slug })));
}

export async function generateMetadata(props: PageProps<"/docs/[category]/[slug]">): Promise<Metadata> {
  const { category, slug } = await props.params;
  const doc = await getDoc(category, slug);
  return { title: doc?.title ?? "Docs", description: doc?.description };
}

export default async function DocPage(props: PageProps<"/docs/[category]/[slug]">) {
  const { category, slug } = await props.params;
  const [doc, index] = await Promise.all([getDoc(category, slug), getDocsIndex()]);
  if (!doc) notFound();
  const cat = index.find((c) => c.slug === category);
  const flat = index.flatMap((c) => c.docs);
  const i = flat.findIndex((d) => d.category === category && d.slug === slug);
  const prev = flat[i - 1];
  const next = flat[i + 1];
  const headings = [...doc.body.matchAll(/^(##|###)\s+(.+)$/gm)].map((m) => ({ depth: m[1].length, text: m[2].replace(/`/g, "") }));

  return (
    <div className="flex">
      <main className="min-w-0 flex-1 px-6 py-10 lg:px-12">
        <div className="mx-auto max-w-3xl">
          <div className="mb-2 text-sm text-accent">{cat?.title}</div>
          <h1 className="mb-2 text-3xl font-bold tracking-tight">{doc.title}</h1>
          <p className="mb-4 text-muted">{doc.description}</p>
          <div className="mb-8 flex flex-wrap items-center gap-2">
            {doc.tags.map((t) => (
              <span key={t} className="rounded-full border border-border px-2 py-0.5 text-xs text-muted">
                #{t}
              </span>
            ))}
            {doc.source && (
              <a
                href={doc.source}
                target="_blank"
                rel="noreferrer"
                className="ml-auto flex items-center gap-1 text-xs text-muted hover:text-accent"
              >
                공식 문서 <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <Markdown source={doc.body} />
          <div className="mt-14 grid gap-3 border-t border-border pt-6 sm:grid-cols-2">
            {prev ? (
              <Link href={`/docs/${prev.category}/${prev.slug}`} className="rounded-xl border border-border p-3 hover:border-accent">
                <span className="flex items-center gap-1 text-xs text-muted">
                  <ArrowLeft className="h-3 w-3" /> 이전
                </span>
                <span className="text-sm font-medium">{prev.title}</span>
              </Link>
            ) : (
              <span />
            )}
            {next && (
              <Link href={`/docs/${next.category}/${next.slug}`} className="rounded-xl border border-border p-3 text-right hover:border-accent">
                <span className="flex items-center justify-end gap-1 text-xs text-muted">
                  다음 <ArrowRight className="h-3 w-3" />
                </span>
                <span className="text-sm font-medium">{next.title}</span>
              </Link>
            )}
          </div>
        </div>
      </main>
      <DocToc headings={headings} />
    </div>
  );
}
