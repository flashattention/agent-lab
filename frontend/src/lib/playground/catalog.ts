import type { NodeData, NodeKind } from "./types.ts";

export type KindInfo = {
  kind: NodeKind;
  label: string;
  category: "흐름" | "노드" | "라우팅 · 제어" | "멀티 에이전트";
  icon: string; // lucide kebab-case
  color: string; // tailwind 색 이름 계열 hex
  description: string;
  api: string; // 대응되는 LangGraph/LangChain API
  defaults: () => Partial<NodeData>;
  maxIn?: number;
  maxOut?: number;
  unique?: boolean;
};

export const KINDS: Record<NodeKind, KindInfo> = {
  start: {
    kind: "start",
    label: "START",
    category: "흐름",
    icon: "play",
    color: "#10b981",
    description: "그래프의 진입점. 사용자 입력이 여기서 시작됩니다.",
    api: "langgraph.graph.START",
    defaults: () => ({ name: "__start__" }),
    maxIn: 0,
    unique: true,
  },
  end: {
    kind: "end",
    label: "END",
    category: "흐름",
    icon: "flag",
    color: "#64748b",
    description: "그래프 종료 지점. 여기에 도달하면 실행이 끝납니다.",
    api: "langgraph.graph.END",
    defaults: () => ({ name: "__end__" }),
    maxOut: 0,
    unique: true,
  },
  llm: {
    kind: "llm",
    label: "LLM 노드",
    category: "노드",
    icon: "sparkles",
    color: "#8b5cf6",
    description: "채팅 모델을 호출해 응답 메시지를 상태에 추가합니다. 뒤에 Tools 라우터가 오면 도구가 자동 바인딩됩니다.",
    api: "init_chat_model(...).invoke / bind_tools",
    defaults: () => ({ name: "assistant", prompt: "당신은 유능한 AI 어시스턴트입니다. 한국어로 간결하고 정확하게 답하세요." }),
  },
  agent: {
    kind: "agent",
    label: "Agent (create_agent)",
    category: "노드",
    icon: "bot",
    color: "#6366f1",
    description: "도구를 가진 완성형 ReAct 에이전트를 하나의 노드로 사용합니다. 멀티 에이전트의 워커로 적합합니다.",
    api: "langchain.agents.create_agent",
    defaults: () => ({ name: "agent", prompt: "당신은 도구를 활용하는 전문 에이전트입니다.", tools: ["web_search"], description: "웹 검색으로 정보를 조사" }),
  },
  tools: {
    kind: "tools",
    label: "Tools (ToolNode)",
    category: "노드",
    icon: "wrench",
    color: "#f59e0b",
    description: "LLM이 요청한 tool_calls 를 실제로 실행하고 ToolMessage 를 돌려줍니다.",
    api: "langgraph.prebuilt.ToolNode",
    defaults: () => ({ name: "tools", tools: ["get_weather", "web_search"] }),
  },
  retriever: {
    kind: "retriever",
    label: "Retriever (RAG)",
    category: "노드",
    icon: "database",
    color: "#0ea5e9",
    description: "벡터 스토어에서 질문과 관련된 문서를 검색해 state.context 에 넣습니다.",
    api: "InMemoryVectorStore.as_retriever",
    defaults: () => ({ name: "retrieve", k: 3 }),
  },
  function: {
    kind: "function",
    label: "Function",
    category: "노드",
    icon: "braces",
    color: "#14b8a6",
    description: "직접 작성한 Python 함수 노드. 상태를 받아 업데이트(dict)를 반환합니다.",
    api: "StateGraph.add_node(fn)",
    defaults: () => ({
      name: "process",
      code: '# state 를 받아 업데이트할 키만 dict 로 반환하세요.\nlast = state["messages"][-1]\nprint(f"[process] 마지막 메시지 길이: {len(str(last.content))}")\nreturn {}',
    }),
  },
  human: {
    kind: "human",
    label: "Human-in-the-loop",
    category: "노드",
    icon: "user-check",
    color: "#ec4899",
    description: "interrupt()로 실행을 멈추고 사람의 승인/수정을 받은 뒤 Command(resume=...)로 재개합니다. Checkpointer 필수.",
    api: "langgraph.types.interrupt",
    defaults: () => ({ name: "human_review", prompt: "이 응답을 사용자에게 보내도 될까요?" }),
  },
  router: {
    kind: "router",
    label: "Conditional Edge",
    category: "라우팅 · 제어",
    icon: "git-fork",
    color: "#f97316",
    description: "이전 노드 뒤에 add_conditional_edges 로 붙는 라우팅 함수. 나가는 엣지마다 하나의 경로가 됩니다.",
    api: "StateGraph.add_conditional_edges",
    defaults: () => ({ name: "route", strategy: "llm", prompt: "사용자 요청을 가장 잘 처리할 경로를 고르세요." }),
  },
  evaluator: {
    kind: "evaluator",
    label: "Evaluator (Reflection)",
    category: "라우팅 · 제어",
    icon: "scale",
    color: "#e11d48",
    description: "직전 결과를 기준에 따라 평가해 pass → 다음 단계, retry → 재시도 경로로 보냅니다. 반복 상한 포함.",
    api: "with_structured_output + add_conditional_edges",
    defaults: () => ({ name: "evaluate", prompt: "답변이 질문에 정확하고 완결적으로 답했는가?", maxIterations: 3 }),
  },
  supervisor: {
    kind: "supervisor",
    label: "Supervisor",
    category: "멀티 에이전트",
    icon: "crown",
    color: "#a855f7",
    description: "연결된 워커 에이전트 중 다음 작업자를 고르고 Command(goto=...)로 위임합니다. 워커는 다시 Supervisor로 돌아와야 합니다.",
    api: "langgraph.types.Command(goto=...)",
    defaults: () => ({ name: "supervisor", prompt: "당신은 팀 매니저입니다. 작업을 가장 잘 처리할 팀원에게 순서대로 위임하고, 모두 끝나면 FINISH 를 고르세요.", maxIterations: 6 }),
  },
  map: {
    kind: "map",
    label: "Map (Send fan-out)",
    category: "멀티 에이전트",
    icon: "split",
    color: "#22c55e",
    description: "직전 결과를 여러 항목으로 나눠 Send API로 워커 노드를 병렬 실행합니다 (map-reduce).",
    api: "langgraph.types.Send",
    defaults: () => ({ name: "fan_out", maxItems: 4 }),
  },
  reduce: {
    kind: "reduce",
    label: "Reduce (Aggregate)",
    category: "멀티 에이전트",
    icon: "merge",
    color: "#84cc16",
    description: "병렬 워커들의 결과(state.results)를 모아 하나의 최종 답변으로 합칩니다.",
    api: "Annotated[list, operator.add] 리듀서",
    defaults: () => ({ name: "aggregate", prompt: "아래 부분 결과들을 하나의 일관된 최종 답변으로 종합하세요." }),
  },
};

