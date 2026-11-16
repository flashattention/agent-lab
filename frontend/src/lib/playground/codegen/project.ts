// 프로젝트 수준 파일: main.py, README, 구조 테스트.
import { allNodes, walkGraphs } from "../subgraph.ts";
import type { GNode, SubGraph } from "../types.ts";
import type { Ctx } from "./context.ts";
import { VIRTUAL, py } from "./context.ts";

export function mainFile(c: Ctx): string {
  const s = c.g.settings;
  const everything = allNodes(c.g);
  // Human 노드와 Agent 의 승인 미들웨어는 둘 다 interrupt 로 멈춘다 (재개 값 형식은 다르다)
  const hasHuman = everything.some((n) => n.kind === "human" || (n.kind === "agent" && !!n.data.middleware?.hitl));
  const hasSub = everything.some((n) => n.kind === "subgraph");
  const trace = `"run_name": "agentlab-demo", "tags": ["agentlab", "demo"], "metadata": {"source": "agentlab-playground"}`;
  const cfg = s.checkpointer !== "none" ? `{"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": ${s.recursionLimit}, ${trace}}` : `{"recursion_limit": ${s.recursionLimit}, ${trace}}`;
  return `"""실행 진입점: 데모 입력으로 그래프를 스트리밍 실행한다.

    python main.py
"""

${s.checkpointer !== "none" ? "import uuid\n\n" : ""}from langgraph.errors import GraphRecursionError
${hasHuman ? "from langgraph.types import Command\n" : ""}
from agent.graph import build_graph

DEMO_INPUT = ${py(s.demoInput)}


def show(update: object) -> None:
    """노드가 반환한 상태 업데이트를 읽기 좋게 출력한다."""
    if not isinstance(update, dict):
        return
    for msg in update.get("messages", []) or []:
        role = getattr(msg, "type", "?")
        name = f"({msg.name})" if getattr(msg, "name", None) else ""
        if getattr(msg, "tool_calls", None):
            calls = ", ".join(f"{t['name']}({t['args']})" for t in msg.tool_calls)
            print(f"   [{role}{name}] 🛠  {calls}")
        else:
            print(f"   [{role}{name}] {str(msg.content)[:400]}")
    for key, value in update.items():
        if key != "messages":
            print(f"   · {key} = {str(value)[:200]}")


${
  hasSub
    ? `def run(graph, payload, config) -> list:
    """스트리밍 실행. interrupt 가 발생하면 그 값들을, 끝까지 돌면 빈 리스트를 반환한다.

    subgraphs=True 로 서브 에이전트 내부 노드의 업데이트도 함께 받는다.
    ns(namespace)는 ("researcher:<task id>", ...) 처럼 바깥 → 안쪽 순서의 경로다.
    """
    for ns, chunk in graph.stream(payload, config, stream_mode="updates", subgraphs=True):
        where = "".join(f"{part.split(':')[0]} › " for part in ns)
        for node, update in chunk.items():
            if node == "__interrupt__":
                for it in update:
                    print(f"\\n⏸  interrupt ({where.rstrip(' ›') or 'root'}): {it.value}")
                return [it.value for it in update]
            print(f"\\n{'  ' * len(ns)}▶ {where}{node}")
            show(update)
    return []`
    : `def run(graph, payload, config) -> list:
    """스트리밍 실행. interrupt 가 발생하면 그 값들을, 끝까지 돌면 빈 리스트를 반환한다."""
    for chunk in graph.stream(payload, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                for it in update:
                    print(f"\\n⏸  interrupt: {it.value}")
                return [it.value for it in update]
            print(f"\\n▶ {node}")
            show(update)
    return []`
}
${
  hasHuman
    ? `

def approve(value: object) -> object:
    """데모용 재개 값: 사람이 모두 승인했다고 가정한다.

    Agent 의 승인 미들웨어(HumanInTheLoopMiddleware)는 {"decisions": [...]} 로,
    Human 노드는 {"approved": ...} 로 재개한다. 결정 종류: approve / edit / reject / respond.
    """
    if isinstance(value, dict) and "action_requests" in value:
        return {"decisions": [{"type": "approve"} for _ in value["action_requests"]]}
    return {"approved": True}`
    : ""
}


def main() -> None:
    graph = build_graph()
    config = ${cfg}
    print("노드:", ", ".join(n for n in graph.get_graph().nodes if not n.startswith("__")))
    print(f"입력: {DEMO_INPUT}")
    try:
        interrupted = run(graph, {"messages": [{"role": "user", "content": DEMO_INPUT}]}, config)
${
  hasHuman
    ? `        # 데모: 사람이 승인했다고 가정하고 재개한다. (실서비스에서는 UI/API 로 결정을 받는다)
        resumes = 0
        while interrupted and resumes < 5:
            resumes += 1
            print("👤 승인 → Command(resume=...) 로 재개")
            interrupted = run(graph, Command(resume=approve(interrupted[0])), config)`
    : `        if interrupted:
            print("(interrupt 발생 — Command(resume=...) 로 재개하세요)")`
}
    except GraphRecursionError:
        print("\\n⛔ recursion_limit 초과: 루프의 종료 조건을 확인하세요.")
        raise
    print("\\n✅ 실행 완료")


if __name__ == "__main__":
    main()
`;
}

export function mermaid(c: Ctx): string {
  const lines = ["flowchart TD"];
  const level = (g: SubGraph, prefix: string, pad: string) => {
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const id = (n: GNode) => prefix + (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name);
    for (const n of g.nodes) {
      if (n.kind === "subgraph" && n.data.graph) {
        lines.push(`${pad}subgraph ${id(n)} [${n.data.name}]`);
        level(n.data.graph, `${id(n)}__`, pad + "  ");
        lines.push(`${pad}end`);
        continue;
      }
      const shape = n.kind === "router" || n.kind === "map" ? `{${n.data.name}}` : n.kind === "start" || n.kind === "end" ? `([${n.kind.toUpperCase()}])` : `[${n.data.name}]`;
      lines.push(`${pad}${id(n)}${shape}`);
    }
    for (const e of g.edges) {
      const s = byId.get(e.source);
      const t = byId.get(e.target);
      if (!s || !t) continue;
      const cond = ["router", "evaluator", "supervisor", "map"].includes(s.kind) || e.sourceHandle === "reject";
      lines.push(`${pad}${id(s)} ${cond ? "-.->" : "-->"}${e.sourceHandle && e.sourceHandle !== "out" ? `|${e.sourceHandle}|` : ""} ${id(t)}`);
    }
  };
  level(c.g, "", "  ");
  return lines.join("\n");
}

/** 모든 서브그래프 (경로 포함) */
export function subagents(g: SubGraph) {
  const out: { node: GNode; pkg: string; names: string[] }[] = [];
  walkGraphs(g, (_lv, path, owner) => {
    if (!owner) return;
    const names: string[] = [];
    let cur: SubGraph = g;
    for (const id of path) {
      const n = cur.nodes.find((x) => x.id === id)!;
      names.push(n.data.name);
      cur = n.data.graph!;
    }
    out.push({ node: owner, names, pkg: ["agent", ...names.flatMap((nm) => ["subagents", nm])].join(".") });
  });
  return out;
}

export function readme(c: Ctx): string {
  const subs = subagents(c.g);
  const subTable = subs.length
    ? `
## 서브 에이전트

| 경로 | 노드 | 입출력 | 메모리 | 역할 |
| --- | --- | --- | --- | --- |
${subs.map((x) => `| \`${x.pkg.replace(/\./g, "/")}/\` | ${x.names.join(" › ")} | ${x.node.data.io === "shared" ? "상태 공유" : "격리 (최종 답변만)"} | ${x.node.data.memory === "persistent" ? "독립 영속" : "부모 상속"} | ${x.node.data.description ?? ""} |`).join("\n")}

