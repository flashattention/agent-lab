import type { Metadata } from "next";
import { Suspense } from "react";
import { MarketView } from "@/components/market/market-view";

export const metadata: Metadata = { title: "에이전트 마켓", description: "다른 사람이 만든 에이전트를 골라 내 그래프에 Sub-agent 로 붙입니다." };

export default function AgentsPage() {
  return (
    // 주소의 ?id= (링크 공유) 를 읽으므로 Suspense 로 감싼다
    <Suspense fallback={<div className="grid flex-1 place-items-center text-sm text-muted">불러오는 중…</div>}>
      <MarketView />
    </Suspense>
  );
}
