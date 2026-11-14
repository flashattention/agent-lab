/** 첫 화면 그림: 왼쪽에 그린 그래프, 오른쪽에 그 그래프에서 생성된 코드. 플레이그라운드가 하는 일을 그대로 축소했다. */

const NODES = [
  { id: "start", x: 96, y: 18, w: 88, h: 30, label: "START", color: "#10b981", pill: true },
  { id: "agent", x: 50, y: 86, w: 180, h: 52, label: "agent", api: "ChatModel + bind_tools", color: "#8b5cf6" },
  { id: "tools", x: 50, y: 196, w: 180, h: 52, label: "tools", api: "ToolNode", color: "#f59e0b" },
  { id: "end", x: 290, y: 97, w: 76, h: 30, label: "END", color: "#64748b", pill: true },
];

const CODE: [string, string][] = [
  ["k", "builder = StateGraph(State)"],
  ["", 'builder.add_node("agent", call_model)'],
  ["", 'builder.add_node("tools", ToolNode(tools))'],
  ["", 'builder.add_edge(START, "agent")'],
  ["hl", 'builder.add_conditional_edges("agent", tools_condition)'],
  ["", 'builder.add_edge("tools", "agent")'],
  ["k", "graph = builder.compile(checkpointer=memory)"],
];

export function HeroCanvas() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2.5 text-xs text-muted">
        <span className="font-medium text-fg">여행 플래너 에이전트</span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-success" /> 저장됨
        </span>
        <span className="ml-auto rounded-full bg-success/10 px-2 py-0.5 font-medium text-success">구조 정상</span>
      </div>
      <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div className="bg-grid border-b border-border md:border-r md:border-b-0">
          <svg viewBox="0 0 390 270" className="h-full w-full" role="img" aria-label="START, agent, tools, END 노드가 연결된 ReAct 에이전트 그래프">
            <g fill="none" stroke="var(--border-strong)" strokeWidth="1.6">
              <path d="M140 48 V86" />
              <path className="hero-wire" d="M110 138 V196" stroke="var(--accent)" />
              <path d="M170 196 V138" />
              <path className="hero-wire" d="M230 112 H290" stroke="var(--accent)" />
            </g>
            <g fontSize="9.5" fill="var(--muted)" fontFamily="var(--font-mono)">
              <text x="62" y="171">tool_calls</text>
              <text x="240" y="104">없음</text>
            </g>
            {NODES.map((n) => (
              <g key={n.id}>
                <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={n.pill ? n.h / 2 : 10} fill="var(--surface)" stroke={n.pill ? n.color : "var(--border-strong)"} strokeWidth="1.4" />
                {!n.pill && <rect x={n.x + 10} y={n.y + 12} width="28" height="28" rx="7" fill={n.color} />}
                <text x={n.pill ? n.x + n.w / 2 : n.x + 48} y={n.pill ? n.y + 19.5 : n.y + 24} textAnchor={n.pill ? "middle" : "start"} fontSize={n.pill ? 11 : 12.5} fontWeight="600" fill="var(--fg)">
                  {n.label}
                </text>
                {n.api && (
                  <text x={n.x + 48} y={n.y + 39} fontSize="9" fill="var(--muted)" fontFamily="var(--font-mono)">
                    {n.api}
                  </text>
                )}
              </g>
            ))}
          </svg>
        </div>
        <div className="min-w-0 bg-code">
          <div className="border-b border-border px-4 py-2 font-mono text-[11px] text-muted">graph.py</div>
          <pre className="overflow-x-auto px-4 py-3 font-mono text-[11px] leading-[1.9] text-fg-2 [word-break:normal]">
            {CODE.map(([kind, line], i) => (
              <div key={i} className={kind === "hl" ? "-mx-4 border-l-2 border-accent bg-accent-soft px-4 text-fg" : undefined}>
                <span className="mr-3 inline-block w-3 text-right text-muted select-none">{i + 1}</span>
                {line}
              </div>
            ))}
          </pre>
          <div className="border-t border-border px-4 py-2.5 font-mono text-[11px] leading-relaxed text-muted">
            <span className="text-fg">$ python main.py</span>
            <br />
            agent → tools → agent → <span className="text-success">완료 (2.1s)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
