"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
} from "@xyflow/react";
import { useTheme } from "next-themes";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Eraser,
  FileCode2,
  LayoutGrid,
  Library,
  Loader2,
  Menu,
  Network,
  OctagonAlert,
  Play,
  Redo2,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Square,
  Undo2,
  X,
} from "lucide-react";
import { analyze } from "@/lib/playground/analyze";
import { generateProject, normalizeGraph } from "@/lib/playground/codegen";
import { KINDS } from "@/lib/playground/catalog";
import { PATTERNS } from "@/lib/playground/patterns";
import type { NodeKind } from "@/lib/playground/types";
import { lookupRefined, refineCode, validateCode, type ValidateReport } from "@/lib/api";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { CodeEditor, type EditorMarker } from "@/components/ide/code-editor";
import { ConsolePanel } from "@/components/ide/console-panel";
import { TracePanel } from "@/components/ide/trace-panel";
import { buildTrace, nodeStates } from "@/lib/trace";
import { useNavOverlay } from "@/lib/chrome";
import { parseTraceback, useRunner } from "@/components/ide/use-runner";
import { SplitGroup, SplitHandle, SplitPanel } from "@/components/ui/split";
import { AgentNode, type NodeStatus } from "./agent-node";
import { Explorer } from "./explorer";
import { PatternsDialog } from "./patterns-dialog";
import { ProjectBar } from "./project-bar";
import { RightPanel, type RightTab } from "./right-panel";
import { CANVAS_TAB, toGraph, usePlayground } from "./store";
import { useProjectSync } from "./use-project-sync";
import { useAuth } from "@/lib/auth";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { SignInButton } from "@/components/auth/auth-menu";

