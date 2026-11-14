"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ReactFlowProvider, useReactFlow } from "@xyflow/react";
import { Sparkles } from "lucide-react";
import { analyze } from "@/lib/playground/analyze";
import { generateProject, normalizeGraph } from "@/lib/playground/codegen";
import { PATTERNS } from "@/lib/playground/patterns";
import type { NodeKind } from "@/lib/playground/types";
import { lookupRefined, refineCode, validateCode, type ValidateReport } from "@/lib/api";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { Canvas } from "./canvas";
import { MobileNotice } from "./mobile-notice";
import { toViewEdges, toViewNodes } from "./view-model";
import { CodeEditor, type EditorMarker } from "@/components/ide/code-editor";
import { ConsolePanel } from "@/components/ide/console-panel";
import { TracePanel } from "@/components/ide/trace-panel";
import { buildTrace, nodeStates } from "@/lib/trace";
import { parseTraceback, useRunner } from "@/components/ide/use-runner";
import { SplitGroup, SplitHandle, SplitPanel } from "@/components/ui/split";
import { Explorer } from "./explorer";
import { PatternsDialog } from "./patterns-dialog";
import { RightPanel, type RightTab } from "./right-panel";
import { BottomPanel, type BottomTab } from "./bottom-panel";
import { EditorTabs } from "./editor-tabs";
import { NoticeToast, type Notice } from "./notice";
import { ProblemsPanel } from "./problems-panel";
import { SharedRunDialog } from "./shared-run-dialog";
import { PlaygroundToolbar } from "./toolbar";
import { customCodeNodes } from "@/lib/playground/custom-code";
import { CANVAS_TAB, toGraph, usePlayground } from "./store";
import { useProjectSync } from "./use-project-sync";
import { useAuth } from "@/lib/auth";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { useMounted } from "@/lib/use-mounted";

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
  const rf = useReactFlow();
  const apiKey = useSettings((x) => x.apiKey);
  const setSettingsOpen = useSettings((x) => x.setOpen);
  const runner = useRunner();
  const sync = useProjectSync();
  const user = useAuth((x) => x.user);
  const needLogin = SUPABASE_ENABLED && !user; // 코드 실행·검증·고도화는 로그인한 사용자만
  const [showPatterns, setShowPatterns] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("problems");
  const [rightTab, setRightTab] = useState<RightTab>("palette");
  const [validation, setValidation] = useState<ValidateReport | null>(null);
  const [busy, setBusy] = useState<null | "validate" | "refine">(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [markers, setMarkers] = useState<Record<string, EditorMarker[]>>({});
  const [reveal, setReveal] = useState<{ line: number; nonce: number } | null>(null);
  const mounted = useMounted();
  const canvasRef = useRef<HTMLDivElement>(null);

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
  const structural = useMemo(() => JSON.parse(signature), [signature]);
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
  const viewNodes = useMemo(() => toViewNodes(s.nodes, analysis, runStates), [s.nodes, analysis, runStates]);
  const viewEdges = useMemo(() => toViewEdges(s.nodes, s.edges, analysis), [s.edges, s.nodes, analysis]);

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

  // 저장된 캔버스를 복원할 때는 패널 크기가 정해진 뒤에 한 번 더 화면에 맞춘다
  useEffect(() => {
    if (!mounted) return;
    const t = setTimeout(() => usePlayground.getState().nodes.length && rf.fitView({ padding: 0.2 }), 150);
    return () => clearTimeout(t);
  }, [mounted, rf]);

  // 프로젝트를 새로 열면 화면에 맞춘다
  useEffect(() => {
    if (s.projectId) setTimeout(() => rf.fitView({ padding: 0.2 }), 60);
  }, [s.projectId, rf]);

  /* ------------------------------------------------------------ 액션 */
  const askLogin = () => setNotice({ kind: "login", text: "코드 실행, 검증, 고도화는 로그인 후 사용할 수 있습니다." });

  // 공유받은 프로젝트에 작성자가 고친 코드가 있으면, 내 키로 실행하기 전에 확인한다
  const [confirmShared, setConfirmShared] = useState(false);
  const customFns = useMemo(() => customCodeNodes(graph), [signature]); // eslint-disable-line react-hooks/exhaustive-deps
  const sharedEdited = sync.state === "viewing" && (modified.size > 0 || customFns.length > 0);

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
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col">
      <MobileNotice />
      <SplitGroup orientation="horizontal" className="min-h-0 flex-1">
        {/* 왼쪽: 툴바 + 파일 탐색기 + 하단 패널(문제/터미널/트레이스) */}
        <SplitPanel defaultSize="25" minSize="16">
          <div className="flex h-full min-h-0 flex-col bg-surface">
            <PlaygroundToolbar
              sync={sync}
              counts={{ errors: errors.length, warnings: warnings.length, nodes: graph.nodes.length }}
              canRun={analysis.ok}
              busy={busy}
              running={running}
              onPatterns={() => setShowPatterns(true)}
              onAutoLayout={() => {
                s.autoLayout();
                setTimeout(() => rf.fitView({ padding: 0.2, duration: 300 }), 30);
              }}
              onDownload={download}
              onValidate={validate}
              onRefine={() => (apiKey || refinedValid ? refine() : setSettingsOpen(true))}
              onRun={() => run()}
              onStop={runner.stop}
            />

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
                <BottomPanel
                  tab={bottomTab}
                  onTab={setBottomTab}
                  issueCount={errors.length + warnings.length}
                  hasErrors={errors.length > 0}
                  running={running}
                  problems={<ProblemsPanel analysis={analysis} validation={validation} refinedNotes={refinedValid?.notes} onFocus={focusNodes} />}
                  terminal={
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
                  }
                />
              </SplitPanel>
            </SplitGroup>
          </div>
        </SplitPanel>
        <SplitHandle />

        {/* 가운데: 탭 (캔버스 + 파일) — 화면 높이 전체 */}
        <SplitPanel defaultSize="53" minSize="30">
          <div className="flex h-full min-h-0 flex-col">
            <EditorTabs modified={modified} activeFile={activeFile} />
            <div className="relative min-h-0 flex-1">
              <Canvas
                ref={canvasRef}
                nodes={viewNodes}
                edges={viewEdges}
                hidden={s.activeTab !== CANVAS_TAB}
                errorCount={errors.length}
                onShowProblems={() => setBottomTab("problems")}
                onDropKind={(kind, pos) => addAt(kind, pos)}
              />
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
              {notice && <NoticeToast notice={notice} onClose={() => setNotice(null)} />}
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
        <SharedRunDialog
          files={[...modified]}
          functionNodes={customFns}
          onOpenFile={(f) => {
            s.openTab(f);
            setConfirmShared(false);
          }}
          onCancel={() => setConfirmShared(false)}
          onRunWithKey={() => run({ confirmed: true })}
          onRunMock={() => run({ confirmed: true, noKey: true })}
        />
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
