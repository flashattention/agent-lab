"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/** 서버 렌더링에서는 false, 브라우저에서 hydration 이 끝나면 true. (localStorage 처럼 브라우저에만 있는 값을 그릴 때 사용) */
export function useMounted() {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
