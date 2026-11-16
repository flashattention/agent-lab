import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { Navbar } from "@/components/nav/navbar";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://agentlab-ai.vercel.app";
const DESCRIPTION = "에이전트를 그리면 실행되는 LangGraph 코드가 됩니다. 실행 전 구조 분석, 샌드박스 실행, 실시간 트레이스, 43개 강의와 한국어 API 레퍼런스.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "AgentLab — AI 에이전트를 그려서 설계하는 작업 공간", template: "%s · AgentLab" },
  description: DESCRIPTION,
  openGraph: { type: "website", siteName: "AgentLab", locale: "ko_KR", url: "/", description: DESCRIPTION },
  twitter: { card: "summary_large_image" },
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
