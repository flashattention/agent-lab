"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Settings = {
  apiKey: string;
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
      apiKey: "",
      model: "openai:gpt-5-mini",
      refineModel: "gpt-5",
      editorFontSize: 13,
      open: false,
      set: (patch) => set(patch),
      setOpen: (open) => set({ open }),
    }),
    {
      name: "agentlab-settings",
      partialize: ({ apiKey, model, refineModel, editorFontSize }) => ({ apiKey, model, refineModel, editorFontSize }),
    },
  ),
);

/** 학습 진도 (완료한 강의, 퀴즈 점수) */
type Progress = {
  done: Record<string, number>; // lessonId → 완료 시각
  quiz: Record<string, number>; // lessonId → 맞힌 개수
  toggle: (id: string) => void;
  setQuiz: (id: string, score: number) => void;
};

export const useProgress = create<Progress>()(
  persist(
    (set) => ({
      done: {},
      quiz: {},
      toggle: (id) =>
        set((s) => {
          const done = { ...s.done };
          if (done[id]) delete done[id];
          else done[id] = Date.now();
          return { done };
        }),
      setQuiz: (id, score) => set((s) => ({ quiz: { ...s.quiz, [id]: score } })),
    }),
    { name: "agentlab-progress" },
  ),
);
