// 비주얼 그래프 → LangGraph 1.x / LangChain 1.x 파이썬 프로젝트 (결정적 템플릿 생성기)
import { PROVIDER_PACKAGES, providerOf } from "../catalog.ts";
import { allNodes } from "../subgraph.ts";
import type { Graph, SubGraph } from "../types.ts";
import type { Ctx } from "./context.ts";
import { context, withOs } from "./context.ts";
import { graphFile, nodesInit } from "./graph.ts";
import { nodeFile } from "./nodes.ts";
import { mainFile, readme, subagents, testFile } from "./project.ts";
import { routingFile } from "./routing.ts";
import { configFile, retrieverFile, stateFile, toolsFile } from "./support.ts";
export { GENERATOR_VERSION } from "./context.ts";

/** 한 그래프(최상위 또는 서브그래프)의 패키지 파일: state / nodes / routing / graph */
export function graphPackage(c: Ctx, files: Record<string, string>) {
  if (!c.isRoot) files[`${c.dir}/__init__.py`] = `"""서브 에이전트 '${c.graphName}'."""\n\nfrom ${c.pkg}.graph import build_graph, graph\n\n__all__ = ["build_graph", "graph"]\n`;
  files[`${c.dir}/state.py`] = stateFile(c);
  files[`${c.dir}/nodes/__init__.py`] = nodesInit(c);
  for (const n of c.real) files[`${c.dir}/nodes/${n.data.name}.py`] = withOs(nodeFile(c, n));
  const routing = routingFile(c);
  if (routing) files[`${c.dir}/routing.py`] = routing;
  files[`${c.dir}/graph.py`] = graphFile(c);
  const subs = c.real.filter((n) => n.kind === "subgraph" && n.data.graph);
  if (subs.length) files[`${c.dir}/subagents/__init__.py`] = `"""'${c.graphName}' 이(가) 사용하는 서브 에이전트 패키지."""\n`;
  for (const n of subs)
    graphPackage(context({ ...n.data.graph!, settings: c.g.settings }, `${c.pkg}.subagents.${n.data.name}`, n.data.name, n.data.memory ?? "inherit"), files);
}

export function generateProject(g: Graph): Record<string, string> {
  const c = context(g);
  const files: Record<string, string> = {};
  const everything = allNodes(g);
  files["main.py"] = mainFile(c);
  files["agent/__init__.py"] = '"""AgentLab 플레이그라운드에서 생성된 LangGraph 에이전트."""\n';
  files["agent/config.py"] = configFile();
  if (c.usedTools.length) files["agent/tools.py"] = toolsFile(c);
  if (everything.some((n) => n.kind === "retriever")) files["agent/retriever.py"] = retrieverFile();
  graphPackage(c, files);
  const graphs: Record<string, string> = { agent: "./agent/graph.py:graph" };
  // 부모 상속 메모리인 서브 에이전트는 Agent Server 에서도 단독 그래프로 노출한다
  for (const x of subagents(g)) if (x.node.data.memory !== "persistent") graphs[x.names.join("__")] = `./${x.pkg.replace(/\./g, "/")}/graph.py:graph`;
  // 노드별 모델이 다른 공급자를 쓰면 해당 통합 패키지를 추가한다
  const providers = new Set(["langchain-openai>=1.7", ...everything.filter((n) => n.data.model?.trim()).map((n) => PROVIDER_PACKAGES[providerOf(n.data.model)]).filter(Boolean)]);
  files["requirements.txt"] = `langgraph>=1.2\nlangchain>=1.4\n${[...providers].sort().join("\n")}\n${g.settings.checkpointer === "sqlite" ? "langgraph-checkpoint-sqlite>=3.1\n" : ""}python-dotenv\n`;
  files["requirements-dev.txt"] = "-r requirements.txt\npytest>=8\nruff>=0.8\n";
  files[".gitignore"] = ".env\n.venv/\n__pycache__/\n*.pyc\ncheckpoints.db*\n.langgraph_api/\n.pytest_cache/\n.ruff_cache/\n";
  files["tests/__init__.py"] = "";
  files["tests/test_graph.py"] = testFile(c);
  files["langgraph.json"] = JSON.stringify({ $schema: "https://langgra.ph/schema.json", dependencies: ["."], graphs, env: ".env" }, null, 2) + "\n";
  files[".env.example"] = "OPENAI_API_KEY=sk-...\nLAB_MODEL=openai:gpt-5-mini\n# LangSmith 트레이싱 (선택)\nLANGSMITH_TRACING=true\nLANGSMITH_API_KEY=\n";
  files["README.md"] = readme(c);
  return files;
}

/** 서버 캐시 키 계산용: 좌표/임의 id 를 제거하고 노드 이름 기준으로 정규화 (서브그래프까지 재귀) */
export function normalizeGraph(g: Graph) {
  return { ...normalizeLevel(g), settings: g.settings };
}

export type NormNode = { id: string; type: string; data: Record<string, unknown> };

export function normalizeLevel(g: SubGraph): { nodes: NormNode[]; edges: { source: string; target: string; sourceHandle: string | null; label: null }[] } {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const name = (id: string) => {
    const n = byId.get(id);
    return n ? (n.kind === "start" ? "__start__" : n.kind === "end" ? "__end__" : n.data.name) : id;
  };
  return {
    nodes: g.nodes.map((n) => {
      const { graph, preset, ...data } = n.data;
      void preset; // 출처 정보는 코드에 영향이 없다
      return { id: name(n.id), type: n.kind, data: graph ? { ...data, graph: normalizeLevel(graph) } : { ...data } };
    }),
    edges: g.edges.map((e) => ({ source: name(e.source), target: name(e.target), sourceHandle: e.sourceHandle ?? null, label: null })),
  };
}
