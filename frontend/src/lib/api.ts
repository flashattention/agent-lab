"use client";

import { useAuth } from "./auth";
import { useSettings } from "./settings";
import type { TraceEvent } from "./trace";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type RunEvent =
  | { type: "start"; mock: boolean; entry: string }
  | { type: "stdout" | "stderr"; data: string }
  | { type: "trace"; event: TraceEvent }
  | { type: "exit"; code: number; timed_out: boolean; duration_ms: number; mock: boolean }
  | { type: "error"; message: string };

function headers(): HeadersInit {
  const { apiKey } = useSettings.getState();
  const { token } = useAuth.getState();
  return {
    "content-type": "application/json",
    ...(apiKey ? { "x-openai-key": apiKey } : {}),
    ...(token ? { authorization: `Bearer ${token}` } : {}),
  };
}

async function errorText(res: Response) {
  try {
    const j = await res.json();
    return j.detail || JSON.stringify(j);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

/** 백엔드에서 코드를 실행하고 NDJSON 이벤트를 콜백으로 전달한다. */
export async function runCode(
  files: Record<string, string>,
  entry: string,
  onEvent: (e: RunEvent) => void,
  opts: { timeout?: number; signal?: AbortSignal } = {},
) {
  const { model } = useSettings.getState();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/run`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ files, entry, timeout: opts.timeout ?? 45, model }),
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    onEvent({ type: "error", message: `실행 서버(${API_URL})에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.` });
    return;
  }
  if (!res.ok || !res.body) {
    onEvent({ type: "error", message: await errorText(res) });
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
}

export type LintIssue = { file: string; line: number; col: number; code: string; message: string };
export type ValidateReport = {
  ok: boolean;
  lint: LintIssue[];
  run: null | { exit_code: number; timed_out: boolean; stdout: string; stderr: string; duration_ms: number };
};

export async function validateCode(files: Record<string, string>, entry = "main.py"): Promise<ValidateReport> {
  const res = await fetch(`${API_URL}/api/validate`, { method: "POST", headers: headers(), body: JSON.stringify({ files, entry }) });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

export type RefineResult = {
  cached: boolean;
  key: string;
  files?: Record<string, string>;
  notes?: string;
  model?: string;
  error?: string;
  attempts?: { ok: boolean; report?: ValidateReport; error?: string }[];
};

export async function refineCode(graph: unknown, files: Record<string, string>): Promise<RefineResult> {
  const { refineModel } = useSettings.getState();
  const res = await fetch(`${API_URL}/api/refine`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ graph, files, model: refineModel }),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

export async function lookupRefined(graph: unknown): Promise<{ key: string; hit: null | { files: Record<string, string>; notes: string; model: string } }> {
  const res = await fetch(`${API_URL}/api/refine/cached`, { method: "POST", headers: headers(), body: JSON.stringify({ graph }) });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

export async function listModels(): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/models`, { headers: headers() });
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()).models;
}

export async function health(): Promise<{ ok: boolean; versions: Record<string, string>; python: string; auth_required?: boolean } | null> {
  try {
    const res = await fetch(`${API_URL}/api/health`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}
