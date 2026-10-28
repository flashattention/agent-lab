// 플레이그라운드 그래프 모델 (React Flow 와 독립적인 순수 타입)

export type NodeKind =
  | "start"
  | "end"
  | "llm"
  | "agent"
  | "tools"
  | "retriever"
  | "function"
  | "human"
  | "router"
  | "evaluator"
  | "supervisor"
  | "map"
  | "reduce";

export type RouterStrategy = "llm" | "tools_condition" | "state_key";

export type NodeData = {
  name: string; // python 식별자 겸 LangGraph 노드 이름
  label?: string;
  prompt?: string; // system prompt / 평가 기준 / 질문
  tools?: string[]; // TOOL_LIBRARY 키
  strategy?: RouterStrategy; // router 전용
  stateKey?: string; // router state_key 전략 전용
  maxIterations?: number; // evaluator / supervisor 루프 상한
  k?: number; // retriever top-k
  maxItems?: number; // map 최대 분기 수
  code?: string; // function 노드 본문
  description?: string; // supervisor 가 worker 를 고를 때 참고하는 설명
};

export type GNode = { id: string; kind: NodeKind; data: NodeData; position: { x: number; y: number } };
export type GEdge = { id: string; source: string; target: string; sourceHandle?: string | null; label?: string };

export type GraphSettings = {
  checkpointer: "none" | "memory" | "sqlite";
  store: boolean;
  recursionLimit: number;
  demoInput: string;
  streamMode: "updates" | "values" | "messages";
};

export type Graph = { nodes: GNode[]; edges: GEdge[]; settings: GraphSettings };

export const DEFAULT_SETTINGS: GraphSettings = {
  checkpointer: "memory",
  store: false,
  recursionLimit: 25,
  demoInput: "서울 날씨를 알려주고 여행 팁도 추천해줘",
  streamMode: "updates",
};

export type IssueLevel = "error" | "warning" | "info";
export type Issue = {
  level: IssueLevel;
  message: string;
  hint?: string;
  nodes?: string[]; // node ids
  edges?: string[]; // edge ids
};

export type Analysis = {
  issues: Issue[];
  errorNodes: Set<string>;
  warnNodes: Set<string>;
  errorEdges: Set<string>;
  warnEdges: Set<string>;
  ok: boolean;
};
