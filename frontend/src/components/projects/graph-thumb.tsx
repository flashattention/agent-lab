import { KINDS } from "@/lib/playground/catalog";
import type { SubGraph } from "@/lib/playground/types";

/** 그래프를 작은 도식으로 그린다. 프로젝트 카드의 미리보기용. */
export function GraphThumb({ graph, className }: { graph: SubGraph; className?: string }) {
  const nodes = graph?.nodes ?? [];
  if (!nodes.length) return <div className={className} />;
  const size = (kind: string) => (kind === "start" || kind === "end" ? { w: 120, h: 44 } : { w: 220, h: 80 });
  const box = nodes.map((n) => ({ id: n.id, kind: n.kind, x: n.position.x, y: n.position.y, ...size(n.kind) }));
  const minX = Math.min(...box.map((b) => b.x));
  const minY = Math.min(...box.map((b) => b.y));
  const maxX = Math.max(...box.map((b) => b.x + b.w));
  const maxY = Math.max(...box.map((b) => b.y + b.h));
  const pad = 40;
  const byId = new Map(box.map((b) => [b.id, b]));
  return (
    <svg viewBox={`${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`} className={className} preserveAspectRatio="xMidYMid meet" aria-hidden>
      {graph.edges.map((e) => {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) return null;
        return <line key={e.id} x1={a.x + a.w / 2} y1={a.y + a.h / 2} x2={b.x + b.w / 2} y2={b.y + b.h / 2} stroke="var(--border-strong)" strokeWidth={5} />;
      })}
      {box.map((b) => (
        <rect key={b.id} x={b.x} y={b.y} width={b.w} height={b.h} rx={b.h / (b.w === 120 ? 2 : 5)} fill={KINDS[b.kind]?.color ?? "#888"} />
      ))}
    </svg>
  );
}