export const PALETTE_ORDER: NodeKind[] = [
  "start",
  "end",
  "llm",
  "agent",
  "tools",
  "retriever",
  "function",
  "human",
  "router",
  "evaluator",
  "supervisor",
  "map",
  "reduce",
];

/* ------------------------------------------------------------------ 도구 라이브러리 */
export type ToolDef = { name: string; label: string; description: string; sensitive?: boolean; code: string };

export const TOOL_LIBRARY: Record<string, ToolDef> = {
  get_weather: {
    name: "get_weather",
    label: "날씨 조회",
    description: "도시의 현재 날씨",
    code: `@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    data = {"서울": "맑음, 18°C", "부산": "구름 조금, 21°C", "도쿄": "비, 16°C", "뉴욕": "흐림, 12°C"}
    return f"{city}: {data.get(city, '맑음, 20°C')}"`,
  },
  web_search: {
    name: "web_search",
    label: "웹 검색 (데모)",
    description: "웹 검색 결과 요약",
    code: `@tool
def web_search(query: str) -> str:
    """웹에서 정보를 검색해 상위 결과를 요약합니다. (데모용 고정 데이터)"""
    corpus = {
        "langgraph": "LangGraph 는 상태 기반 그래프로 장기 실행·멀티 에이전트 워크플로를 만드는 오케스트레이션 프레임워크입니다.",
        "여행": "가을 서울 여행은 북촌 한옥마을, 경복궁 야간개장, 한강 공원 피크닉이 인기입니다.",
        "ai": "2026년 AI 에이전트는 MCP 기반 도구 연동, 장기 메모리, 평가 자동화가 핵심 트렌드입니다.",
    }
    hits = [v for k, v in corpus.items() if k in query.lower()]
    return "\\n".join(hits) or f"'{query}' 에 대한 검색 결과: 관련 문서 3건 (요약 생략)"`,
  },
  calculator: {
    name: "calculator",
    label: "계산기",
    description: "안전한 산술 계산",
    code: `@tool
def calculator(expression: str) -> str:
    """사칙연산/거듭제곱 수식을 계산합니다. 예: '(3 + 4) * 2'"""
    import ast
    import operator as op

    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg}

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("지원하지 않는 수식입니다")

    try:
        return str(ev(ast.parse(expression, mode="eval").body))
    except Exception as exc:  # 도구 오류는 문자열로 돌려줘 LLM 이 스스로 복구하게 한다
        return f"계산 실패: {exc}"`,
  },
  search_docs: {
    name: "search_docs",
    label: "사내 문서 검색",
    description: "지식베이스 키워드 검색",
    code: `@tool
def search_docs(query: str) -> str:
    """사내 지식베이스(FAQ)에서 관련 문서를 찾습니다."""
    faq = {
        "환불": "환불은 결제 후 14일 이내 가능하며, 영업일 기준 3~5일 소요됩니다.",
        "배송": "기본 배송은 2~3일, 제주/도서산간은 추가 1~2일이 걸립니다.",
        "비밀번호": "설정 > 보안 > 비밀번호 재설정에서 이메일 인증 후 변경할 수 있습니다.",
    }
    hits = [f"[{k}] {v}" for k, v in faq.items() if k in query]
    return "\\n".join(hits) or "관련 문서를 찾지 못했습니다."`,
  },
  get_order_status: {
    name: "get_order_status",
    label: "주문 조회",
    description: "주문 번호로 배송 상태 확인",
    code: `@tool
def get_order_status(order_id: str) -> str:
    """주문 번호로 주문/배송 상태를 조회합니다."""
    return f"주문 {order_id}: 결제 완료 → 배송 중 (예상 도착: 내일)"`,
  },
  issue_refund: {
    name: "issue_refund",
    label: "환불 실행 ⚠️",
    description: "실제 환불을 실행 (민감)",
    sensitive: true,
    code: `@tool
def issue_refund(order_id: str, amount: int) -> str:
    """주문에 대해 환불을 실행합니다. (민감한 작업 — 운영에서는 HITL 승인 필수)"""
    return f"주문 {order_id} 에 {amount:,}원 환불 요청이 접수되었습니다."`,
  },
  get_current_time: {
    name: "get_current_time",
    label: "현재 시각",
    description: "현재 날짜와 시각",
    code: `@tool
def get_current_time() -> str:
    """현재 날짜와 시각(ISO 8601)을 반환합니다."""
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")`,
  },
};

export function defaultData(kind: NodeKind): NodeData {
  return { name: kind, ...KINDS[kind].defaults() } as NodeData;
}
