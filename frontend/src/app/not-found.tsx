import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid flex-1 place-items-center px-6 py-24 text-center">
      <div>
        <p className="font-mono text-sm text-accent">404</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">페이지를 찾을 수 없습니다</h1>
        <p className="mt-3 text-muted">주소가 바뀌었거나 아직 준비 중인 콘텐츠입니다.</p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/learn" className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-accent-fg">
            학습으로
          </Link>
          <Link href="/docs" className="rounded-xl border border-border px-4 py-2 text-sm font-semibold">
            Docs 검색
          </Link>
        </div>
      </div>
    </main>
  );
}
