import "server-only";

import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";

const ROOT = path.join(process.cwd(), "content");
const LEARN = path.join(ROOT, "learn");
const DOCS = path.join(ROOT, "docs");

export type LessonMeta = {
  id: string; // "<module>/<lesson>"
  module: string;
  slug: string;
  title: string;
  summary: string;
  duration: number;
  level: string;
  tags: string[];
  requiresKey: boolean;
  objectives: string[];
};

export type Module = {
  slug: string;
  index: number;
  title: string;
  description: string;
  icon: string;
  lessons: LessonMeta[];
};

export type QuizItem = { q: string; options: string[]; answer: number; explain?: string };

export type Lesson = LessonMeta & {
  body: string;
  files: Record<string, string>;
  quiz: QuizItem[];
  prev: LessonMeta | null;
  next: LessonMeta | null;
  moduleTitle: string;
};

const dirs = (p: string) =>
  fs.existsSync(p)
    ? fs
        .readdirSync(p, { withFileTypes: true })
        .filter((d) => d.isDirectory() && !d.name.startsWith(".") && !d.name.startsWith("_") && d.name !== "__pycache__")
        .map((d) => d.name)
        .sort()
    : [];

const readJson = <T,>(p: string, fallback: T): T => {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8")) as T;
  } catch {
    return fallback;
  }
};

const prettify = (slug: string) => slug.replace(/^\d+-/, "").replace(/-/g, " ");

function lessonMeta(module: string, slug: string): LessonMeta | null {
  const file = path.join(LEARN, module, slug, "lesson.md");
  if (!fs.existsSync(file)) return null;
  const { data } = matter(fs.readFileSync(file, "utf8"));
  return {
    id: `${module}/${slug}`,
    module,
    slug,
    title: data.title ?? prettify(slug),
    summary: data.summary ?? "",
    duration: Number(data.duration ?? 20),
    level: data.level ?? "초급",
    tags: data.tags ?? [],
    requiresKey: Boolean(data.requiresKey),
    objectives: data.objectives ?? [],
  };
}

export async function getCurriculum(): Promise<Module[]> {
  "use cache";
  return dirs(LEARN).map((m, i) => {
    const info = readJson(path.join(LEARN, m, "_module.json"), {} as Partial<Module>);
    return {
      slug: m,
      index: i + 1,
      title: info.title ?? prettify(m),
      description: info.description ?? "",
      icon: info.icon ?? "BookOpen",
      lessons: dirs(path.join(LEARN, m))
        .map((l) => lessonMeta(m, l))
        .filter((x): x is LessonMeta => !!x),
    };
  });
}

function readFilesRecursive(dir: string, base = dir, out: Record<string, string> = {}) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name.startsWith(".") || ent.name === "__pycache__") continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) readFilesRecursive(full, base, out);
    else if (/\.(py|txt|json|md|toml|yaml|yml|csv)$/.test(ent.name) && !["lesson.md", "quiz.json"].includes(ent.name))
      out[path.relative(base, full)] = fs.readFileSync(full, "utf8");
  }
  return out;
}

export async function getLesson(module: string, slug: string): Promise<Lesson | null> {
  "use cache";
  const dir = path.join(LEARN, module, slug);
  const meta = lessonMeta(module, slug);
  if (!meta) return null;
  const { content } = matter(fs.readFileSync(path.join(dir, "lesson.md"), "utf8"));
  const curriculum = await getCurriculum();
  const flat = curriculum.flatMap((m) => m.lessons);
  const idx = flat.findIndex((l) => l.id === meta.id);
  return {
    ...meta,
    body: content,
    files: readFilesRecursive(dir),
    quiz: readJson(path.join(dir, "quiz.json"), [] as QuizItem[]),
    prev: flat[idx - 1] ?? null,
    next: flat[idx + 1] ?? null,
    moduleTitle: curriculum.find((m) => m.slug === module)?.title ?? module,
  };
}

/* ------------------------------------------------------------------ Docs */
export type DocMeta = { category: string; slug: string; title: string; description: string; order: number; source?: string; tags: string[] };
export type DocCategory = { slug: string; title: string; description: string; icon: string; order: number; docs: DocMeta[] };

export async function getDocsIndex(): Promise<DocCategory[]> {
  "use cache";
  return dirs(DOCS)
    .map((c) => {
      const info = readJson(path.join(DOCS, c, "_category.json"), {} as Partial<DocCategory>);
      const docs = fs
        .readdirSync(path.join(DOCS, c))
        .filter((f) => f.endsWith(".md"))
        .map((f) => {
          const { data } = matter(fs.readFileSync(path.join(DOCS, c, f), "utf8"));
          return {
            category: c,
            slug: f.replace(/\.md$/, ""),
            title: data.title ?? prettify(f.replace(/\.md$/, "")),
            description: data.description ?? "",
            order: Number(data.order ?? 999),
            source: data.source,
            tags: data.tags ?? [],
          };
        })
        .sort((a, b) => a.order - b.order || a.slug.localeCompare(b.slug));
      return {
        slug: c,
        title: info.title ?? prettify(c),
        description: info.description ?? "",
        icon: info.icon ?? "FileText",
        order: info.order ?? 99,
        docs,
      };
    })
    .sort((a, b) => a.order - b.order);
}

export async function getDoc(category: string, slug: string) {
  "use cache";
  const file = path.join(DOCS, category, `${slug}.md`);
  if (!fs.existsSync(file)) return null;
  const { data, content } = matter(fs.readFileSync(file, "utf8"));
  return { title: (data.title as string) ?? slug, description: (data.description as string) ?? "", source: data.source as string | undefined, tags: (data.tags as string[]) ?? [], body: content };
}

/** Docs 검색 인덱스 (본문 일부 포함) */
export async function getDocsSearchIndex() {
  "use cache";
  const cats = await getDocsIndex();
  return cats.flatMap((c) =>
    c.docs.map((d) => {
      const { content } = matter(fs.readFileSync(path.join(DOCS, c.slug, `${d.slug}.md`), "utf8"));
      const headings = [...content.matchAll(/^#{2,3}\s+(.+)$/gm)].map((m) => m[1]);
      return { ...d, categoryTitle: c.title, headings, text: content.replace(/```[\s\S]*?```/g, " ").slice(0, 1500) };
    }),
  );
}
