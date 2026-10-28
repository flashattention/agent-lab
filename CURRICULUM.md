# AgentLab 커리큘럼 (Zero → Production AI Agent Engineer)

각 강의는 `frontend/content/learn/<모듈>/<강의>/` 에 위치한다. 다른 강의에서 다룰 내용은 깊게 반복하지 말고 "→ 7.2에서 자세히" 처럼 참조한다.

## 01-foundations — AI Agent의 세계 (입문)
- 01-what-is-an-agent — AI Agent란? LLM vs Workflow vs Agent, 자율성 스펙트럼, 인지 아키텍처(perceive-reason-act), 에이전트 루프. 실습: 순수 Python으로 규칙기반 "가짜 에이전트 루프" 구현해 루프 개념 체득
- 02-llm-fundamentals — LLM 핵심: 토큰/tiktoken, 컨텍스트 윈도우, 샘플링, 추론(reasoning) 모델, 비용 계산, 메시지 역할(system/user/assistant/tool)
- 03-agent-taxonomy — 에이전트의 다양한 형태: Augmented LLM, Prompt chaining, Routing, Parallelization, Orchestrator-workers, Evaluator-optimizer, Autonomous agent, ReAct/Plan-and-Execute/Reflexion/ReWOO/LATS, 코딩·리서치·브라우저·음성 에이전트, Deep Agents. 2026 업계 지형(LangGraph, OpenAI Agents SDK, Claude Agent SDK, CrewAI, AutoGen 등) 비교
- 04-first-llm-call — LangChain으로 첫 LLM 호출: init_chat_model, invoke/stream/batch, 메시지, usage_metadata, 에러처리

## 02-langchain-core — LangChain v1 핵심 (초급)
- 01-messages-and-content-blocks — 메시지 타입, content_blocks(표준 콘텐츠 블록: text/reasoning/image/tool_call), 멀티모달 입력 형식
- 02-prompts-and-runnables — 프롬프트 템플릿, LCEL(`|`), Runnable 인터페이스(invoke/batch/stream/ainvoke), RunnableParallel/Lambda, with_retry/with_fallbacks
- 03-structured-output — Pydantic/TypedDict/JSON Schema 구조화 출력, with_structured_output, 추출(extraction) 실무, 검증 실패 처리
- 04-tools-and-tool-calling — @tool, 스키마 설계, bind_tools, tool_calls 처리, ToolMessage, 병렬 도구 호출, ToolRuntime(상태/컨텍스트 주입), 좋은 도구 설계 원칙
- 05-streaming — stream/astream, 토큰 스트리밍, astream_events, 청크 합치기, UX 관점

## 03-building-agents — create_agent로 에이전트 만들기 (초급→중급)
- 01-react-loop-from-scratch — ReAct 루프를 순수 Python + LangChain 모델로 직접 구현(while 루프, tool 실행, 종료 조건, max_iterations)
- 02-create-agent — `langchain.agents.create_agent` 완전 정복: tools, system_prompt, response_format(구조화 응답), name, 내부 그래프 구조
- 03-middleware — 미들웨어 아키텍처(before_agent/before_model/wrap_model_call/after_model/wrap_tool_call/after_agent), 내장 미들웨어(Summarization, HITL, PII, ModelCallLimit, ToolCallLimit, ModelFallback, ToolRetry, TodoList, LLMToolSelector, ContextEditing), 커스텀 미들웨어 작성
- 04-memory-and-context — 단기 메모리(checkpointer+thread_id), context_schema & Runtime 컨텍스트, dynamic_prompt, 메시지 트리밍/요약, 컨텍스트 엔지니어링 원칙(write/select/compress/isolate)

## 04-langgraph-core — LangGraph 핵심 (중급)
- 01-graph-basics — StateGraph/START/END/노드/엣지, compile, invoke, 그래프 시각화(draw_mermaid), 왜 그래프인가
- 02-state-and-reducers — TypedDict/Pydantic/dataclass 상태, Annotated 리듀서, add_messages, 커스텀 리듀서, Overwrite, input/output 스키마, private state
- 03-conditional-edges — add_conditional_edges, 라우팅 함수, path_map, 루프와 종료 조건, recursion_limit
- 04-command-and-send — Command(update/goto/graph=PARENT), 노드 내 동적 라우팅, Send로 동적 fan-out(map-reduce), 병렬 실행과 superstep
- 05-react-agent-in-langgraph — ToolNode/tools_condition으로 ReAct 에이전트 직접 구성 → create_agent와 비교, 커스터마이징 포인트
- 06-subgraphs — 서브그래프(공유 상태/변환 상태), 네임스페이스, 모듈화 설계, 서브그래프 스트리밍
- 07-functional-api — @entrypoint/@task, Graph API와의 비교, 언제 무엇을 쓰나

