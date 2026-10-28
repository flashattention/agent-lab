"use client";

import { Children, isValidElement, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import rehypeHighlight from "rehype-highlight";
import { AlertTriangle, Check, Copy, Info, Lightbulb, OctagonAlert, Play, Sparkles } from "lucide-react";
import { Mermaid } from "./mermaid";

/* ------------------------------------------------------------------ GitHub alert 플러그인 */
type MdNode = { type: string; value?: string; children?: MdNode[]; data?: Record<string, unknown> };

const ALERTS = {
  NOTE: { label: "참고", icon: Info, cls: "border-accent-2/40 bg-accent-2/5", color: "text-accent-2" },
  TIP: { label: "팁", icon: Lightbulb, cls: "border-success/40 bg-success/5", color: "text-success" },
  IMPORTANT: { label: "중요", icon: Sparkles, cls: "border-accent/40 bg-accent/5", color: "text-accent" },
  WARNING: { label: "주의", icon: AlertTriangle, cls: "border-warning/40 bg-warning/5", color: "text-warning" },
  CAUTION: { label: "경고", icon: OctagonAlert, cls: "border-danger/40 bg-danger/5", color: "text-danger" },
} as const;

function remarkAlerts() {
  return (tree: MdNode) => {
    const walk = (node: MdNode) => {
      if (node.type === "blockquote") {
        const para = node.children?.[0];
        const first = para?.children?.[0];
        const m = first?.type === "text" && first.value?.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/);
        if (m && first) {
          first.value = first.value!.slice(m[0].length);
          node.data = { hName: "aside", hProperties: { "data-alert": m[1] } };
        }
      }
      node.children?.forEach(walk);
    };
    walk(tree);
  };
}

/* ------------------------------------------------------------------ 코드 블록 */
function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

function CodeBlock({ children, onRun }: { children: ReactNode; onRun?: (code: string) => void }) {
  const [copied, setCopied] = useState(false);
  const child = Children.only(children) as React.ReactElement<{ className?: string; children?: ReactNode }>;
  const lang = /language-(\w+)/.exec(child.props.className || "")?.[1] ?? "";
  const code = textOf(child.props.children).replace(/\n$/, "");

  if (lang === "mermaid") return <Mermaid chart={code} />;

  return (
    <div className="group relative">
      <div className="absolute top-2 right-2 z-10 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        {lang && <span className="rounded px-1.5 py-0.5 font-mono text-[10px] text-muted uppercase">{lang}</span>}
        {onRun && lang === "python" && (
          <button
            onClick={() => onRun(code)}
            title="IDE에서 열어 실행"
            className="flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-[11px] text-fg-2 hover:border-accent hover:text-accent"
          >
            <Play className="h-3 w-3" /> IDE로
          </button>
        )}
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 1400);
          }}
          className="rounded-md border border-border bg-surface p-1.5 text-muted hover:text-fg"
          title="복사"
        >
          {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

export function Markdown({ source, onRunSnippet }: { source: string; onRunSnippet?: (code: string) => void }) {
  const components: Components = {
    pre: ({ children }) => <CodeBlock onRun={onRunSnippet}>{children}</CodeBlock>,
    aside: (props) => {
      const kind = (props as { "data-alert"?: keyof typeof ALERTS })["data-alert"] ?? "NOTE";
      const a = ALERTS[kind] ?? ALERTS.NOTE;
      const Icon = a.icon;
      return (
        <div className={`my-5 rounded-xl border px-4 py-3 ${a.cls} [&>p]:my-1`}>
          <div className={`mb-1 flex items-center gap-1.5 text-[13px] font-semibold ${a.color}`}>
            <Icon className="h-4 w-4" /> {a.label}
          </div>
          {props.children}
        </div>
      );
    },
    a: ({ href, children }) => (
      <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
        {children}
      </a>
    ),
  };
  return (
    <div className="prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkAlerts]}
        rehypePlugins={[rehypeSlug, [rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={components}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
