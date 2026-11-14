// 실행 진입점(main.py), README, Mermaid 다이어그램.
import type { GNode } from "../types.ts";
import { py } from "./context.ts";
import type { Ctx } from "./context.ts";

export function mainFile(c: Ctx): string {
  const s = c.g.settings;
  const hasHuman = c.g.nodes.some((n) => n.kind === "human");
  const cfg = s.checkpointer !== "none" ? `{"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": ${s.recursionLimit}}` : `{"recursion_limit": ${s.recursionLimit}}`;
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


def run(graph, payload, config) -> bool:
    """스트리밍 실행. interrupt 가 발생하면 True 를 반환한다."""
    for chunk in graph.stream(payload, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                for it in update:
                    print(f"\\n⏸  interrupt: {it.value}")
                return True
            print(f"\\n▶ {node}")
            show(update)
    return False


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
            interrupted = run(graph, Command(resume={"approved": True}), config)`
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
  const id = (n: GNode) => (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name);
  const lines = ["flowchart TD"];
  for (const n of c.g.nodes) {
    const shape = n.kind === "router" || n.kind === "map" ? `{${n.data.name}}` : n.kind === "start" || n.kind === "end" ? `([${n.kind.toUpperCase()}])` : `[${n.data.name}]`;
    lines.push(`  ${id(n)}${shape}`);
  }
  for (const e of c.g.edges) {
    const s = c.byId.get(e.source);
    const t = c.byId.get(e.target);
    if (!s || !t) continue;
    const cond = ["router", "evaluator", "supervisor", "map"].includes(s.kind) || e.sourceHandle === "reject";
    lines.push(`  ${id(s)} ${cond ? "-.->" : "-->"}${e.sourceHandle && e.sourceHandle !== "out" ? `|${e.sourceHandle}|` : ""} ${id(t)}`);
  }
  return lines.join("\n");
}

export function readme(c: Ctx): string {
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
${c.g.nodes.some((n) => ["router", "map", "evaluator"].includes(n.kind)) ? "| `agent/routing.py` | 조건부 엣지 라우팅 함수 / Send fan-out |\n" : ""}${c.usedTools.length ? "| `agent/tools.py` | 도구 정의 |\n" : ""}| \`agent/graph.py\` | StateGraph 조립 및 컴파일 |
| \`main.py\` | 스트리밍 실행 데모 |
| \`langgraph.json\` | LangGraph Server(Agent Server) 배포 설정 |

## 배포

\`\`\`bash
pip install -U "langgraph-cli[inmem]"
langgraph dev   # 로컬 Agent Server + Studio
\`\`\`
`;
}
