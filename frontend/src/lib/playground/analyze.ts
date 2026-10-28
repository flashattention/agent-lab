// 그래프 구조 정적 분석: 실행 전에 오류(빨강)와 병목/위험(노랑)을 찾아낸다.
import type { Analysis, GEdge, GNode, Graph, Issue } from "./types.ts";
import { KINDS, TOOL_LIBRARY } from "./catalog.ts";

const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
const RESERVED = new Set(["START", "END", "__start__", "__end__", "state", "graph", "tools_condition", "Command", "Send"]);
const PY_KEYWORDS = new Set(
  "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(
    " ",
  ),
);
const ROUTING = new Set(["router", "evaluator", "supervisor"]);

export function analyze(graph: Graph): Analysis {
  const { nodes, edges, settings } = graph;
  const issues: Issue[] = [];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const out = new Map<string, GEdge[]>();
  const inc = new Map<string, GEdge[]>();
  for (const n of nodes) {
    out.set(n.id, []);
    inc.set(n.id, []);
  }
  for (const e of edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) continue;
    out.get(e.source)!.push(e);
    inc.get(e.target)!.push(e);
  }
  const err = (message: string, hint?: string, ns: string[] = [], es: string[] = []) =>
    issues.push({ level: "error", message, hint, nodes: ns, edges: es });
  const warn = (message: string, hint?: string, ns: string[] = [], es: string[] = []) =>
    issues.push({ level: "warning", message, hint, nodes: ns, edges: es });
  const info = (message: string, hint?: string, ns: string[] = []) => issues.push({ level: "info", message, hint, nodes: ns });
  const nm = (id: string) => {
    const n = byId.get(id);
    return n?.kind === "start" ? "START" : n?.kind === "end" ? "END" : (n?.data.name ?? id);
  };

  const starts = nodes.filter((n) => n.kind === "start");
  const ends = nodes.filter((n) => n.kind === "end");

  if (nodes.length === 0) {
    return { issues: [{ level: "info", message: "오른쪽 컴포넌트를 끌어다 놓거나 패턴 예시를 불러와 시작하세요." }], errorNodes: new Set(), warnNodes: new Set(), errorEdges: new Set(), warnEdges: new Set(), ok: false };
  }
  if (starts.length === 0) err("START 노드가 없습니다.", "컴포넌트 > 흐름에서 START를 추가하세요.");
  if (starts.length > 1) err("START 노드는 하나만 있어야 합니다.", undefined, starts.map((n) => n.id));
  if (ends.length === 0) err("END 노드가 없습니다.", "그래프가 끝날 지점을 END로 연결하세요.");
  if (ends.length > 1) warn("END 노드가 여러 개입니다. 코드에서는 하나의 END로 합쳐집니다.", undefined, ends.map((n) => n.id));

  /* ---------------------------------------------------------- 이름 규칙 */
  const seen = new Map<string, string>();
  for (const n of nodes) {
    if (n.kind === "start" || n.kind === "end") continue;
    const name = n.data.name;
    if (!IDENT.test(name) || PY_KEYWORDS.has(name)) err(`'${name}' 은(는) 올바른 Python 식별자가 아닙니다.`, "영문자/숫자/_ 만 사용하고 숫자로 시작하지 마세요.", [n.id]);
    else if (RESERVED.has(name)) err(`'${name}' 은(는) 예약된 이름입니다.`, undefined, [n.id]);
    if (seen.has(name)) err(`노드 이름 '${name}' 이(가) 중복됩니다.`, "LangGraph 노드 이름은 그래프 안에서 유일해야 합니다.", [n.id, seen.get(name)!]);
    else seen.set(name, n.id);
  }

  /* ---------------------------------------------------------- 엣지 기본 규칙 */
  const pairSeen = new Set<string>();
  for (const e of edges) {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) continue;
    if (t.kind === "start") err("START 로 들어가는 엣지는 허용되지 않습니다.", undefined, [t.id], [e.id]);
    if (s.kind === "end") err("END 에서 나가는 엣지는 허용되지 않습니다.", undefined, [s.id], [e.id]);
    if (e.source === e.target && !ROUTING.has(s.kind))
      err(`'${s.data.name}' 이(가) 자기 자신으로 무조건 돌아갑니다 → 무한 루프`, "Conditional Edge/Evaluator 로 종료 조건을 만드세요.", [s.id], [e.id]);
    const key = `${e.source}->${e.target}:${e.sourceHandle ?? ""}`;
    if (pairSeen.has(key)) warn(`'${nm(e.source)}' → '${nm(e.target)}' 엣지가 중복되었습니다.`, undefined, [], [e.id]);
    pairSeen.add(key);
  }

  /* ---------------------------------------------------------- 막힌 노드 / 도달성 */
  for (const n of nodes) {
    if (n.kind !== "end" && out.get(n.id)!.length === 0 && n.kind !== "supervisor")
      err(`'${nm(n.id)}' 에서 나가는 엣지가 없습니다 (dead end).`, "다음 노드나 END 로 연결하세요.", [n.id]);
    if (n.kind !== "start" && inc.get(n.id)!.length === 0) err(`'${nm(n.id)}' 로 들어오는 엣지가 없습니다.`, "START 에서 도달할 수 있게 연결하세요.", [n.id]);
  }

  const reach = (from: string[], dir: Map<string, GEdge[]>, pick: (e: GEdge) => string) => {
    const seenR = new Set(from);
    const stack = [...from];
    while (stack.length) {
      const id = stack.pop()!;
      for (const e of dir.get(id) ?? []) {
        const nx = pick(e);
        if (!seenR.has(nx)) {
          seenR.add(nx);
          stack.push(nx);
        }
      }
    }
    return seenR;
  };
  // supervisor 의 FINISH 는 암묵적으로 END 로 간다
  const fromStart = reach(starts.map((n) => n.id), out, (e) => e.target);
  const canEnd = reach(
    [...ends.map((n) => n.id), ...nodes.filter((n) => n.kind === "supervisor").map((n) => n.id)],
    inc,
    (e) => e.source,
  );
  if (starts.length) {
    const unreachable = nodes.filter((n) => !fromStart.has(n.id) && n.kind !== "start");
    if (unreachable.length)
      err(`START 에서 도달할 수 없는 노드: ${unreachable.map((n) => nm(n.id)).join(", ")}`, "연결이 끊긴 구간입니다.", unreachable.map((n) => n.id));
  }
  if (ends.length) {
    const trapped = nodes.filter((n) => fromStart.has(n.id) && !canEnd.has(n.id) && n.kind !== "end" && n.kind !== "start");
    if (trapped.length)
      err(
        `END 에 도달할 수 없는 구간: ${trapped.map((n) => n.data.name).join(", ")}`,
        "이 노드들에 들어가면 그래프가 끝나지 않습니다 (출구 없는 루프/막힌 경로).",
        trapped.map((n) => n.id),
        edges.filter((e) => trapped.some((t) => t.id === e.target)).map((e) => e.id),
      );
  }

  /* ---------------------------------------------------------- 사이클 (Tarjan SCC) */
  let idx = 0;
  const index = new Map<string, number>();
  const low = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  const sccs: string[][] = [];
  const strong = (v: string) => {
    index.set(v, idx);
    low.set(v, idx++);
    stack.push(v);
    onStack.add(v);
    for (const e of out.get(v) ?? []) {
      const w = e.target;
      if (!index.has(w)) {
        strong(w);
        low.set(v, Math.min(low.get(v)!, low.get(w)!));
      } else if (onStack.has(w)) low.set(v, Math.min(low.get(v)!, index.get(w)!));
    }
    if (low.get(v) === index.get(v)) {
      const comp: string[] = [];
      let w: string;
      do {
        w = stack.pop()!;
        onStack.delete(w);
        comp.push(w);
      } while (w !== v);
      sccs.push(comp);
    }
  };
  for (const n of nodes) if (!index.has(n.id)) strong(n.id);
  for (const comp of sccs) {
    const set = new Set(comp);
    const cyclic = comp.length > 1 || (out.get(comp[0]) ?? []).some((e) => e.target === comp[0]);
    if (!cyclic) continue;
    const exits = comp.filter((id) => {
      const n = byId.get(id)!;
      return (ROUTING.has(n.kind) || n.kind === "human") && ((out.get(id) ?? []).some((e) => !set.has(e.target)) || n.kind === "supervisor");
    });
    const cycleEdges = edges.filter((e) => set.has(e.source) && set.has(e.target)).map((e) => e.id);
    if (exits.length === 0)
      err(
        `무한 루프: ${comp.map(nm).join(" → ")} 사이클에 종료 조건이 없습니다.`,
        "Conditional Edge(라우터)나 Evaluator 로 루프를 빠져나갈 경로를 만드세요.",
        comp,
        cycleEdges,
      );
    else {
      const guarded = comp.some((id) => ["evaluator", "supervisor"].includes(byId.get(id)!.kind));
      if (!guarded)
        info(`루프 ${comp.map(nm).join(" ↔ ")} 는 LLM 판단으로 종료됩니다. recursion_limit=${settings.recursionLimit} 가 안전장치입니다.`, undefined, comp);
    }
  }

  /* ---------------------------------------------------------- 종류별 규칙 */
  let llmToolCount = 0;
  for (const n of nodes) {
    const o = out.get(n.id)!;
    const i = inc.get(n.id)!;
    const name = n.data.name;
    switch (n.kind) {
      case "router": {
        if (o.length < 2) err(`라우터 '${name}' 에는 최소 2개의 나가는 경로가 필요합니다.`, "조건부 엣지는 둘 이상의 분기를 가질 때 의미가 있습니다.", [n.id]);
        for (const e of i) {
          const p = byId.get(e.source)!;
          if (p.kind === "router" || p.kind === "map")
            err(`'${p.data.name}' → '${name}': 라우팅 함수끼리 직접 연결할 수 없습니다.`, "사이에 실제 노드를 두세요.", [n.id, p.id], [e.id]);
          else if ((out.get(p.id) ?? []).length > 1)
            warn(`'${p.data.name}' 에서 라우터와 다른 노드로 동시에 나갑니다 → 병렬 실행됩니다.`, "의도한 것이 아니라면 라우터 하나로 모든 분기를 처리하세요.", [p.id], (out.get(p.id) ?? []).map((x) => x.id));
        }
        if (n.data.strategy === "tools_condition") {
          const toolTargets = o.filter((e) => byId.get(e.target)?.kind === "tools");
          if (toolTargets.length !== 1) err(`tools_condition 라우터 '${name}' 는 정확히 하나의 Tools 노드로 연결되어야 합니다.`, undefined, [n.id]);
          if (o.length - toolTargets.length !== 1) err(`tools_condition 라우터 '${name}' 는 도구 외 경로(보통 END)가 정확히 하나 필요합니다.`, undefined, [n.id]);
        }
        if (n.data.strategy === "state_key" && !n.data.stateKey) err(`라우터 '${name}' 의 state 키를 지정하세요.`, undefined, [n.id]);
        break;
      }
      case "evaluator": {
        const pass = o.filter((e) => e.sourceHandle === "pass");
        const retry = o.filter((e) => e.sourceHandle === "retry");
        if (pass.length !== 1) err(`Evaluator '${name}' 의 pass(통과) 경로를 하나 연결하세요.`, undefined, [n.id]);
        if (retry.length !== 1) err(`Evaluator '${name}' 의 retry(재시도) 경로를 하나 연결하세요.`, undefined, [n.id]);
        break;
      }
      case "supervisor": {
        const workers = o.filter((e) => byId.get(e.target)?.kind !== "end");
        if (workers.length === 0) err(`Supervisor '${name}' 에 연결된 워커가 없습니다.`, "Agent/LLM 노드를 워커로 연결하세요.", [n.id]);
        if (workers.length > 5) warn(`Supervisor '${name}' 의 워커가 ${workers.length}개입니다. 라우팅 정확도가 떨어질 수 있습니다.`, "계층형(Hierarchical) supervisor 로 나누는 것을 고려하세요.", [n.id]);
        for (const e of workers) {
          const w = byId.get(e.target)!;
          if (!(out.get(w.id) ?? []).some((x) => x.target === n.id))
            warn(`워커 '${w.data.name}' 가 Supervisor 로 돌아오지 않습니다.`, "워커 → Supervisor 엣지를 추가해야 다음 작업을 위임할 수 있습니다.", [w.id], [e.id]);
          if (w.kind === "router" || w.kind === "map") err(`Supervisor 의 워커로 '${w.data.name}'(${KINDS[w.kind].label}) 는 사용할 수 없습니다.`, undefined, [w.id]);
        }
        break;
      }
      case "tools": {
        if (!n.data.tools?.length) err(`Tools 노드 '${name}' 에 도구가 하나도 없습니다.`, "속성 패널에서 도구를 선택하세요.", [n.id]);
        const fromRouter = i.some((e) => byId.get(e.source)?.kind === "router" && byId.get(e.source)?.data.strategy === "tools_condition");
        if (!fromRouter)
          warn(`Tools 노드 '${name}' 앞에 tools_condition 라우터가 없습니다.`, "LLM 이 도구를 요청하지 않아도 항상 실행되어 오류가 날 수 있습니다.", [n.id], i.map((e) => e.id));
        const back = o.some((e) => ["llm", "agent"].includes(byId.get(e.target)?.kind ?? ""));
        if (!back) warn(`Tools 노드 '${name}' 의 결과가 LLM 으로 돌아가지 않습니다.`, "도구 결과를 해석할 LLM 노드로 다시 연결하는 것이 일반적입니다 (ReAct 루프).", [n.id]);
        llmToolCount = Math.max(llmToolCount, n.data.tools?.length ?? 0);
        break;
      }
      case "human": {
        if (settings.checkpointer === "none")
          err(`Human 노드 '${name}' 는 interrupt 를 쓰므로 Checkpointer 가 필요합니다.`, "그래프 설정에서 Checkpointer 를 memory 또는 sqlite 로 바꾸세요.", [n.id]);
        break;
      }
      case "map": {
        if (o.length !== 1) err(`Map '${name}' 은(는) 정확히 하나의 워커 노드로 연결되어야 합니다.`, undefined, [n.id]);
        const w = o[0] && byId.get(o[0].target);
        if (w && !["llm", "agent", "function"].includes(w.kind)) err(`Map 워커 '${w.data.name}' 는 LLM/Agent/Function 노드여야 합니다.`, undefined, [w.id]);
        if (w) {
          const downstream = reach([w.id], out, (e) => e.target);
          if (![...downstream].some((id) => byId.get(id)?.kind === "reduce"))
            warn(`Map '${name}' 의 결과를 모으는 Reduce 노드가 없습니다.`, "병렬 결과는 state.results 에 쌓입니다. Reduce 로 종합하세요.", [n.id]);
        }
        for (const e of i) if (["router", "map"].includes(byId.get(e.source)?.kind ?? "")) err("라우팅 함수 뒤에 Map 을 바로 붙일 수 없습니다.", undefined, [n.id], [e.id]);
        break;
      }
      case "agent":
      case "llm": {
        if ((n.data.tools?.length ?? 0) > 6)
          warn(`'${name}' 의 도구가 ${n.data.tools!.length}개입니다 → 도구 선택 정확도 저하/토큰 비용 증가.`, "LLMToolSelectorMiddleware 나 하위 에이전트로 분리하세요.", [n.id]);
        break;
      }
    }

    // fan-in 병목
    const plainIn = i.filter((e) => !["router", "evaluator", "supervisor", "map"].includes(byId.get(e.source)?.kind ?? ""));
    if (plainIn.length >= 3 && n.kind !== "end" && n.kind !== "supervisor")
      warn(
        `병목: '${name}' 이(가) ${plainIn.length}개의 병렬 브랜치를 모두 기다립니다.`,
        "가장 느린 브랜치가 전체 지연을 결정합니다. 타임아웃(add_node(timeout=...))이나 Send 기반 map-reduce 를 고려하세요.",
        [n.id],
        plainIn.map((e) => e.id),
      );
  }

  /* ---------------------------------------------------------- 민감 도구 & 직렬 LLM 체인 */
  const sensitiveUsers = nodes.filter((n) => (n.data.tools ?? []).some((t) => TOOL_LIBRARY[t]?.sensitive) && ["tools", "agent"].includes(n.kind));
  const hasHuman = nodes.some((n) => n.kind === "human");
  if (sensitiveUsers.length && !hasHuman)
    warn("민감한 도구(환불 등)가 승인 절차 없이 실행됩니다.", "Human-in-the-loop 노드나 HumanInTheLoopMiddleware 로 승인 단계를 두세요.", sensitiveUsers.map((n) => n.id));

  // 사이클을 제외한 최장 LLM 직렬 경로
  const memo = new Map<string, number>();
  const visiting = new Set<string>();
  const longest = (id: string): number => {
    if (memo.has(id)) return memo.get(id)!;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const n = byId.get(id)!;
    const self = ["llm", "agent", "evaluator", "supervisor", "reduce"].includes(n.kind) ? 1 : 0;
    const best = Math.max(0, ...(out.get(id) ?? []).map((e) => longest(e.target)));
    visiting.delete(id);
    memo.set(id, self + best);
    return self + best;
  };
  if (starts[0]) {
    const chain = longest(starts[0].id);
    if (chain >= 5) warn(`LLM 호출이 최소 ${chain}번 직렬로 일어납니다 → 응답 지연이 큽니다.`, "독립적인 단계는 병렬 분기로, 단순 단계는 작은 모델/규칙으로 바꾸세요.");
  }

  /* ---------------------------------------------------------- 결과 집계 */
  const errorNodes = new Set<string>();
  const warnNodes = new Set<string>();
  const errorEdges = new Set<string>();
  const warnEdges = new Set<string>();
  for (const is of issues) {
    for (const n of is.nodes ?? []) (is.level === "error" ? errorNodes : is.level === "warning" ? warnNodes : new Set()).add(n);
    for (const e of is.edges ?? []) (is.level === "error" ? errorEdges : is.level === "warning" ? warnEdges : new Set()).add(e);
  }
  // 오류 노드에 붙은 엣지도 강조
  for (const e of edges) if (errorNodes.has(e.target) && errorNodes.has(e.source)) errorEdges.add(e.id);
  issues.sort((a, b) => ["error", "warning", "info"].indexOf(a.level) - ["error", "warning", "info"].indexOf(b.level));
  return { issues, errorNodes, warnNodes, errorEdges, warnEdges, ok: !issues.some((x) => x.level === "error") };
}

export function isTerminalKind(n: GNode) {
  return n.kind === "end";
}
