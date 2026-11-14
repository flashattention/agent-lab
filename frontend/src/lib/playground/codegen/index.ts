// 비주얼 그래프 → LangGraph 1.x / LangChain 1.x 파이썬 프로젝트 (결정적 템플릿 생성기)
import type { Graph } from "../types.ts";
import { context } from "./context.ts";
export { GENERATOR_VERSION } from "./context.ts";
import { stateFile, configFile, toolsFile, retrieverFile } from "./support.ts";
import { nodeFile } from "./nodes.ts";
import { routingFile } from "./routing.ts";
import { graphFile, nodesInit } from "./graph.ts";
import { mainFile, readme } from "./project.ts";

export function generateProject(g: Graph): Record<string, string> {
  const c = context(g);
  const files: Record<string, string> = {};
  files["main.py"] = mainFile(c);
  files["agent/__init__.py"] = '"""AgentLab 플레이그라운드에서 생성된 LangGraph 에이전트."""\n';
  files["agent/config.py"] = configFile();
  files["agent/state.py"] = stateFile(c);
  if (c.usedTools.length) files["agent/tools.py"] = toolsFile(c);
  if (c.hasRetriever) files["agent/retriever.py"] = retrieverFile();
  files["agent/nodes/__init__.py"] = nodesInit(c);
  for (const n of c.real) files[`agent/nodes/${n.data.name}.py`] = nodeFile(c, n);
  const routing = routingFile(c);
  if (routing) files["agent/routing.py"] = routing;
  files["agent/graph.py"] = graphFile(c);
  files["requirements.txt"] = `langgraph>=1.2\nlangchain>=1.4\nlangchain-openai>=1.7\n${g.settings.checkpointer === "sqlite" ? "langgraph-checkpoint-sqlite>=3.1\n" : ""}python-dotenv\n`;
  files["langgraph.json"] = JSON.stringify({ $schema: "https://langgra.ph/schema.json", dependencies: ["."], graphs: { agent: "./agent/graph.py:graph" }, env: ".env" }, null, 2) + "\n";
  files[".env.example"] = "OPENAI_API_KEY=sk-...\nLAB_MODEL=openai:gpt-5-mini\n# LangSmith 트레이싱 (선택)\nLANGSMITH_TRACING=true\nLANGSMITH_API_KEY=\n";
  files["README.md"] = readme(c);
  return files;
}

/** 서버 캐시 키 계산용: 좌표/임의 id 를 제거하고 노드 이름 기준으로 정규화 */
export function normalizeGraph(g: Graph) {
  const name = (id: string) => {
    const n = g.nodes.find((x) => x.id === id);
    return n ? (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name) : id;
  };
  return {
    nodes: g.nodes.map((n) => ({ id: name(n.id), type: n.kind, data: { ...n.data } })),
    edges: g.edges.map((e) => ({ source: name(e.source), target: name(e.target), sourceHandle: e.sourceHandle ?? null, label: null })),
    settings: g.settings,
  };
}
