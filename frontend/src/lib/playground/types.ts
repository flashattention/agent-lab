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
  | "reduce"
  | "subgraph";

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
  model?: string; // 노드별 모델 (init_chat_model 형식, 예: "openai:gpt-5"). 비우면 LAB_MODEL
  middleware?: AgentMiddleware; // agent 전용: create_agent(middleware=[...])
  // subgraph 전용
  graph?: SubGraph; // 안쪽 그래프 (START/END 를 가진 완결된 그래프). 설정은 최상위 그래프를 따른다.
  io?: SubgraphIO;
  memory?: SubgraphMemory;
  preset?: PresetLink; // 프리셋에서 가져온 경우 출처
};

/** Agent(create_agent) 노드의 미들웨어. 켠 것만 값이 있다. langchain.agents.middleware 1.4 기준 */
export type AgentMiddleware = {
  hitl?: { tools: string[] }; // HumanInTheLoopMiddleware: 이 도구들은 실행 전에 사람 승인
  modelCallLimit?: number; // ModelCallLimitMiddleware(run_limit=N)
  toolCallLimit?: number; // ToolCallLimitMiddleware(run_limit=N)
  summarization?: { tokens: number }; // SummarizationMiddleware(trigger=("tokens", N))
  retry?: { maxRetries: number }; // ModelRetryMiddleware + ToolRetryMiddleware
  fallback?: string; // ModelFallbackMiddleware(모델 ID)
  pii?: { types: PiiType[]; strategy: "redact" | "mask" | "hash" | "block" }; // PIIMiddleware (사용자 입력)
};
export type PiiType = "email" | "credit_card" | "ip" | "mac_address" | "url";

/** 서브그래프와 부모 그래프가 상태를 주고받는 방식 */
export type SubgraphIO =
  | "isolated" // 대화 기록을 넘기고 최종 답변 한 개만 돌려받는다 (컨텍스트 격리, 기본)
  | "shared"; // 컴파일된 서브그래프를 그대로 노드로 등록해 messages 등 같은 키를 공유한다

/** 서브그래프의 체크포인트(메모리) 방식 */
export type SubgraphMemory =
  | "inherit" // 부모 체크포인터를 이어받는다. 호출마다 새로 시작 (기본)
  | "persistent"; // checkpointer=True: 같은 thread 에서 호출될 때마다 이전 대화를 기억한다

export type PresetLink = { id: string; name: string; updatedAt?: string; market?: boolean }; // market: 마켓·링크 공유에서 가져옴

/** 서브그래프. tools 는 프리셋으로 옮길 때 함께 가져가는 커스텀 도구 정의 */
export type SubGraph = { nodes: GNode[]; edges: GEdge[]; tools?: CustomTool[] };

/** 사용자가 직접 작성한 @tool 함수 */
export type CustomTool = { name: string; description: string; code: string; sensitive?: boolean };

export type GNode = { id: string; kind: NodeKind; data: NodeData; position: { x: number; y: number } };
export type GEdge = { id: string; source: string; target: string; sourceHandle?: string | null; label?: string };

export type GraphSettings = {
  checkpointer: "none" | "memory" | "sqlite";
  store: boolean;
  recursionLimit: number;
  demoInput: string;
  streamMode: "updates" | "values" | "messages";
  customTools?: CustomTool[];
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
  path?: string[]; // 문제가 있는 그래프의 위치: 최상위는 [], 서브그래프 안이면 subgraph 노드 id 들
  message: string;
  hint?: string;
  nodes?: string[]; // node ids
  edges?: string[]; // edge ids
};

export type Analysis = {
  issues: Issue[];
  ok: boolean;
};

export type Highlight = {
  errorNodes: Set<string>;
  warnNodes: Set<string>;
  errorEdges: Set<string>;
  warnEdges: Set<string>;
};
