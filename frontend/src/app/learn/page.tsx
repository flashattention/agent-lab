import type { Metadata } from "next";
import { getCurriculum } from "@/lib/content";
import { CurriculumBoard } from "@/components/learn/curriculum-board";

export const metadata: Metadata = { title: "학습" };

export default async function LearnPage() {
  const curriculum = await getCurriculum();
  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-12 md:px-8">
      <div className="mb-10 max-w-2xl">
        <p className="mb-2 text-sm font-medium text-accent">Zero → Production</p>
        <h1 className="mb-3 text-4xl font-bold tracking-tight">AI Agent 엔지니어 커리큘럼</h1>
        <p className="leading-relaxed text-muted">
          에이전트가 무엇인지부터 LangChain v1·LangGraph v1, RAG, 멀티 에이전트, 프로덕션 배포까지 다룹니다.
          모든 강의에는 바로 실행해 볼 수 있는 IDE와 자동 채점 과제가 있습니다.
        </p>
      </div>
      <CurriculumBoard curriculum={curriculum} />
    </main>
  );
}
