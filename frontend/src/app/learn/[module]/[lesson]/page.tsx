import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getCurriculum, getLesson } from "@/lib/content";
import { LessonView } from "@/components/learn/lesson-view";

export async function generateStaticParams() {
  const curriculum = await getCurriculum();
  return curriculum.flatMap((m) => m.lessons.map((l) => ({ module: m.slug, lesson: l.slug })));
}

export async function generateMetadata(props: PageProps<"/learn/[module]/[lesson]">): Promise<Metadata> {
  const { module, lesson } = await props.params;
  const data = await getLesson(module, lesson);
  return { title: data?.title ?? "강의", description: data?.summary };
}

export default async function LessonPage(props: PageProps<"/learn/[module]/[lesson]">) {
  const { module, lesson } = await props.params;
  const [data, curriculum] = await Promise.all([getLesson(module, lesson), getCurriculum()]);
  if (!data) notFound();
  return <LessonView lesson={data} curriculum={curriculum} />;
}