각 서브 에이전트는 독립된 패키지라서 단독으로 실행·테스트할 수 있고, \`langgraph dev\` 에서도 별도 그래프로 열립니다.
`
    : "";
  return `# LangGraph Agent (AgentLab Playground 생성)

\`\`\`mermaid
${mermaid(c)}
\`\`\`

## 실행

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env  # OPENAI_API_KEY 입력
python main.py
\`\`\`

## 구조

| 파일 | 역할 |
| --- | --- |
| \`agent/state.py\` | 공유 상태 스키마와 리듀서 |
| \`agent/nodes/*.py\` | 노드별 구현 (${c.real.map((n) => n.data.name).join(", ")}) |
${c.g.nodes.some((n) => ["router", "map", "evaluator"].includes(n.kind)) ? "| `agent/routing.py` | 조건부 엣지 라우팅 함수 / Send fan-out |\n" : ""}${subs.length ? "| `agent/subagents/<이름>/` | 서브 에이전트 패키지 (각자 state/nodes/routing/graph) |\n" : ""}${c.usedTools.length ? "| `agent/tools.py` | 도구 정의 |\n" : ""}| \`agent/graph.py\` | StateGraph 조립 및 컴파일 |
| \`main.py\` | 스트리밍 실행 데모 |
| \`langgraph.json\` | LangGraph Server(Agent Server) 배포 설정 |
${subTable}
## 배포

\`\`\`bash
pip install -U "langgraph-cli[inmem]"
langgraph dev   # 로컬 Agent Server + Studio
\`\`\`
`;
}

/** LLM 을 호출하지 않는 구조 테스트: 각 그래프가 캔버스와 같은 노드로 컴파일되는지 */
export function testFile(c: Ctx): string {
  const nodesOf = (g: SubGraph) => g.nodes.filter((n) => !VIRTUAL.has(n.kind)).map((n) => n.data.name).sort();
  const subs = subagents(c.g).map((x) => {
    let cur: SubGraph = c.g;
    for (const nm of x.names) cur = cur.nodes.find((n) => n.data.name === nm && n.kind === "subgraph")!.data.graph!;
    return { module: `${x.pkg}.graph`, test: x.names.join("__"), nodes: nodesOf(cur) };
  });
  const set = (xs: string[]) => (xs.length ? `{${xs.map(py).join(", ")}}` : "set()");
  return `"""구조 테스트: LLM 을 호출하지 않고 그래프가 캔버스와 같은 모양으로 컴파일되는지 확인한다.

    pip install -r requirements-dev.txt
    pytest -q

CI 에 넣어 두면 노드 이름 변경·연결 누락 같은 회귀를 실제 호출 비용 없이 잡을 수 있다.
"""

import pytest


@pytest.fixture(autouse=True)
def _fake_key(monkeypatch):
    # 모델 객체를 만들 때 키가 있어야 하지만, 이 테스트는 모델을 호출하지 않는다
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")


def _nodes(graph) -> set[str]:
    return {n for n in graph.get_graph().nodes if not n.startswith("__")}


def test_root_graph():
    from agent.graph import graph

    assert _nodes(graph) == ${set(nodesOf(c.g))}
${subs
  .map(
    (x) => `

def test_subagent_${x.test}():
    from ${x.module} import graph

    assert _nodes(graph) == ${set(x.nodes)}
`,
  )
  .join("")}`;
}
