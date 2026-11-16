// 잘 설계된 에이전트 패턴 예시 모음 (플레이그라운드 갤러리)
import type { GEdge, GNode, Graph, GraphSettings, NodeData, NodeKind, SubGraph } from "./types.ts";
import { DEFAULT_SETTINGS } from "./types.ts";
import { defaultData } from "./catalog.ts";

type NodeSpec = [kind: NodeKind, name: string, data?: Partial<NodeData>];
type EdgeSpec = [source: string, target: string, handle?: string];

export type Pattern = {
  id: string;
  title: string;
  summary: string;
  category: "기초" | "워크플로" | "RAG" | "멀티 에이전트" | "프로덕션";
  difficulty: "초급" | "중급" | "고급";
  why: string; // 언제 쓰는가
  graph: Graph;
};

function build(nodes: NodeSpec[], edges: EdgeSpec[], settings: Partial<GraphSettings> = {}): Graph {
  const gnodes: GNode[] = nodes.map(([kind, name, data]) => ({
    id: kind === "start" ? "start" : kind === "end" ? "end" : name,
    kind,
    data: { ...defaultData(kind), name: kind === "start" ? "__start__" : kind === "end" ? "__end__" : name, ...data },
    position: { x: 0, y: 0 },
  }));
  const gedges: GEdge[] = edges.map(([s, t, h], i) => ({
    id: `e${i}-${s}-${t}`,
    source: s === "START" ? "start" : s === "END" ? "end" : s,
    target: t === "START" ? "start" : t === "END" ? "end" : t,
    sourceHandle: h ?? null,
  }));
  return { nodes: gnodes, edges: gedges, settings: { ...DEFAULT_SETTINGS, ...settings } };
}

/** 서브그래프(Sub-agent)의 안쪽 그래프 */
function sub(nodes: NodeSpec[], edges: EdgeSpec[]): SubGraph {
  const { nodes: n, edges: e } = build(nodes, edges);
  return { nodes: n, edges: e };
}