## 05-persistence-and-hitl — 영속성·Human-in-the-loop·장기 메모리 (중급→고급)
- 01-checkpointers-and-threads — InMemorySaver/SqliteSaver/PostgresSaver, thread, get_state/get_state_history, 내구성 모드(durability)
- 02-time-travel — 리플레이, update_state로 포크, 디버깅 워크플로
- 03-human-in-the-loop — interrupt()/Command(resume=...), 승인·편집·거절 패턴, 다중 interrupt, HumanInTheLoopMiddleware
- 04-long-term-memory — Store(InMemoryStore, 네임스페이스, 시맨틱 검색 index), 메모리 유형(semantic/episodic/procedural), 백그라운드 메모리 추출
- 05-reliability — RetryPolicy, CachePolicy, timeout, 노드 에러 처리, 멱등성, durable execution

## 06-rag-and-vector-db — RAG와 벡터 DB (중급→고급)
- 01-embeddings-and-similarity — 임베딩 원리, 코사인 유사도 numpy 직접 구현, 차원/정규화, 임베딩 모델 선택
- 02-documents-and-chunking — Document, 텍스트 분할 전략(Recursive, 마크다운 헤더, 토큰 기반), chunk size/overlap 튜닝, 메타데이터
- 03-vector-stores — InMemoryVectorStore, Qdrant(:memory:), Chroma(Ephemeral) 실습, 메타데이터 필터, MMR, 프로덕션 DB 비교(pgvector, Pinecone, Weaviate, Milvus, Elasticsearch/OpenSearch, MongoDB Atlas, Redis), 인덱스(HNSW/IVF), 하이브리드 검색(BM25+dense), 리랭킹
- 04-agentic-rag — retriever를 도구로, LangGraph Agentic RAG(검색 결정 → 관련성 평가 → 질의 재작성 → 생성)
- 05-advanced-rag — Corrective RAG, Self-RAG, Adaptive RAG, 쿼리 분해/HyDE, RAG 평가(정확성, faithfulness, context recall), GraphRAG 개요

## 07-multi-agent — 멀티 에이전트 시스템 (고급)
- 01-multi-agent-patterns — 왜/언제 멀티 에이전트인가, 패턴(Supervisor, Hierarchical, Network, Swarm/Handoff, Agents-as-tools), 장단점, 컨텍스트 격리
- 02-supervisor — Supervisor 직접 구현(구조화 출력 라우터 + Command), langgraph-supervisor 라이브러리 비교
- 03-handoffs-and-swarm — 핸드오프 도구(Command(goto, graph=Command.PARENT)), 스웜 패턴, langgraph-swarm
- 04-plan-and-execute — Planner/Executor/Replanner, 체크리스트 기반 실행, ReWOO 비교
- 05-reflection-and-evaluator — Reflection, Evaluator-Optimizer 루프, 품질 기준과 반복 상한
- 06-deep-agents — 장기 과제 에이전트: 계획(Todo), 가상 파일시스템, 서브에이전트, deepagents 라이브러리(create_deep_agent)

## 08-production — 프로덕션 AI Agent 엔지니어링 (전문가)
- 01-streaming-in-depth — stream_mode(values/updates/messages/custom/debug) 조합, subgraphs=True, get_stream_writer, 프론트엔드 연동
- 02-observability-and-evals — LangSmith 트레이싱, 메타데이터/태그, 평가 데이터셋, LLM-as-judge, 궤적(trajectory) 평가, 회귀 테스트, 단위 테스트(Mock 모델로 그래프 테스트)
- 03-guardrails-and-security — 프롬프트 인젝션, 도구 권한 최소화, PII, 입력/출력 가드레일, HITL 승인, 비용 한도, 샌드박싱
- 04-mcp-integration — Model Context Protocol 개념, FastMCP로 서버 만들기, LangChain에서 MCP 도구 사용
- 05-deployment — FastAPI로 에이전트 서빙(스트리밍 SSE), 비동기/동시성, langgraph.json & LangGraph Server(Agent Server)/Platform, 체크포인터·스토어 프로덕션 구성, 스케일링
- 06-cost-and-performance — 모델 라우팅, 캐싱(프롬프트 캐싱/노드 캐시), 병렬화, 토큰 예산, 폴백, 지연 최적화
- 07-capstone — 캡스톤: 고객지원 멀티 에이전트(라우터 + RAG + 도구 + HITL 환불 승인 + 메모리 + 스트리밍) 설계와 구현, 아키텍처 리뷰 체크리스트
