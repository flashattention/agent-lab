"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

const SESSION_KEY = "agentlab-key";
const readSessionKey = () => {
  try {
    return typeof window === "undefined" ? "" : sessionStorage.getItem(SESSION_KEY) || "";
  } catch {
    return "";
  }
};

export type Settings = {
  apiKey: string;
  rememberKey: boolean; // false 면 키를 이 탭(sessionStorage)에만 두고, 탭을 닫으면 지운다
  model: string; // init_chat_model 형식: "openai:gpt-5-mini"
  refineModel: string; // 플레이그라운드 코드 고도화용 고성능 모델
  editorFontSize: number;
  open: boolean;
  set: (patch: Partial<Omit<Settings, "set" | "setOpen">>) => void;
  setOpen: (open: boolean) => void;
};

export const useSettings = create<Settings>()(
  persist(
    (set) => ({
      apiKey: readSessionKey(),
      rememberKey: false,
      model: "openai:gpt-5-mini",
      refineModel: "gpt-5",
      editorFontSize: 13,
      open: false,
      set: (patch) => {
        if (patch.apiKey !== undefined)
          try {
            if (patch.apiKey) sessionStorage.setItem(SESSION_KEY, patch.apiKey);
            else sessionStorage.removeItem(SESSION_KEY);
          } catch {}
        set(patch);
      },
      setOpen: (open) => set({ open }),
    }),
    {
      name: "agentlab-settings",
      // 키는 "계속 기억"을 켠 경우에만 localStorage 에 남긴다 (XSS 시 노출 범위 축소)
      partialize: ({ apiKey, rememberKey, model, refineModel, editorFontSize }) => ({ ...(rememberKey ? { apiKey } : {}), rememberKey, model, refineModel, editorFontSize }),
      version: 1,
      // 이전 버전에서 저장해 둔 키가 있으면 사용자가 잃지 않도록 "계속 기억"을 켠 상태로 옮긴다
      migrate: (old, v) => {
        const o = (old ?? {}) as Partial<Settings>;
        return (v < 1 ? { ...o, rememberKey: !!o.apiKey } : o) as Settings;
      },
    },
  ),
);

/** 학습 진도 (완료한 강의, 퀴즈 점수) */
type Progress = {
  done: Record<string, number>; // lessonId → 완료 시각
  quiz: Record<string, number>; // lessonId → 맞힌 개수
  answers: Record<string, (number | null)[]>; // lessonId → 문항별로 고른 보기 (안 풀었으면 null)
  toggle: (id: string) => void;
  setQuiz: (id: string, score: number) => void;
  setAnswers: (id: string, picked: (number | null)[] | null) => void;
};

export const useProgress = create<Progress>()(
  persist(
    (set) => ({
      done: {},
      quiz: {},
      answers: {},
      toggle: (id) =>
        set((s) => {
          const done = { ...s.done };
          if (done[id]) delete done[id];
          else done[id] = Date.now();
          return { done };
        }),
      setQuiz: (id, score) => set((s) => ({ quiz: { ...s.quiz, [id]: score } })),
      setAnswers: (id, picked) =>
        set((s) => {
          const answers = { ...s.answers };
          if (picked) answers[id] = picked;
          else delete answers[id];
          return { answers };
        }),
    }),
    { name: "agentlab-progress" },
  ),
);
