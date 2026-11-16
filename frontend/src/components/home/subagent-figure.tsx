import { Boxes } from "lucide-react";

/**
 * 첫 화면 그림: 바깥 그래프의 Sub-agent 노드를 열면 안쪽 그래프가 나오고,
 * 만든 에이전트는 프리셋으로 저장해 다른 그래프에서 다시 쓴다. 플레이그라운드 화면을 그대로 축소했다.
 */

type N = { id: string; x: number; y: number; w: number; h: number; label: string; api?: string; color: string; pill?: boolean; stack?: boolean; open?: boolean };

const OUTER: N[] = [
  { id: "start", x: 116, y: 14, w: 88, h: 28, label: "START", color: "#10b981", pill: true },
  { id: "sup", x: 70, y: 70, w: 180, h: 50, label: "supervisor", api: "Command(goto=…)", color: "#a855f7" },
  { id: "rt", x: 12, y: 160, w: 140, h: 50, label: "research_team", api: "노드 3", color: "#7c3aed", stack: true, open: true },
  { id: "wt", x: 172, y: 160, w: 140, h: 50, label: "writing_team", api: "노드 2", color: "#7c3aed", stack: true },
  { id: "end", x: 276, y: 81, w: 70, h: 28, label: "END", color: "#64748b", pill: true },
];

const INNER: N[] = [
  { id: "start", x: 96, y: 14, w: 88, h: 28, label: "START", color: "#10b981", pill: true },
  { id: "r", x: 50, y: 70, w: 180, h: 50, label: "researcher", api: "openai:gpt-5", color: "#8b5cf6" },
  { id: "t", x: 50, y: 170, w: 180, h: 50, label: "research_tools", api: "web_search · lookup_stock", color: "#f59e0b" },
  { id: "end", x: 262, y: 81, w: 70, h: 28, label: "END", color: "#64748b", pill: true },
];

function Node({ n }: { n: N }) {
  return (
    <g>
      {n.stack && (
        <>
          <rect x={n.x + 6} y={n.y + 6} width={n.w} height={n.h} rx="10" fill="var(--bg)" stroke="var(--border)" />
          <rect x={n.x + 3} y={n.y + 3} width={n.w} height={n.h} rx="10" fill="var(--surface)" stroke="var(--border)" />
        </>
      )}
      <rect
        x={n.x}
        y={n.y}
        width={n.w}
        height={n.h}
        rx={n.pill ? n.h / 2 : 10}
        fill={n.open ? "var(--accent-soft)" : "var(--surface)"}
        stroke={n.pill ? n.color : n.stack ? n.color : "var(--border-strong)"}
        strokeWidth={n.stack ? 1.8 : 1.4}
      />
      {!n.pill && <rect x={n.x + 9} y={n.y + 11} width="28" height="28" rx="7" fill={n.color} />}
      <text
        x={n.pill ? n.x + n.w / 2 : n.x + 45}
        y={n.pill ? n.y + 18.5 : n.y + 23}
        textAnchor={n.pill ? "middle" : "start"}
        fontSize={n.pill ? 10.5 : 11.5}
        fontWeight="600"
        fill="var(--fg)"
        fontFamily={n.pill ? undefined : "var(--font-mono)"}
      >
        {n.label}
      </text>
      {n.api && (
        <text x={n.x + 45} y={n.y + 38} fontSize="8.5" fill="var(--muted)" fontFamily="var(--font-mono)">
          {n.api}
        </text>
      )}
    </g>
  );
}

const PRESETS = [
  { name: "웹 리서처", meta: "노드 3 · web_search", src: "계정" },
  { name: "보고서 작성팀", meta: "노드 2 · 자기 검토", src: "계정" },
  { name: "환불 승인 플로", meta: "노드 3 · 사람 승인", src: "팀원 공유" },
];

export function SubagentFigure() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
      <div className="grid md:grid-cols-2">
        {/* 바깥 그래프 */}
        <div className="bg-grid relative border-b border-border md:border-r md:border-b-0">
          <div className="flex items-center gap-1.5 border-b border-border bg-surface/90 px-4 py-2 text-[11px] text-muted">
            <span className="font-semibold text-fg">agent</span>
            <span className="ml-auto">더블클릭해 열기</span>
          </div>
          <svg viewBox="0 0 360 230" className="w-full" role="img" aria-label="supervisor 가 research_team, writing_team 서브 에이전트에 일을 맡기는 그래프. research_team 이 열려 있다.">
            <g fill="none" stroke="var(--border-strong)" strokeWidth="1.5">
              <path d="M160 42 V70" />
              <path d="M120 120 L82 160" strokeDasharray="4 3" />
              <path d="M200 120 L242 160" strokeDasharray="4 3" />
              <path d="M250 95 H276" strokeDasharray="4 3" />
            </g>
            {OUTER.map((n) => (
              <Node key={n.id} n={n} />
            ))}
          </svg>
        </div>
        {/* 안쪽 그래프 */}
        <div className="bg-grid relative">
          <div className="flex items-center gap-1 border-b border-accent/40 bg-surface/90 px-4 py-2 font-mono text-[11px] text-muted">
            agent <span>›</span> <span className="font-semibold text-accent">research_team</span>
            <span className="ml-auto rounded bg-accent-soft px-1.5 py-px font-sans text-[10px] text-accent">격리 모드</span>
          </div>
          <svg viewBox="0 0 360 230" className="w-full" role="img" aria-label="research_team 내부: researcher 와 research_tools 가 도구 호출 루프를 이룬다">
            <g fill="none" stroke="var(--border-strong)" strokeWidth="1.5">
              <path d="M140 42 V70" />
              <path className="hero-wire" d="M110 120 V170" stroke="var(--accent)" />
              <path d="M170 170 V120" />
              <path d="M230 95 H262" strokeDasharray="4 3" />
            </g>
            <g fontSize="9" fill="var(--muted)" fontFamily="var(--font-mono)">
              <text x="104" y="150" textAnchor="end">tool_calls</text>
            </g>
            {INNER.map((n) => (
              <Node key={n.id} n={n} />
            ))}
          </svg>
        </div>
      </div>
      {/* 프리셋 */}
      <div className="border-t border-border px-4 py-3">
        <div className="mb-2 flex items-center text-[11px] font-semibold tracking-wide text-muted uppercase">
          내 에이전트 프리셋
          <span className="ml-auto font-normal tracking-normal normal-case">끌어다 놓으면 Sub-agent 로 들어갑니다</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {PRESETS.map((p) => (
            <div key={p.name} className="flex items-center gap-2.5 rounded-xl border border-border bg-bg px-3 py-2">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-white" style={{ background: "#7c3aed" }}>
                <Boxes className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-medium">{p.name}</span>
                <span className="block truncate text-[11px] text-muted">
                  {p.meta} · {p.src}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
