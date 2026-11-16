"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2, ShieldCheck, X } from "lucide-react";
import { useSettings } from "@/lib/settings";
import { listModels } from "@/lib/api";

const DEFAULT_MODELS = ["gpt-5-mini", "gpt-5", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1"];

export function SettingsDialog() {
  const s = useSettings();
  const [show, setShow] = useState(false);
  const [models, setModels] = useState<string[]>(DEFAULT_MODELS);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!s.open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && s.setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s, s.open]);

  if (!s.open) return null;

  const verify = async () => {
    setStatus("loading");
    try {
      const list = await listModels();
      if (list.length) setModels(list);
      setStatus("ok");
      setMsg(`키 확인 완료 · 사용 가능한 모델 ${list.length}개`);
    } catch (e) {
      setStatus("error");
      setMsg((e as Error).message);
    }
  };

  const modelId = s.model.replace(/^openai:/, "");

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={() => s.setOpen(false)}>
      <div
        className="fade-in w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-soft"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold">설정</h2>
          <button onClick={() => s.setOpen(false)} className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-fg">
            <X className="h-4 w-4" />
          </button>
        </div>

        <label className="mb-1.5 block text-sm font-medium">OpenAI API Key</label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type={show ? "text" : "password"}
              value={s.apiKey}
              onChange={(e) => s.set({ apiKey: e.target.value.trim() })}
              placeholder="sk-..."
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 pr-9 font-mono text-sm outline-none focus:border-accent"
            />
            <button onClick={() => setShow(!show)} className="absolute top-1/2 right-2 -translate-y-1/2 text-muted hover:text-fg">
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <button
            onClick={verify}
            disabled={!s.apiKey || status === "loading"}
            className="rounded-lg border border-border px-3 text-sm hover:bg-surface-2 disabled:opacity-40"
          >
            {status === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : "확인"}
          </button>
        </div>
        {msg && <p className={`mt-1.5 text-xs ${status === "error" ? "text-danger" : "text-success"}`}>{msg}</p>}
        <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-muted">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {s.rememberKey ? "키는 이 브라우저(localStorage)에 저장됩니다." : "키는 이 탭에만 보관되고 탭을 닫으면 지워집니다."} 코드 실행 요청 시에만 서버로 전달되고, 서버는 키를 저장하지
          않습니다. 실행 샌드박스는 OpenAI 외의 주소로 연결할 수 없습니다. 키가 없으면 모든 예제가 <b className="text-fg-2">Mock LLM 모드</b>로 실행됩니다(흐름 검증용 모의 응답).
        </p>
        <label className="mt-2 flex items-center gap-2 text-xs text-fg-2">
          <input type="checkbox" checked={s.rememberKey} onChange={(e) => s.set({ rememberKey: e.target.checked })} className="accent-[var(--accent)]" />
          이 브라우저에 계속 기억 (공용 PC 에서는 끄세요)
        </label>

        <div className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">실습 기본 모델</label>
            <input
              list="model-list"
              value={modelId}
              onChange={(e) => s.set({ model: `openai:${e.target.value.trim()}` })}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-accent"
            />
            <p className="mt-1 text-[11px] text-muted">
              코드의 <code>LAB_MODEL</code> 환경변수로 주입
            </p>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">코드 고도화 모델</label>
            <input
              list="model-list"
              value={s.refineModel}
              onChange={(e) => s.set({ refineModel: e.target.value.trim() })}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-accent"
            />
            <p className="mt-1 text-[11px] text-muted">플레이그라운드 ✨ 고도화에 사용</p>
          </div>
          <datalist id="model-list">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>

        <div className="mt-5">
          <label className="mb-1.5 block text-sm font-medium">에디터 글꼴 크기 · {s.editorFontSize}px</label>
          <input
            type="range"
            min={11}
            max={18}
            value={s.editorFontSize}
            onChange={(e) => s.set({ editorFontSize: Number(e.target.value) })}
            className="w-full accent-[var(--accent)]"
          />
        </div>
      </div>
    </div>
  );
}
