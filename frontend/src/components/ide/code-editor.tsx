"use client";

import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
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

const VIEW_PREFIX = "agentlab-view:";

/** 파일별 스크롤·커서 위치를 브라우저에 저장한다. */
function readView(path: string) {
  try {
    return JSON.parse(localStorage.getItem(VIEW_PREFIX + path) || "null");
  } catch {
    return null;
  }
}
function writeView(path: string, state: unknown) {
  try {
    if (state) localStorage.setItem(VIEW_PREFIX + path, JSON.stringify(state));
  } catch {}
}
/** prefix 로 시작하는 파일들의 저장된 위치를 지운다 (코드를 원본으로 되돌릴 때). */
export function clearSavedViews(pathPrefix: string) {
  try {
    for (const k of Object.keys(localStorage)) if (k.startsWith(VIEW_PREFIX + pathPrefix)) localStorage.removeItem(k);
  } catch {}
}

export function CodeEditor({
  path,
  value,
  onChange,
  readOnly = false,
  markers = [],
  onRun,
  revealLine,
  persistView = false,
}: {
  path: string;
  value: string;
  onChange?: (v: string) => void;
  readOnly?: boolean;
  markers?: EditorMarker[];
  onRun?: () => void;
  revealLine?: { line: number; nonce: number } | null;
  /** true 면 파일(path)별로 마지막 스크롤·커서 위치를 저장했다가 다시 열 때 되살린다 */
  persistView?: boolean;
}) {
  const { resolvedTheme } = useTheme();
  const fontSize = useSettings((s) => s.editorFontSize);
  const editorRef = useRef<Ed | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const runRef = useRef(onRun);
  useEffect(() => {
    runRef.current = onRun;
  }, [onRun]);
  // cacheComponents 는 다른 페이지로 가면 이 화면을 지우지 않고 숨긴다(React Activity). 숨길 때 Monaco 가
  // 에디터를 dispose 하는데 React 상태는 남아 있어서, 다시 보일 때 "InstantiationService has been disposed" 로
  // 깨졌다. 숨겨질 때 key 를 바꿔 두면 다시 보일 때 새 에디터를 만든다 (내용은 value 로, 위치는 저장본으로 복원).
  const [instance, setInstance] = useState(0);
  useLayoutEffect(() => () => setInstance((n) => n + 1), []);
  const pathRef = useRef(path);
  const persistRef = useRef(persistView);
  useEffect(() => {
    persistRef.current = persistView;
  }, [persistView]);

  // 파일을 바꾸면 그 파일의 마지막 위치로 (라이브러리가 모델을 바꾼 뒤에 실행된다)
  useEffect(() => {
    pathRef.current = path;
    const ed = editorRef.current;
    if (!ed || !persistView) return;
    const saved = readView(path);
    if (saved) ed.restoreViewState(saved);
  }, [path, persistView]);

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
      key={instance}
      keepCurrentModel
      path={path}
      value={value}
      language={language}
      theme={resolvedTheme === "dark" ? "agentlab-dark" : "agentlab-light"}
      beforeMount={defineThemes}
      onMount={(ed, monaco) => {
        editorRef.current = ed;
        monacoRef.current = monaco;
        ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
        if (persistRef.current) {
          const saved = readView(pathRef.current);
          if (saved) ed.restoreViewState(saved);
          // 스크롤·커서가 움직이면 잠시 뒤 저장한다
          let t: ReturnType<typeof setTimeout> | undefined;
          const save = () => {
            clearTimeout(t);
            const p = pathRef.current;
            t = setTimeout(() => persistRef.current && writeView(p, ed.saveViewState()), 250);
          };
          ed.onDidScrollChange(save);
          ed.onDidChangeCursorPosition(save);
          ed.onDidDispose(() => clearTimeout(t));
        }
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