export const PATTERNS: Pattern[] = [
  {
    id: "react-agent",
    title: "ReAct Agent (직접 구성)",
    summary: "LLM ↔ ToolNode 루프. tools_condition 으로 도구 호출 여부를 판단하는 가장 기본적인 에이전트.",
    category: "기초",
    difficulty: "초급",
    why: "도구가 필요한 대부분의 단일 에이전트. create_agent 의 내부 구조를 직접 다루고 싶을 때.",
    graph: build(
      [
        ["start", "START"],
        ["llm", "assistant", { prompt: "당신은 도구를 활용하는 여행 도우미입니다. 필요한 정보는 도구로 조회하세요." }],
        ["router", "should_continue", { strategy: "tools_condition" }],
        ["tools", "tools", { tools: ["get_weather", "web_search", "calculator"] }],
        ["end", "END"],
      ],
      [
        ["START", "assistant"],
        ["assistant", "should_continue"],
        ["should_continue", "tools"],
        ["should_continue", "END"],
        ["tools", "assistant"],
      ],
    ),
  },
  {
    id: "prebuilt-agent",
    title: "create_agent 한 줄 에이전트",
    summary: "LangChain v1 create_agent 로 만든 완성형 에이전트를 노드 하나로 사용. 호출 상한·재시도 미들웨어 포함 (더블클릭해 설정).",
    category: "기초",
    difficulty: "초급",
    why: "빠른 프로토타이핑. 미들웨어로 확장하는 표준 진입점.",
    graph: build(
      [
        ["start", "START"],
        [
          "agent",
          "travel_agent",
          {
            prompt: "당신은 친절한 여행 플래너입니다.",
            tools: ["get_weather", "web_search"],
            description: "날씨와 여행 정보를 조사",
            middleware: { modelCallLimit: 10, toolCallLimit: 20, retry: { maxRetries: 2 } },
          },
        ],
        ["end", "END"],
      ],
      [
        ["START", "travel_agent"],
        ["travel_agent", "END"],
      ],
    ),
  },
  {
    id: "prompt-chaining",
    title: "Prompt Chaining",
    summary: "개요 → 초안 → 다듬기. 고정된 단계로 나누고 중간에 Function 게이트로 품질을 검사.",
    category: "워크플로",
    difficulty: "초급",
    why: "작업을 명확한 하위 단계로 나눌 수 있을 때. 각 호출을 단순하게 만들어 정확도를 높인다.",
    graph: build(
      [
        ["start", "START"],
        ["llm", "outline", { prompt: "주제에 대한 글의 개요를 3개의 불릿으로 작성하세요." }],
        ["function", "gate", { code: '# 프로그래밍적 게이트: 개요가 비어 있으면 경고\noutline = state["messages"][-1].text\nprint(f"  🚦 gate: 개요 길이 {len(outline)}자")\nreturn {}' }],
        ["llm", "draft", { prompt: "직전 개요를 바탕으로 3문단 블로그 글 초안을 작성하세요." }],
        ["llm", "polish", { prompt: "초안의 문장을 매끄럽게 다듬고 제목을 붙이세요." }],
        ["end", "END"],
      ],
      [
        ["START", "outline"],
        ["outline", "gate"],
        ["gate", "draft"],
        ["draft", "polish"],
        ["polish", "END"],
      ],
      { demoInput: "AI 에이전트가 바꿀 개발자의 하루" },
    ),
  },
  {
    id: "router",
    title: "Routing (의도 분류)",
    summary: "LLM 라우터가 질문을 분류해 전문 에이전트로 보냄. add_conditional_edges 의 대표 예.",
    category: "워크플로",
    difficulty: "초급",
    why: "입력 유형이 뚜렷이 나뉘고, 유형별로 다른 프롬프트/도구/모델이 필요할 때.",
    graph: build(
      [
        ["start", "START"],
        ["router", "classify", { strategy: "llm", prompt: "고객 문의를 분류하세요: 주문/배송은 order_agent, 환불/정책은 policy_agent, 그 외는 general." }],
        ["agent", "order_agent", { prompt: "주문/배송 담당 상담원입니다.", tools: ["get_order_status"], description: "주문 상태와 배송 조회" }],
        ["agent", "policy_agent", { prompt: "환불/정책 담당 상담원입니다.", tools: ["search_docs"], description: "환불 규정 등 정책 안내" }],
        ["llm", "general", { prompt: "친절한 일반 상담원입니다.", description: "그 밖의 일반 문의" }],
        ["end", "END"],
      ],
      [
        ["START", "classify"],
        ["classify", "order_agent"],
        ["classify", "policy_agent"],
        ["classify", "general"],
        ["order_agent", "END"],
        ["policy_agent", "END"],
        ["general", "END"],
      ],
      { demoInput: "주문번호 A-1024 배송이 언제 오나요?" },
    ),
  },
  {
    id: "parallel",
    title: "Parallelization (Sectioning)",
    summary: "독립적인 관점 3개를 동시에 실행하고 defer 노드로 모아 종합.",
    category: "워크플로",
    difficulty: "중급",
    why: "서로 독립적인 하위 작업으로 지연을 줄이거나, 여러 관점을 얻어 품질을 높이고 싶을 때.",
    graph: build(
      [
        ["start", "START"],
        ["llm", "pros", { prompt: "주제의 장점만 3가지 분석하세요." }],
        ["llm", "cons", { prompt: "주제의 단점/리스크만 3가지 분석하세요." }],
        ["llm", "market", { prompt: "주제의 시장 동향만 분석하세요." }],
        ["llm", "synthesize", { prompt: "앞선 세 분석을 종합해 의사결정용 요약을 작성하세요." }],
        ["end", "END"],
      ],
      [
        ["START", "pros"],
        ["START", "cons"],
        ["START", "market"],
        ["pros", "synthesize"],
        ["cons", "synthesize"],
        ["market", "synthesize"],
        ["synthesize", "END"],
      ],
      { demoInput: "사내 고객지원에 AI 에이전트를 도입해야 할까?" },
    ),
  },
  {
    id: "map-reduce",
    title: "Map-Reduce (Send API)",
    summary: "계획 노드가 항목을 만들고, Send 로 워커를 동적 개수만큼 병렬 실행한 뒤 Reduce.",
    category: "멀티 에이전트",
    difficulty: "중급",
    why: "처리할 항목 수가 실행 시점에 정해질 때 (문서 N개 요약, 키워드별 조사 등).",
    graph: build(
      [
        ["start", "START"],
        ["llm", "planner", { prompt: "질문을 조사하기 위한 하위 주제를 줄마다 하나씩 3~4개 나열하세요." }],
        ["map", "fan_out", { maxItems: 4 }],
        ["llm", "researcher", { prompt: "주어진 하위 주제를 3문장으로 조사·요약하세요." }],
        ["reduce", "aggregate"],
        ["end", "END"],
      ],
      [
        ["START", "planner"],
        ["planner", "fan_out"],
        ["fan_out", "researcher"],
        ["researcher", "aggregate"],
        ["aggregate", "END"],
      ],
      { demoInput: "2026년 AI 에이전트 기술 트렌드를 조사해줘" },
    ),
  },
  {
    id: "reflection",
    title: "Reflection / Evaluator-Optimizer",
    summary: "생성 → 평가 → (재시도 | 통과). 반복 상한으로 무한 루프를 방지.",
    category: "워크플로",
    difficulty: "중급",
    why: "명확한 평가 기준이 있고, 반복 개선으로 품질이 측정 가능하게 올라갈 때.",
    graph: build(
      [
        ["start", "START"],
        ["llm", "writer", { prompt: "요청에 맞는 고품질 답변을 작성하세요. 피드백이 있으면 반드시 반영하세요." }],
        ["evaluator", "critic", { prompt: "정확성, 구체성, 한국어 문장 품질을 모두 만족해야 pass", maxIterations: 3 }],
        ["end", "END"],
      ],
      [
        ["START", "writer"],
        ["writer", "critic"],
        ["critic", "END", "pass"],
        ["critic", "writer", "retry"],
      ],
      { demoInput: "LangGraph 의 체크포인터를 비유를 들어 설명해줘" },
    ),
  },
  {
    id: "plan-execute",
    title: "Plan-and-Execute",
    summary: "Planner 가 계획을 세우고 Executor 에이전트가 실행, Replanner(Evaluator)가 완료 여부 판단.",
    category: "멀티 에이전트",
    difficulty: "고급",
    why: "여러 단계가 필요한 장기 과제. 매 스텝 전체 재추론하는 ReAct 보다 비용/일관성이 좋다.",
    graph: build(
      [
        ["start", "START"],
        ["llm", "planner", { prompt: "목표를 달성하기 위한 단계별 계획을 번호 목록으로 작성하세요." }],
        ["agent", "executor", { prompt: "계획의 다음 미완료 단계를 도구로 수행하고 결과를 보고하세요.", tools: ["web_search", "calculator", "get_current_time"], description: "계획 단계 실행" }],
        ["evaluator", "replanner", { prompt: "계획의 모든 단계가 완료되어 최종 답을 줄 수 있으면 pass", maxIterations: 4 }],
        ["llm", "final_answer", { prompt: "지금까지의 실행 결과로 사용자에게 최종 답변을 작성하세요." }],
        ["end", "END"],
      ],
      [
        ["START", "planner"],
        ["planner", "executor"],
        ["executor", "replanner"],
        ["replanner", "final_answer", "pass"],
        ["replanner", "executor", "retry"],
        ["final_answer", "END"],
      ],
      { demoInput: "LangGraph 관련 최신 정보를 찾아보고 학습 계획을 세워줘" },
    ),
  },
  {
    id: "supervisor",
    title: "Supervisor 멀티 에이전트",
    summary: "Supervisor 가 리서처/작가/분석가에게 순서대로 위임 (Command goto). 워커는 Supervisor 로 복귀.",
    category: "멀티 에이전트",
    difficulty: "고급",
    why: "전문 영역이 다른 에이전트 여러 개를 중앙에서 조율해야 할 때.",
    graph: build(
      [
        ["start", "START"],
        ["supervisor", "supervisor", { maxIterations: 6 }],
        ["agent", "researcher", { prompt: "당신은 리서처입니다. 웹 검색으로 사실을 수집하세요.", tools: ["web_search"], description: "웹 검색으로 사실 수집" }],
        ["agent", "analyst", { prompt: "당신은 데이터 분석가입니다. 필요한 계산을 수행하세요.", tools: ["calculator"], description: "수치 계산과 분석" }],
        ["llm", "writer", { prompt: "당신은 테크니컬 라이터입니다. 팀이 모은 정보로 보고서를 쓰세요.", description: "최종 보고서 작성" }],
        ["end", "END"],
      ],
      [
        ["START", "supervisor"],
        ["supervisor", "researcher"],
        ["supervisor", "analyst"],
        ["supervisor", "writer"],
        ["researcher", "supervisor"],
        ["analyst", "supervisor"],
        ["writer", "supervisor"],
        ["supervisor", "END"],
      ],
      { demoInput: "AI 에이전트 시장 규모를 조사하고 연 25% 성장 시 3년 후 규모를 계산해 보고서로 써줘" },
    ),
  },
  {
    id: "hierarchical-team",
    title: "계층형 팀 (Sub-agent)",
    summary: "Supervisor 가 리서치 팀·작성 팀 서브그래프에 위임. 각 팀은 자체 ReAct 루프/검토 루프를 가진 독립 그래프.",
    category: "멀티 에이전트",
    difficulty: "고급",
    why: "워커 하나하나가 여러 단계로 이루어진 큰 시스템. 팀 단위로 나눠 만들고, 프리셋으로 저장해 다른 프로젝트에서 재사용할 때.",
    graph: build(
      [
        ["start", "START"],
        ["supervisor", "supervisor", { maxIterations: 4, prompt: "당신은 프로젝트 매니저입니다. 조사가 필요하면 research_team, 문서 작성은 writing_team 에 맡기고 끝나면 FINISH 를 고르세요." }],
        [
          "subgraph",
          "research_team",
          {
            description: "웹 검색과 계산으로 사실과 수치를 조사",
            graph: sub(
              [
                ["start", "START"],
                ["llm", "researcher", { prompt: "당신은 리서처입니다. 도구로 사실과 수치를 모은 뒤 핵심만 요약해 보고하세요." }],
                ["router", "need_tools", { strategy: "tools_condition" }],
                ["tools", "research_tools", { tools: ["web_search", "calculator"] }],
                ["end", "END"],
              ],
              [
                ["START", "researcher"],
                ["researcher", "need_tools"],
                ["need_tools", "research_tools"],
                ["need_tools", "END"],
                ["research_tools", "researcher"],
              ],
            ),
          },
        ],
        [
          "subgraph",
          "writing_team",
          {
            description: "조사 결과로 보고서를 쓰고 스스로 검토해 다듬음",
            graph: sub(
              [
                ["start", "START"],
                ["llm", "drafter", { prompt: "당신은 테크니컬 라이터입니다. 대화에 모인 정보로 짧은 보고서를 쓰세요. 피드백이 있으면 반영하세요." }],
                ["evaluator", "review", { prompt: "보고서가 수치 근거를 포함하고 구조가 명확하면 pass", maxIterations: 2 }],
                ["end", "END"],
              ],
              [
                ["START", "drafter"],
                ["drafter", "review"],
                ["review", "END", "pass"],
                ["review", "drafter", "retry"],
              ],
            ),
          },
        ],
        ["end", "END"],
      ],
      [
        ["START", "supervisor"],
        ["supervisor", "research_team"],
        ["supervisor", "writing_team"],
        ["research_team", "supervisor"],
        ["writing_team", "supervisor"],
        ["supervisor", "END"],
      ],
      { demoInput: "AI 에이전트 시장 규모를 조사하고 연 25% 성장 시 3년 후 규모를 보고서로 정리해줘" },
    ),
  },
  {
    id: "agentic-rag",
    title: "Agentic RAG (Corrective)",
    summary: "검색 → 답변 생성 → 근거 평가. 근거가 부족하면 질의를 재작성해 다시 검색.",
    category: "RAG",
    difficulty: "중급",
    why: "문서 기반 QA 에서 검색 품질 편차가 클 때. 환각을 줄이고 근거 있는 답을 강제한다.",
    graph: build(
      [
        ["start", "START"],
        ["retriever", "retrieve", { k: 3 }],
        ["llm", "generate", { prompt: "참고 문서만 근거로 답하세요. 문서에 없으면 모른다고 답하세요." }],
        ["evaluator", "grade", { prompt: "답변의 모든 주장이 참고 문서에 근거하면 pass", maxIterations: 2 }],
        ["llm", "rewrite_query", { prompt: "검색이 잘 되도록 사용자 질문을 더 구체적인 검색 질의 한 줄로 바꾸세요." }],
        ["end", "END"],
      ],
      [
        ["START", "retrieve"],
        ["retrieve", "generate"],
        ["generate", "grade"],
        ["grade", "END", "pass"],
        ["grade", "rewrite_query", "retry"],
        ["rewrite_query", "retrieve"],
      ],
      { demoInput: "체크포인터는 무슨 역할을 하나요?" },
    ),
  },
  {
    id: "hitl",
    title: "Human-in-the-loop 승인",
    summary: "에이전트가 환불안을 작성 → 사람 승인(interrupt) → 승인 시 실행, 거절 시 재작성.",
    category: "프로덕션",
    difficulty: "중급",
    why: "결제·환불·메일 발송 등 되돌리기 어려운 행동 전에 사람이 확인해야 할 때.",
    graph: build(
      [
        ["start", "START"],
        ["agent", "support_agent", { prompt: "고객 요청을 조사하고 환불 처리 계획을 제안하세요. 아직 환불을 실행하지 마세요.", tools: ["get_order_status", "search_docs"], description: "조사 및 처리안 작성" }],
        ["human", "approval", { prompt: "이 환불 처리안을 승인하시겠습니까?" }],
        ["agent", "executor", { prompt: "승인된 처리안대로 환불을 실행하고 결과를 고객에게 안내하세요.", tools: ["issue_refund"], description: "승인된 작업 실행" }],
        ["end", "END"],
      ],
      [
        ["START", "support_agent"],
        ["support_agent", "approval"],
        ["approval", "executor", "approve"],
        ["approval", "support_agent", "reject"],
        ["executor", "END"],
      ],
      { demoInput: "주문 B-2048 을 환불해 주세요. 30000원 결제했어요." },
    ),
  },
  {
    id: "support-system",
    title: "고객지원 시스템 (종합)",
    summary: "라우터 + RAG + 도구 에이전트 + 품질 평가를 결합한 프로덕션형 구조.",
    category: "프로덕션",
    difficulty: "고급",
    why: "실제 서비스 수준 설계를 한눈에. 각 구성요소를 바꿔 끼우며 실험해 보세요.",
    graph: build(
      [
        ["start", "START"],
        ["router", "triage", { strategy: "llm", prompt: "문의를 분류하세요. 정책/FAQ 질문은 retrieve, 주문 관련은 order_agent." }],
        ["retriever", "retrieve", { k: 3, description: "FAQ/정책 문서 검색" }],
        ["llm", "faq_answer", { prompt: "참고 문서를 근거로 정확히 답하세요.", description: "문서 기반 답변" }],
        ["agent", "order_agent", { prompt: "주문 담당 상담원입니다.", tools: ["get_order_status"], description: "주문/배송 조회" }],
        ["evaluator", "qa_check", { prompt: "답변이 공손하고 정확하며 다음 행동을 안내하면 pass", maxIterations: 2 }],
        ["end", "END"],
      ],
      [
        ["START", "triage"],
        ["triage", "retrieve"],
        ["triage", "order_agent"],
        ["retrieve", "faq_answer"],
        ["faq_answer", "qa_check"],
        ["order_agent", "qa_check"],
        ["qa_check", "END", "pass"],
        ["qa_check", "faq_answer", "retry"],
      ],
      { demoInput: "환불 규정이 어떻게 되나요?", checkpointer: "sqlite" },
    ),
  },
];
