"use client";

import { useCallback, useRef, useState } from "react";
import { runCode, type RunEvent } from "@/lib/api";
import type { TraceEvent } from "@/lib/trace";

export type ConsoleLine = { kind: "stdout" | "stderr" | "info" | "error" | "success"; text: string };
export type RunStatus = "idle" | "running" | "ok" | "error";

export type TraceLocation = { file: string; line: number; message: string };

/** Python traceback 에서 사용자 파일의 마지막 오류 위치를 찾는다. */
export function parseTraceback(stderr: string, files: string[]): TraceLocation | null {
  const re = /File "([^"]+)", line (\d+)/g;
  let last: TraceLocation | null = null;
  let m: RegExpExecArray | null;
  while ((m = re.exec(stderr))) {
    const f = m[1].replace(/^.*?agentlab-[^/]+\//, "").replace(/^\.\//, "");
    const hit = files.find((x) => x === f || f.endsWith("/" + x));
    if (hit) last = { file: hit, line: Number(m[2]), message: "" };
  }
  if (last) {
    const lines = stderr.trim().split("\n");
    last.message = lines[lines.length - 1] ?? "";
  }
  return last;
}

export function useRunner() {
  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [meta, setMeta] = useState<{ mock?: boolean; duration?: number; code?: number } | null>(null);
  const [stderrAll, setStderrAll] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  // 트레이스 이벤트는 많이 올 수 있으므로 모아 두었다가 프레임마다 한 번만 반영한다
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const traceBuf = useRef<TraceEvent[]>([]);
  const traceFrame = useRef<number | null>(null);
  const flushTrace = useCallback(() => {
    traceFrame.current = null;
    setTrace(traceBuf.current.slice());
  }, []);
  const pushTrace = useCallback(
    (e: TraceEvent) => {
      traceBuf.current.push(e);
      if (traceFrame.current == null) traceFrame.current = requestAnimationFrame(flushTrace);
    },
    [flushTrace],
  );

  const push = (kind: ConsoleLine["kind"], text: string) =>
    setLines((prev) => {
      const last = prev[prev.length - 1];
      // 같은 스트림의 연속 청크는 합쳐서 렌더링 비용을 줄인다
      if (last && last.kind === kind && (kind === "stdout" || kind === "stderr")) {
        return [...prev.slice(0, -1), { kind, text: last.text + text }];
      }
      return [...prev, { kind, text }];
    });

  const run = useCallback(async (files: Record<string, string>, entry: string, opts: { timeout?: number; noKey?: boolean } = {}) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLines([{ kind: "info", text: `$ python ${entry}\n` }]);
    setStatus("running");
    setMeta(null);
    setStderrAll("");
    traceBuf.current = [];
    setTrace([]);
    let stderr = "";
    let final = "error" as RunStatus;
    try {
      await runCode(
        files,
        entry,
        (e: RunEvent) => {
          if (e.type === "trace") pushTrace(e.event);
          else if (e.type === "stdout") push("stdout", e.data);
          else if (e.type === "stderr") {
            stderr += e.data;
            if (e.data.startsWith("[AgentLab] OPENAI_API_KEY 없음")) push("info", "ⓘ Mock LLM 모드 — 설정에서 API Key를 넣으면 실제 GPT로 실행됩니다.\n");
            else push("stderr", e.data);
          } else if (e.type === "start") setMeta({ mock: e.mock });
          else if (e.type === "exit") {
            final = e.code === 0 ? "ok" : "error";
            setMeta({ mock: e.mock, duration: e.duration_ms, code: e.code });
            push(e.code === 0 ? "success" : "error", `\n${e.code === 0 ? "✓" : "✗"} 종료 코드 ${e.code} · ${(e.duration_ms / 1000).toFixed(2)}s\n`);
          } else if (e.type === "error") push("error", e.message + "\n");
        },
        { signal: ctrl.signal, timeout: opts.timeout, noKey: opts.noKey },
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        push("info", "\n■ 실행을 중단했습니다.\n");
        final = "idle";
      } else push("error", String(e));
    }
    if (traceFrame.current != null) cancelAnimationFrame(traceFrame.current);
    flushTrace();
    setStderrAll(stderr);
    setStatus(final);
    return { ok: final === "ok", stderr };
  }, [flushTrace, pushTrace]);

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const clear = useCallback(() => {
    setLines([]);
    setStatus("idle");
    setMeta(null);
    traceBuf.current = [];
    setTrace([]);
  }, []);

  return { lines, status, meta, run, stop, clear, stderrAll, trace };
}