const nodeTypes = { agent: AgentNode };

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Workspace() {
  const s = usePlayground();
  const { resolvedTheme } = useTheme();
  const rf = useReactFlow();
  const apiKey = useSettings((x) => x.apiKey);
  const setSettingsOpen = useSettings((x) => x.setOpen);
  const runner = useRunner();
  const sync = useProjectSync();
  const user = useAuth((x) => x.user);
  const needLogin = SUPABASE_ENABLED && !user; // 코드 실행·검증·고도화는 로그인한 사용자만
  const [showPatterns, setShowPatterns] = useState(false);
  const [bottomTab, setBottomTab] = useState<"problems" | "terminal">("problems");
  const [rightTab, setRightTab] = useState<RightTab>("palette");
  const setNavOpen = useNavOverlay((x) => x.setOpen);
  const [validation, setValidation] = useState<ValidateReport | null>(null);
  const [busy, setBusy] = useState<null | "validate" | "refine">(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error" | "info" | "login"; text: string } | null>(null);
  const [markers, setMarkers] = useState<Record<string, EditorMarker[]>>({});
  const [reveal, setReveal] = useState<{ line: number; nonce: number } | null>(null);
  const [mounted, setMounted] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);
  // 처음 방문하면 ReAct 패턴으로 시작
  useEffect(() => {
    const st = usePlayground.getState();
    const onProject = !!st.projectId || new URLSearchParams(window.location.search).has("p");
    if (mounted && !onProject && st.nodes.length === 0 && !st.patternId) {
      usePlayground.getState().loadGraph(PATTERNS[0].graph, PATTERNS[0].id);
      setTimeout(() => rf.fitView({ padding: 0.2 }), 50);
    }
  }, [mounted, rf]);

  const graph = useMemo(() => toGraph(s), [s.nodes, s.edges, s.settings]); // eslint-disable-line react-hooks/exhaustive-deps
  // 좌표 이동만으로는 코드/분석이 바뀌지 않도록 구조 시그니처를 따로 계산
  const signature = useMemo(() => JSON.stringify(normalizeGraph(graph)), [graph]);
  const structural = useMemo(() => JSON.parse(signature), [signature]); // eslint-disable-line react-hooks/exhaustive-deps
  const analysis = useMemo(() => analyze(graph), [signature]); // eslint-disable-line react-hooks/exhaustive-deps
  const generated = useMemo(() => (graph.nodes.length ? generateProject(graph) : {}), [signature]); // eslint-disable-line react-hooks/exhaustive-deps

  const refinedValid = s.refined && s.refined.key === signature ? s.refined : null;
  const baseFiles = refinedValid && s.useRefined ? refinedValid.files : generated;
  const files = useMemo(() => ({ ...baseFiles, ...Object.fromEntries(Object.entries(s.overrides).filter(([k]) => k in baseFiles)) }), [baseFiles, s.overrides]);
  const modified = useMemo(() => new Set(Object.keys(s.overrides).filter((k) => k in baseFiles && baseFiles[k] !== s.overrides[k])), [s.overrides, baseFiles]);

  // 구조가 바뀌면 사용자 수정본/검증 결과를 초기화
  const lastSig = useRef(signature);
  useEffect(() => {
    if (lastSig.current !== signature) {
      lastSig.current = signature;
      if (Object.keys(usePlayground.getState().overrides).length) usePlayground.getState().resetOverrides();
      setValidation(null);
      setMarkers({});
    }
  }, [signature]);

  // 검증된 고도화 코드가 캐시에 있으면 자동으로 가져온다 (LLM 호출 없음)
  const debouncedSig = useDebounced(signature, 900);
  useEffect(() => {
    if (!analysis.ok || !graph.nodes.length) return;
    if (usePlayground.getState().refined?.key === debouncedSig) return;
    let alive = true;
    lookupRefined(JSON.parse(debouncedSig))
      .then((r) => {
        if (alive && r.hit) usePlayground.getState().setRefined({ key: debouncedSig, files: r.hit.files, notes: r.hit.notes, model: r.hit.model, cached: true });
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [debouncedSig]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ------------------------------------------------------------ 실행 트레이스 */
  const running = runner.status === "running";
  const traceTree = useMemo(() => buildTrace(runner.trace, running), [runner.trace, running]);
  const runStates = useMemo(() => nodeStates(traceTree), [traceTree]);
  // 실행 중 첫 트레이스가 들어오면 오른쪽 트레이스 탭으로 한 번 전환
  const traceSwitched = useRef(false);
  useEffect(() => {
    if (!running) return;
    if (!traceTree.order.length) traceSwitched.current = false;
    else if (!traceSwitched.current) {
      traceSwitched.current = true;
      setRightTab("trace");
    }
  }, [running, traceTree.order.length]);

  /* ------------------------------------------------------------ 캔버스 표시용 노드/엣지 */
  const statusOf = (id: string): NodeStatus => (analysis.errorNodes.has(id) ? "error" : analysis.warnNodes.has(id) ? "warn" : "ok");
  const viewNodes = useMemo(
    () => s.nodes.map((n) => ({ ...n, data: { ...n.data, __status: statusOf(n.id), __run: runStates.get(n.data.name) } })),
    [s.nodes, analysis, runStates], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const viewEdges: Edge[] = useMemo(
    () =>
      s.edges.map((e) => {
        const src = s.nodes.find((n) => n.id === e.source);
        const tgt = s.nodes.find((n) => n.id === e.target);
        const conditional = !!src && ["router", "supervisor", "evaluator", "map"].includes(src.data.kind);
        const label =
          src?.data.kind === "evaluator" || src?.data.kind === "human"
            ? e.sourceHandle === "reject"
              ? "거절"
              : e.sourceHandle ?? undefined
            : src?.data.kind === "router" || src?.data.kind === "supervisor"
              ? tgt?.data.kind === "end"
                ? "END"
                : tgt?.data.name
              : src?.data.kind === "map"
                ? "Send(…)"
                : undefined;
        const err = analysis.errorEdges.has(e.id);
        const warn = analysis.warnEdges.has(e.id);
        return {
          ...e,
          type: "smoothstep",
          label: label === "approve" ? "승인" : label,
          animated: conditional || err,
          className: cn(err && "edge-error", !err && warn && "edge-warn", conditional && "edge-conditional"),
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: err ? "var(--danger)" : "var(--border-strong)" },
        };
      }),
    [s.edges, s.nodes, analysis],
  );

  const addAt = useCallback(
    (kind: NodeKind, pos?: { x: number; y: number }) => {
      let position = pos;
      if (!position) {
        const r = canvasRef.current?.getBoundingClientRect();
        position = rf.screenToFlowPosition({ x: (r?.left ?? 0) + (r?.width ?? 600) / 2, y: (r?.top ?? 0) + (r?.height ?? 400) / 2 });
        position = { x: position.x - 110, y: position.y - 40 };
        // 이미 있는 노드와 겹치지 않는 자리를 찾을 때까지 오른쪽 아래로 옮긴다
        const taken = (q: { x: number; y: number }) => usePlayground.getState().nodes.some((n) => Math.abs(n.position.x - q.x) < 230 && Math.abs(n.position.y - q.y) < 100);
        for (let i = 0; i < 12 && taken(position); i++) position = { x: position.x + 250, y: position.y + (i % 3 === 2 ? 110 : 0) };
      }
      s.addNode(kind, position);
      s.setActiveTab(CANVAS_TAB);
    },
    [rf, s],
  );

  // 프로젝트를 새로 열면 화면에 맞춘다
  useEffect(() => {
    if (s.projectId) setTimeout(() => rf.fitView({ padding: 0.2 }), 60);
  }, [s.projectId, rf]);

  /* ------------------------------------------------------------ 액션 */
  const askLogin = () => setNotice({ kind: "login", text: "코드 실행, 검증, 고도화는 로그인 후 사용할 수 있습니다." });

  // 공유받은 프로젝트에 작성자가 고친 코드가 있으면, 내 키로 실행하기 전에 확인한다
  const [confirmShared, setConfirmShared] = useState(false);
  const sharedEdited = sync.state === "viewing" && modified.size > 0;

  const run = async (opts: { confirmed?: boolean; noKey?: boolean } = {}) => {
    if (needLogin) return askLogin();
    if (sharedEdited && apiKey && !opts.confirmed) return setConfirmShared(true);
    setConfirmShared(false);
    setBottomTab("terminal");
    setMarkers({});
    const res = await runner.run(files, "main.py", { timeout: 90, noKey: opts.noKey });
    if (!res.ok) {
      const loc = parseTraceback(res.stderr, Object.keys(files));
      if (loc) setMarkers({ [loc.file]: [{ line: loc.line, message: loc.message }] });
    }
  };

  const validate = async () => {
    if (needLogin) return askLogin();
    setBusy("validate");
    setBottomTab("problems");
    try {
      const r = await validateCode(files);
      setValidation(r);
      const m: Record<string, EditorMarker[]> = {};
      for (const i of r.lint) (m[i.file] ??= []).push({ line: i.line, message: `${i.code} ${i.message}` });
      if (r.run && !r.ok) {
        const loc = parseTraceback(r.run.stderr, Object.keys(files));
        if (loc) (m[loc.file] ??= []).push({ line: loc.line, message: loc.message });
      }
      setMarkers(m);
      setNotice(r.ok ? { kind: "ok", text: "문법 검사 + Mock 실행 검증 통과" } : { kind: "error", text: "검증 실패 — 문제 탭을 확인하세요" });
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const refine = async () => {
    if (needLogin) return askLogin();
    setBusy("refine");
    setNotice({ kind: "info", text: "고성능 LLM이 코드를 고도화하고, 문법 검사와 실행 검증을 진행 중입니다… (최대 1~2분)" });
    try {
      const r = await refineCode(JSON.parse(signature), generated);
      if (r.files) {
        s.setRefined({ key: signature, files: r.files, notes: r.notes ?? "", model: r.model, cached: r.cached });
        s.setUseRefined(true);
        setNotice({ kind: "ok", text: r.cached ? "캐시된 검증 코드를 불러왔습니다 (LLM 호출 없음)" : `고도화 완료 · ${r.attempts?.length ?? 1}회 시도 만에 검증 통과 → 캐시에 저장됨` });
      } else setNotice({ kind: "error", text: r.error ?? "고도화 실패" });
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const download = async () => {
    const JSZip = (await import("jszip")).default;
    const zip = new JSZip();
    for (const [p, c] of Object.entries(files)) zip.file(`langgraph-agent/${p}`, c);
    const blob = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(s.projectId && s.projectName.trim().replace(/[\\/:*?"<>|\s]+/g, "-")) || s.patternId || "langgraph-agent"}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  useEffect(() => {
    if (!notice || notice.kind === "info" || notice.kind === "login") return;
    const t = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  // 단축키: 실행 취소/다시 실행, 실행, 저장. 입력 중이거나 코드 편집기 안에서는 편집기 쪽 단축키를 그대로 둔다.
  const runRef = useRef<() => void>(() => {});
  useEffect(() => {
    runRef.current = () => run();
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const el = e.target as HTMLElement | null;
      const typing = !!el?.closest("input, textarea, select, [contenteditable=true], .monaco-editor");
      const k = e.key.toLowerCase();
      if (k === "s") {
        e.preventDefault();
        sync.flush();
      } else if (k === "enter" && !typing) {
        e.preventDefault();
        runRef.current();
      } else if (k === "z" && !typing) {
        e.preventDefault();
        if (e.shiftKey) usePlayground.getState().redo();
        else usePlayground.getState().undo();
      } else if (k === "y" && !typing) {
        e.preventDefault();
        usePlayground.getState().redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sync.flush]); // eslint-disable-line react-hooks/exhaustive-deps

  const errors = analysis.issues.filter((i) => i.level === "error");
  const warnings = analysis.issues.filter((i) => i.level === "warning");
  const activeFile = s.activeTab !== CANVAS_TAB && files[s.activeTab] !== undefined ? s.activeTab : null;

  const focusNodes = (ids?: string[]) => {
    if (!ids?.length) return;
    s.setActiveTab(CANVAS_TAB);
    s.select(ids[0]);
    setTimeout(() => rf.fitView({ nodes: ids.map((id) => ({ id })), padding: 0.6, duration: 400, maxZoom: 1.2 }), 30);
  };

  if (!mounted) return <div className="grid flex-1 place-items-center text-sm text-muted">플레이그라운드 로딩 중…</div>;

  return (
    <div className="flex h-dvh min-h-0 flex-col">
      <SplitGroup orientation="horizontal" className="min-h-0 flex-1">
        {/* 왼쪽: 툴바 + 파일 탐색기 + 하단 패널(문제/터미널/트레이스) */}
        <SplitPanel defaultSize="25" minSize="16">
          <div className="flex h-full min-h-0 flex-col bg-surface">
            <div className="shrink-0 space-y-1.5 border-b border-border px-2 py-2">
              <div className="flex min-w-0 items-center gap-1">
                <button
                  onClick={() => setNavOpen(true)}
                  title="메뉴 열기 (학습 · Docs · 설정 · 로그인)"
                  aria-label="메뉴 열기"
                  className="relative grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent text-accent-fg hover:brightness-110"
                >
                  <Menu className="h-4 w-4" />
                  {!apiKey && <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-warning ring-2 ring-surface" />}
                </button>
                <div className="min-w-0 flex-1">
                  {SUPABASE_ENABLED ? <ProjectBar sync={sync} /> : <span className="px-1.5 text-sm font-semibold">플레이그라운드</span>}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-0.5">
                <button onClick={() => setShowPatterns(true)} className="mr-1 flex shrink-0 items-center gap-1.5 rounded-lg bg-accent-soft px-2.5 py-1.5 text-xs font-semibold text-accent hover:brightness-105">
                  <Library className="h-3.5 w-3.5" /> 패턴 예시
                </button>
                <ToolButton icon={Undo2} label="실행 취소" title="실행 취소 (Ctrl/⌘+Z)" onClick={s.undo} disabled={!s.past.length} />
                <ToolButton icon={Redo2} label="다시 실행" title="다시 실행 (Ctrl/⌘+Shift+Z)" onClick={s.redo} disabled={!s.future.length} />
                <ToolButton icon={LayoutGrid} label="자동 정렬" onClick={() => { s.autoLayout(); setTimeout(() => rf.fitView({ padding: 0.2, duration: 300 }), 30); }} />
                <ToolButton icon={Eraser} label="비우기" onClick={() => confirm("캔버스를 비울까요?") && s.clear()} />
                <ToolButton icon={Download} label="ZIP 다운로드" onClick={download} disabled={!graph.nodes.length} />
                <div
                  title={errors.length ? `구조 오류 ${errors.length}` : warnings.length ? `경고 ${warnings.length}` : graph.nodes.length ? "구조 정상" : "비어 있음"}
                  className={cn(
                    "ml-auto flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium",
                    errors.length ? "bg-danger/10 text-danger" : warnings.length ? "bg-warning/10 text-warning" : graph.nodes.length ? "bg-success/10 text-success" : "text-muted",
                  )}
                >
                  {errors.length ? <OctagonAlert className="h-3.5 w-3.5" /> : warnings.length ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  {errors.length ? `오류 ${errors.length}` : warnings.length ? `경고 ${warnings.length}` : graph.nodes.length ? "정상" : "비어 있음"}
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={validate}
                  disabled={!!busy || !analysis.ok}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-xs font-medium hover:bg-surface-2 disabled:opacity-40"
                  title="ruff 문법 검사 + Mock LLM 실행 검증"
                >
                  {busy === "validate" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />} 검증
                </button>
                <button
                  onClick={() => (apiKey || refinedValid ? refine() : setSettingsOpen(true))}
                  disabled={!!busy || !analysis.ok}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-2 py-1.5 text-xs font-semibold whitespace-nowrap text-accent hover:border-accent disabled:opacity-40"
                  title="고성능 LLM으로 코드를 고도화하고, 검증을 통과하면 구조별로 캐싱합니다"
                >
                  {busy === "refine" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} 고도화
                </button>
                {runner.status === "running" ? (
                  <button onClick={runner.stop} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-danger px-2 py-1.5 text-xs font-semibold text-white">
                    <Square className="h-3 w-3 fill-current" /> 중지
                  </button>
                ) : (
                  <button
                    onClick={() => run()}
                    disabled={!analysis.ok}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-accent px-2 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110 disabled:opacity-40"
                    title={analysis.ok ? "main.py 실행 (Ctrl/⌘+Enter)" : "구조 오류를 먼저 해결하세요"}
                  >
                    <Play className="h-3 w-3 fill-current" /> 실행
                  </button>
                )}
              </div>
            </div>

            {sync.state === "missing" && (
              <div className="shrink-0 border-b border-warning/30 bg-warning/10 px-3 py-1.5 text-[11.5px] text-warning">
                이 링크의 프로젝트를 열 수 없습니다. 삭제되었거나 공유가 꺼져 있습니다. 본인 프로젝트라면 로그인해 주세요.
              </div>
            )}
            {sync.state === "viewing" && (
              <div className="shrink-0 border-b border-border bg-surface-2 px-3 py-1.5 text-[11.5px] text-muted">
                공유받은 프로젝트입니다. 여기서 고친 내용은 저장되지 않습니다. 계속 작업하려면 내 프로젝트로 복제하세요.
              </div>
            )}

            <SplitGroup orientation="vertical" className="min-h-0 flex-1">
              <SplitPanel defaultSize="38" minSize="12">
                <Explorer
                  files={files}
                  active={s.activeTab}
                  modified={modified}
                  onOpen={s.openTab}
                  title="Explorer"
                  badge={
                    refinedValid ? (
                      <button
                        onClick={() => s.setUseRefined(!s.useRefined)}
                        className={cn("flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold", s.useRefined ? "bg-accent-soft text-accent" : "bg-surface-2 text-muted")}
                        title="LLM 고도화 코드 ↔ 템플릿 코드 전환"
                      >
                        <Sparkles className="h-3 w-3" /> {s.useRefined ? "고도화" : "템플릿"}
                      </button>
                    ) : (
                      <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] text-muted">템플릿</span>
                    )
                  }
                />
              </SplitPanel>
              <SplitHandle vertical />
              <SplitPanel defaultSize="62" minSize="15">
                <div className="flex h-full min-h-0 flex-col">
                  <div className="flex h-8 shrink-0 items-stretch border-b border-border bg-surface text-xs">
                    {(["problems", "terminal"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setBottomTab(t)}
                        className={cn("flex items-center gap-1.5 border-b-2 px-3", bottomTab === t ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")}
                      >
                        {t === "problems" ? "문제" : "터미널"}
                        {t === "problems" && (errors.length + warnings.length > 0) && (
                          <span className={cn("rounded-full px-1.5 text-[10px] font-bold text-white", errors.length ? "bg-danger" : "bg-warning")}>{errors.length + warnings.length}</span>
                        )}
                        {t === "terminal" && running && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
                      </button>
                    ))}
                  </div>
                  <div className="min-h-0 flex-1">
                    {bottomTab === "terminal" ? (
                      <ConsolePanel
                        lines={runner.lines}
                        status={runner.status}
                        mock={runner.meta?.mock}
                        onClear={runner.clear}
                        title="python main.py"
                        onJump={(f, line) => {
                          const hit = Object.keys(files).find((x) => x === f || f.endsWith("/" + x));
                          if (!hit) return;
                          s.openTab(hit);
                          setTimeout(() => setReveal({ line, nonce: Date.now() }), 60);
                        }}
                      />
                    ) : (
                      <ProblemsPanel analysis={analysis} validation={validation} refinedNotes={refinedValid?.notes} onFocus={focusNodes} />
                    )}
                  </div>
                </div>
              </SplitPanel>
            </SplitGroup>
          </div>
        </SplitPanel>
        <SplitHandle />

        {/* 가운데: 탭 (캔버스 + 파일) — 화면 높이 전체 */}
        <SplitPanel defaultSize="53" minSize="30">
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex h-9 shrink-0 items-stretch overflow-x-auto border-b border-border bg-surface-2/60">
              {s.tabs.map((t) => (
                <div
                  key={t}
                  onClick={() => s.setActiveTab(t)}
                  className={cn(
                    "group flex shrink-0 cursor-pointer items-center gap-1.5 border-r border-border px-3 text-[12px]",
                    s.activeTab === t ? "bg-surface text-fg" : "text-muted hover:text-fg",
                  )}
                >
                  {t === CANVAS_TAB ? <Network className="h-3.5 w-3.5 text-accent" /> : <FileCode2 className="h-3.5 w-3.5 opacity-60" />}
                  <span className={t === CANVAS_TAB ? "font-medium" : "font-mono"}>{t === CANVAS_TAB ? "Canvas" : t.split("/").pop()}</span>
                  {modified.has(t) && <span className="h-1.5 w-1.5 rounded-full bg-warning" />}
                  {t !== CANVAS_TAB && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        s.closeTab(t);
                      }}
                      className="rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-surface-3"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
              ))}
              {activeFile && modified.has(activeFile) && (
                <button onClick={() => s.setOverride(activeFile, null)} className="ml-auto flex shrink-0 items-center gap-1 px-3 text-[11px] text-muted hover:text-fg">
                  <RotateCcw className="h-3 w-3" /> 생성 코드로 되돌리기
                </button>
              )}
            </div>
            <div className="relative min-h-0 flex-1">
              <div
                ref={canvasRef}
                className={cn("absolute inset-0 transition-[box-shadow]", s.activeTab !== CANVAS_TAB && "invisible", errors.length > 0 && "shadow-[inset_0_0_0_2px_var(--danger)]")}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const kind = e.dataTransfer.getData("application/agentlab-node") as NodeKind;
                  if (!kind || !KINDS[kind]) return;
                  const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
                  addAt(kind, { x: p.x - 110, y: p.y - 30 });
                }}
              >
                <ReactFlow
                  nodes={viewNodes}
                  edges={viewEdges}
                  nodeTypes={nodeTypes}
                  onNodesChange={s.onNodesChange}
                  onEdgesChange={s.onEdgesChange}
                  onConnect={s.onConnect}
                  onNodeClick={(_, n) => s.select(n.id)}
                  onPaneClick={() => s.select(null)}
                  colorMode={resolvedTheme === "dark" ? "dark" : "light"}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  deleteKeyCode={["Backspace", "Delete"]}
                  proOptions={{ hideAttribution: true }}
                  minZoom={0.2}
                >
                  <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="var(--grid)" />
                  <Controls showInteractive={false} />
                  <MiniMap pannable zoomable nodeColor={(n) => KINDS[(n.data as { kind: NodeKind }).kind]?.color ?? "#888"} maskColor="color-mix(in srgb, var(--bg) 70%, transparent)" />
                </ReactFlow>
                {errors.length > 0 && (
                  <button
                    onClick={() => setBottomTab("problems")}
                    className="fade-in absolute top-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border border-danger/40 bg-surface px-4 py-1.5 text-xs font-medium text-danger shadow-soft"
                  >
                    <OctagonAlert className="h-4 w-4" /> 실행 전 구조 오류 {errors.length}개 — 빨간 노드/엣지를 확인하세요
                  </button>
                )}
                {graph.nodes.length === 0 && (
                  <div className="pointer-events-none absolute inset-0 grid place-items-center">
                    <div className="text-center text-sm text-muted">
                      오른쪽 컴포넌트를 끌어다 놓거나
                      <br />
                      <b className="text-accent">패턴 예시</b>를 불러오세요.
                    </div>
                  </div>
                )}
              </div>
              {activeFile && (
                <div className="absolute inset-0">
                  <CodeEditor
                    path={`playground/${activeFile}`}
                    value={files[activeFile]}
                    onChange={(v) => s.setOverride(activeFile, v)}
                    markers={markers[activeFile]}
                    onRun={() => run()}
                    revealLine={reveal}
                  />
                </div>
              )}
              {notice && (
                <div
                  className={cn(
                    "fade-in absolute bottom-4 left-1/2 z-20 flex max-w-[92%] -translate-x-1/2 items-center gap-2 rounded-full border bg-surface px-4 py-1.5 text-xs shadow-soft",
                    notice.kind === "ok" && "border-success/40 text-success",
                    notice.kind === "error" && "border-danger/40 text-danger",
                    (notice.kind === "info" || notice.kind === "login") && "border-accent/40 text-accent",
                  )}
                >
                  {notice.kind === "info" && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />}
                  <span className="min-w-0">{notice.text}</span>
                  {notice.kind === "login" && <SignInButton />}
                  <button onClick={() => setNotice(null)} className="shrink-0 opacity-70 hover:opacity-100" aria-label="닫기">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </SplitPanel>
        <SplitHandle />

        {/* 오른쪽: 컴포넌트 / 속성 / 그래프 / 트레이스 */}
        <SplitPanel defaultSize="22" minSize="14">
          <RightPanel
            onAdd={(k) => addAt(k)}
            tab={rightTab}
            onTab={setRightTab}
            running={running}
            traceCount={traceTree.order.length}
            trace={<TracePanel events={runner.trace} live={running} />}
          />
        </SplitPanel>
      </SplitGroup>

      {confirmShared && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && setConfirmShared(false)}>
          <div role="dialog" aria-modal="true" aria-label="공유 프로젝트 실행 확인" className="fade-in w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-soft">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="h-4 w-4 text-warning" /> 다른 사람이 수정한 코드가 들어 있습니다
            </div>
            <p className="text-[12.5px] leading-relaxed text-fg-2">
              이 공유 프로젝트에는 작성자가 직접 고친 파일이 있습니다. API 키 문자열은 실행 코드에 전달되지 않지만, 코드가 실행되는 동안 <b>내 키로 OpenAI를 호출해 비용을 발생시킬 수는 있습니다.</b>{" "}
              먼저 코드를 확인하거나 Mock 모드로 실행해 보세요.
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {[...modified].map((f) => (
                <button
                  key={f}
                  onClick={() => {
                    s.openTab(f);
                    setConfirmShared(false);
                  }}
                  className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-2 hover:text-accent"
                >
                  {f}
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setConfirmShared(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-fg">
                취소
              </button>
              <button onClick={() => run({ confirmed: true })} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-2">
                내 키로 실행
              </button>
              <button onClick={() => run({ confirmed: true, noKey: true })} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-fg hover:brightness-110">
                Mock 모드로 실행
              </button>
            </div>
          </div>
        </div>
      )}

      <PatternsDialog
        open={showPatterns}
        onClose={() => setShowPatterns(false)}
        onPick={(p) => {
          s.loadGraph(p.graph, p.id);
          setShowPatterns(false);
          setNotice({ kind: "ok", text: `'${p.title}' 패턴을 불러왔습니다. 왼쪽 파일을 열어 생성된 코드를 확인하고 ▶ 실행해 보세요.` });
          setTimeout(() => rf.fitView({ padding: 0.2, duration: 400 }), 60);
        }}
      />
      {/* structural 은 캐시 키 계산에 사용 — 디버깅 시 확인용 */}
      <span hidden data-structure={structural ? "1" : "0"} />
    </div>
  );
}

function ToolButton({ icon: I, label, title, onClick, disabled }: { icon: typeof Play; label: string; title?: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} title={title ?? label} aria-label={label} className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40">
      <I className="h-3.5 w-3.5" />
    </button>
  );
}

function ProblemsPanel({
  analysis,
  validation,
  refinedNotes,
  onFocus,
}: {
  analysis: ReturnType<typeof analyze>;
  validation: ValidateReport | null;
  refinedNotes?: string;
  onFocus: (ids?: string[]) => void;
}) {
  return (
    <div className="h-full overflow-y-auto bg-surface px-2 py-1.5 text-[12.5px]">
      {analysis.issues.length === 0 && !validation && (
        <div className="flex items-center gap-2 p-2 text-success">
          <CheckCircle2 className="h-4 w-4" /> 구조 분석 통과 — 실행하거나 &lsquo;검증&rsquo;으로 문법·실행 검사를 해보세요.
        </div>
      )}
      {analysis.issues.map((i, k) => (
        <button key={k} onClick={() => onFocus(i.nodes)} className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
          {i.level === "error" ? (
            <OctagonAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
          ) : i.level === "warning" ? (
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" />
          )}
          <span>
            <span className="text-fg">{i.message}</span>
            {i.hint && <span className="block text-[11.5px] text-muted">{i.hint}</span>}
          </span>
        </button>
      ))}
      {validation && (
        <div className="mt-2 border-t border-border px-2 pt-2">
          <div className={cn("mb-1 flex items-center gap-1.5 font-medium", validation.ok ? "text-success" : "text-danger")}>
            {validation.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <OctagonAlert className="h-3.5 w-3.5" />}
            코드 검증 {validation.ok ? "통과" : "실패"}
            {validation.run && <span className="text-[11px] font-normal text-muted">· Mock 실행 {validation.run.duration_ms}ms · exit {validation.run.exit_code}</span>}
          </div>
          {validation.lint.map((l, k) => (
            <div key={k} className="font-mono text-[11.5px] text-danger">
              {l.file}:{l.line}:{l.col} {l.code} {l.message}
            </div>
          ))}
          {validation.run && !validation.ok && <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-code p-2 font-mono text-[11px] whitespace-pre-wrap text-danger">{validation.run.stderr.slice(-2000)}</pre>}
        </div>
      )}
      {refinedNotes && (
        <div className="mt-2 border-t border-border px-2 pt-2">
          <div className="mb-1 flex items-center gap-1.5 font-medium text-accent">
            <Sparkles className="h-3.5 w-3.5" /> LLM 고도화 노트
          </div>
          <p className="text-[12px] whitespace-pre-wrap text-fg-2">{refinedNotes}</p>
        </div>
      )}
    </div>
  );
}

export function Playground() {
  return (
    <ReactFlowProvider>
      {/* 주소의 ?p= 를 읽으므로 Suspense 로 감싼다 */}
      <Suspense fallback={<div className="grid flex-1 place-items-center text-sm text-muted">플레이그라운드 로딩 중…</div>}>
        <Workspace />
      </Suspense>
    </ReactFlowProvider>
  );
}
