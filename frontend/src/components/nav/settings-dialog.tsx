"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Eye, EyeOff, Loader2, ShieldCheck, Trash2, X } from "lucide-react";
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
        {s.apiKey && (
          <button onClick={() => { s.set({ apiKey: "" }); setStatus("idle"); setMsg(""); }} className="mt-1.5 flex items-center gap-1 text-[11px] text-muted hover:text-danger">
            <Trash2 className="h-3 w-3" /> 키 지우기
          </button>
        )}

        <label className="mt-2 flex items-center gap-2 text-xs text-fg-2">
          <input type="checkbox" checked={s.rememberKey} onChange={(e) => s.set({ rememberKey: e.target.checked })} className="accent-[var(--accent)]" />
          이 브라우저에 계속 기억 (공용 PC 에서는 끄세요)
        </label>

        <div className="mt-3 rounded-xl border border-border bg-surface-2/60 p-3 text-xs leading-relaxed text-muted">
          <div className="mb-1.5 flex items-center gap-1.5 font-semibold text-fg-2">
            <ShieldCheck className="h-3.5 w-3.5 text-success" /> 키는 이렇게 다뤄집니다
          </div>
          <ul className="list-disc space-y-1 pl-4">
            <li>
              {s.rememberKey ? "이 브라우저(localStorage)에 저장되고" : "이 탭에만 보관되어 탭을 닫으면 지워지고"}, ▶ 실행할 때만 서버로 전달됩니다. 서버는 키를 저장하거나 기록하지 않습니다.
            </li>
            <li>
              실행되는 코드에는 <b className="text-fg-2">진짜 키가 전달되지 않습니다.</b> 서버의 키 프록시가 OpenAI 추론 API 요청에만 키를 붙여 주므로,
              공유받은 코드라도 키 문자열을 빼낼 수 없습니다.{" "}
              <a href="https://github.com/flashattention/agent-lab/blob/main/backend/app/keyproxy.py" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-accent hover:underline">
                코드 보기 <ExternalLink className="h-3 w-3" />
              </a>
            </li>
            <li>실행 샌드박스는 키 프록시 외의 주소로 연결할 수 없고, 외부 프로그램도 실행할 수 없습니다.</li>
            <li>키가 없으면 모든 예제가 <b className="text-fg-2">Mock LLM 모드</b>로 실행됩니다(흐름 검증용 모의 응답).</li>
          </ul>
          <div className="mt-2.5 rounded-lg bg-warning/10 px-2.5 py-2 text-warning">
            <b>권장:</b> 이 서비스 전용 키를 새로 만들어 쓰세요. OpenAI에서 새 프로젝트를 만들고 <b>월 사용 한도</b>를 건 뒤, 그 프로젝트의 키를 발급하면
            만약의 경우에도 피해가 한도 안으로 제한되고, 언제든 키만 삭제하면 됩니다.
            <span className="mt-1 flex flex-wrap gap-x-3">
              <a href="https://platform.openai.com/settings/organization/projects" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-medium underline">
                프로젝트·한도 설정 <ExternalLink className="h-3 w-3" />
              </a>
              <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-medium underline">
                API 키 발급 <ExternalLink className="h-3 w-3" />
              </a>
            </span>
          </div>
        </div>

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
