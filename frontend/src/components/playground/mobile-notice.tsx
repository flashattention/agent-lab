"use client";

import Link from "next/link";
import { useState } from "react";
import { Monitor } from "lucide-react";

/** 플레이그라운드는 3단 레이아웃이라 좁은 화면에서는 안내를 먼저 보여 준다. */
export function MobileNotice() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div className="fixed inset-x-0 top-14 bottom-0 z-40 grid place-items-center bg-bg/95 p-6 backdrop-blur md:hidden">
      <div className="max-w-sm text-center">
        <Monitor className="mx-auto h-10 w-10 text-muted" />
        <h2 className="mt-4 text-lg font-semibold">데스크톱에서 열어 주세요</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">플레이그라운드는 캔버스, 코드, 실행 트레이스를 한 화면에 나란히 보여 주는 도구라 넓은 화면에 맞춰져 있습니다. 강의는 휴대폰에서도 읽을 수 있습니다.</p>
        <div className="mt-6 flex justify-center gap-2">
          <Link href="/learn" className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-accent-fg">
            강의 보기
          </Link>
          <button onClick={() => setDismissed(true)} className="rounded-xl border border-border px-4 py-2 text-sm font-semibold">
            그래도 열기
          </button>
        </div>
      </div>
    </div>
  );
}
