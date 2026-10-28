import { getDocsIndex, getDocsSearchIndex } from "@/lib/content";
import { DocsSidebar } from "@/components/docs/docs-sidebar";

export default async function DocsLayout({ children }: LayoutProps<"/docs">) {
  const [index, search] = await Promise.all([getDocsIndex(), getDocsSearchIndex()]);
  return (
    <div className="flex min-h-0 flex-1">
      <DocsSidebar index={index} search={search} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
