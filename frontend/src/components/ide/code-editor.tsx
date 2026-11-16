"use client";

import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";
import { useSettings } from "@/lib/settings";

type Monaco = Parameters<BeforeMount>[0];
type Ed = Parameters<OnMount>[0];

export type EditorMarker = { line: number; message: string; severity?: "error" | "warning" };

const defineThemes: BeforeMount = (monaco) => {
  monaco.editor.defineTheme("agentlab-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "6b6b78", fontStyle: "italic" },
      { token: "keyword", foreground: "ffffff", fontStyle: "bold" },
      { token: "string", foreground: "6ee7b7" },
      { token: "number", foreground: "fcd34d" },
    ],
    colors: {
      "editor.background": "#0a0a0a",
      "editor.lineHighlightBackground": "#161616",
      "editorLineNumber.foreground": "#3a3a3a",
      "editorLineNumber.activeForeground": "#a3a3a3",
      "editorGutter.background": "#0a0a0a",
      "editor.selectionBackground": "#ffffff2e",
    },
  });
  monaco.editor.defineTheme("agentlab-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "8a8a95", fontStyle: "italic" },
      { token: "keyword", foreground: "0a0a0a", fontStyle: "bold" },
      { token: "string", foreground: "059669" },
      { token: "number", foreground: "d97706" },
    ],
    colors: {
      "editor.background": "#ffffff",
      "editor.lineHighlightBackground": "#f5f5f5",
      "editorLineNumber.foreground": "#cccccc",
      "editorGutter.background": "#ffffff",
    },
  });
};

export function CodeEditor({
  path,
  value,
  onChange,
  readOnly = false,
  markers = [],
  onRun,
  revealLine,
}: {
  path: string;
  value: string;
  onChange?: (v: string) => void;
  readOnly?: boolean;
  markers?: EditorMarker[];
  onRun?: () => void;
  revealLine?: { line: number; nonce: number } | null;
}) {
  const { resolvedTheme } = useTheme();
  const fontSize = useSettings((s) => s.editorFontSize);
  const editorRef = useRef<Ed | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const runRef = useRef(onRun);
  useEffect(() => {
    runRef.current = onRun;
  }, [onRun]);

  const language = path.endsWith(".py")
    ? "python"
    : path.endsWith(".json")
      ? "json"
      : path.endsWith(".md")
        ? "markdown"
        : path.endsWith(".toml")
          ? "ini"
          : path.endsWith(".yaml") || path.endsWith(".yml")
            ? "yaml"
            : path.endsWith("Dockerfile")
              ? "dockerfile"
              : "plaintext";

  // 실행 오류 위치 마커
  useEffect(() => {
    const ed = editorRef.current;
    const monaco = monacoRef.current;
    const model = ed?.getModel();
    if (!ed || !monaco || !model) return;
    monaco.editor.setModelMarkers(
      model,
      "agentlab",
      markers
        .filter((m) => m.line >= 1 && m.line <= model.getLineCount())
        .map((m) => ({
          startLineNumber: m.line,
          endLineNumber: m.line,
          startColumn: model.getLineFirstNonWhitespaceColumn(m.line) || 1,
          endColumn: model.getLineMaxColumn(m.line),
          message: m.message,
          severity: m.severity === "warning" ? monaco.MarkerSeverity.Warning : monaco.MarkerSeverity.Error,
        })),
    );
  }, [markers, path, value]);

  useEffect(() => {
    if (!revealLine || !editorRef.current) return;
    editorRef.current.revealLineInCenter(revealLine.line);
    editorRef.current.setPosition({ lineNumber: revealLine.line, column: 1 });
    editorRef.current.focus();
  }, [revealLine]);

  return (
    <Editor
      path={path}
      value={value}
      language={language}
      theme={resolvedTheme === "dark" ? "agentlab-dark" : "agentlab-light"}
      beforeMount={defineThemes}
      onMount={(ed, monaco) => {
        editorRef.current = ed;
        monacoRef.current = monaco;
        ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
      }}
      onChange={(v) => onChange?.(v ?? "")}
      loading={<div className="grid h-full place-items-center text-xs text-muted">에디터 로딩 중…</div>}
      options={{
        readOnly,
        fontSize,
        fontFamily: "var(--font-geist-mono), ui-monospace, Menlo, monospace",
        fontLigatures: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        padding: { top: 12, bottom: 12 },
        renderLineHighlight: "line",
        tabSize: 4,
        automaticLayout: true,
        wordWrap: "off",
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
        stickyScroll: { enabled: true },
        bracketPairColorization: { enabled: true },
        guides: { indentation: true, bracketPairs: true },
      }}
    />
  );
}
