import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { Navbar } from "@/components/nav/navbar";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "AgentLab — AI Agent 엔지니어링 학습 플랫폼", template: "%s · AgentLab" },
  description:
    "LangChain v1 · LangGraph v1로 AI Agent를 기초부터 현업 수준까지. 브라우저에서 바로 실행하는 강의, 비주얼 그래프 플레이그라운드, 한국어 API 레퍼런스.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body className="flex min-h-full flex-col">
        <Providers>
          <Navbar />
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </Providers>
      </body>
    </html>
  );
}
