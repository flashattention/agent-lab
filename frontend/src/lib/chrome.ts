"use client";

import { create } from "zustand";

/** 전체 화면 작업 공간(플레이그라운드)에서 사이트 상단 nav 바를 잠깐 펼칠지 여부. */
export const useNavOverlay = create<{ open: boolean; setOpen: (v: boolean) => void }>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
}));

/** 상단 nav 바를 숨기고 화면 전체를 쓰는 경로. */
export const isImmersive = (pathname: string) => pathname.startsWith("/playground");
