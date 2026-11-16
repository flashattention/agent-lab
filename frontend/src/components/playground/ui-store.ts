"use client";

import { create } from "zustand";
import type { SubGraph } from "@/lib/playground/types";

export type Notice = { kind: "ok" | "error" | "info" | "login"; text: string };

/** 프리셋 저장 대화상자에 넘기는 내용 */
export type SaveDraft = {
  graph: SubGraph;
  name: string;
  node_name: string;
  description: string;
  linkNodeId?: string; // 저장 후 이 Sub-agent 노드(현재 레벨)를 새 프리셋과 연결한다
  overwriteId?: string; // 덮어쓰기 후보 (노드가 이미 연결된 프리셋)
};

type UIState = {
  notice: Notice | null;
  setNotice: (n: Notice | null) => void;
  saveDraft: SaveDraft | null;
  openSave: (d: SaveDraft | null) => void;
  libraryOpen: boolean;
  setLibraryOpen: (v: boolean) => void;
};

/** 플레이그라운드 여러 패널이 함께 쓰는 화면 상태 (저장되지 않음) */
export const usePlaygroundUI = create<UIState>()((set) => ({
  notice: null,
  setNotice: (notice) => set({ notice }),
  saveDraft: null,
  openSave: (saveDraft) => set({ saveDraft }),
  libraryOpen: false,
  setLibraryOpen: (libraryOpen) => set({ libraryOpen }),
}));
