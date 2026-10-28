# AgentLab 콘텐츠 작성 가이드

AgentLab은 AI Agent를 전혀 모르는 초보자를 **현업 AI Agent 엔지니어** 수준까지 끌어올리는 한국어 학습 사이트입니다.
모든 강의 화면의 오른쪽에는 IDE가 있습니다. 학습자는 거기서 코드를 수정하고 실행하고, 결과를 보며 디버깅합니다.

## 실행 환경 (실제로 설치된 버전, 2026-10 기준)

- Python 3.13 / langgraph **1.2.18** / langchain **1.4.7** / langchain-core **1.7.0** / langchain-openai **1.7.3**
- 추가 패키지: pydantic 2.14, langgraph-checkpoint-sqlite, langchain-text-splitters, langchain-qdrant + qdrant-client
  (`QdrantClient(":memory:")`), langchain-chroma + chromadb (`chromadb.EphemeralClient()`, 컬렉션 이름은 3자 이상),
  fastmcp, `langchain.mcp`(beta), deepagents 0.7, langgraph-supervisor, langgraph-swarm, tiktoken, numpy
- **LangChain v1 / LangGraph v1 API만** 씁니다. 금지 목록: `langgraph.prebuilt.create_react_agent`(deprecated, `langchain.agents.create_agent` 사용),
  `MessageGraph`, `langchain.chains`, `AgentExecutor`, `initialize_agent`, `LLMChain`, `ConversationBufferMemory`, `langchain_community`.
- 대표 import:
  ```python
  from langchain.chat_models import init_chat_model
  from langchain.agents import create_agent
  from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware, before_model, wrap_model_call, ...
  from langchain.tools import tool, ToolRuntime
  from langchain.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
  from langgraph.graph import StateGraph, START, END, MessagesState, add_messages
  from langgraph.types import Command, Send, interrupt, RetryPolicy, CachePolicy
  from langgraph.checkpoint.memory import InMemorySaver
  from langgraph.store.memory import InMemoryStore
  from langgraph.func import entrypoint, task
  from langgraph.runtime import Runtime
  ```
- API가 확실하지 않으면 **추측하지 말고** 설치된 소스를 확인하세요:
  `backend/.venv/lib/python3.13/site-packages/` 또는 `cd backend && uv run python -c "import inspect, X; print(inspect.signature(...))"`

## 모델 규칙

- LLM 제공자는 OpenAI만 씁니다. 모델 ID는 항상 환경변수에서 읽습니다. 사용자는 설정 패널에서 모델을 바꿀 수 있습니다.
  ```python
  import os
  MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
  llm = init_chat_model(MODEL)          # 또는 create_agent(MODEL, tools=[...])
  ```
- `temperature`를 설정하지 마세요. GPT-5 계열 추론 모델은 이 값을 거부합니다. 이 점은 본문에서 설명해도 좋습니다.
- 임베딩: `OpenAIEmbeddings(model="text-embedding-3-small")`

## Mock LLM 모드 (반드시 이해할 것)

사용자가 API 키를 넣지 않았거나 검증 스크립트를 실행할 때는 `langchain_openai.ChatOpenAI`/`OpenAIEmbeddings`가
결정적 모의 모델로 교체됩니다(`backend/sandbox/agentlab_mock.py`). 모든 예제는 **Mock 모드에서도 exit 0으로 끝나야** 합니다.

Mock 모델의 동작:
- 도구가 바인딩되어 있고, 마지막 Human 메시지 이후 ToolMessage가 없으면 도구를 호출합니다.
  도구 이름·설명의 단어와 질문의 단어가 겹치는 도구를 최대 3개 고르고, 겹치는 게 없으면 첫 번째 도구를 고릅니다.
  인자는 JSON 스키마로 만듭니다. 문자열 query/question/topic 등에는 질문 원문, 숫자에는 질문 속 숫자를 순서대로 넣고,
  city에는 질문 속 도시(없으면 "서울"), bool에는 True를 넣습니다.
- 도구 결과가 이미 있으면 `"[mock:모델] 도구 실행 결과를 바탕으로…"` 형태의 텍스트로 답합니다.
- `with_structured_output(Schema)`는 스키마 기본값/더미값으로 채운 Pydantic 객체를 돌려줍니다.
  Literal/enum은 진행된 턴 수에 따라 FINISH 외의 옵션을 순환하며 고르고, 모두 돈 뒤에는 FINISH/END/done류를 고릅니다.
  첫 턴에서는 질문에 옵션 문자열이 들어 있으면 그 옵션을 고릅니다. score 같은 숫자 필드는 8, bool은 True입니다.
- 스트리밍(`.stream`, `stream_mode="messages"`)은 토큰 단위로 나눠 내보냅니다. `usage_metadata`도 채웁니다.
- 따라서 **모든 루프에는 반드시 상한**을 둡니다(반복 카운터 또는 `recursion_limit`). 이것은 현업 베스트 프랙티스이기도 합니다.
- Mock 모드에서 출력 내용의 "지능"은 기대하지 마세요. 코드 구조와 흐름이 끝까지 동작하는지가 기준입니다.
- 원시 `openai` SDK 호출은 Mock 대상이 아닙니다. 실행 예제에서는 쓰지 말고, 필요하면 본문 코드블록으로만 보여주세요.

## 폴더 구조

```
frontend/content/learn/
  01-foundations/                 # 모듈 (번호-슬러그)
    _module.json                  # {"title": "...", "description": "...", "icon": "lucide 아이콘 이름"}
    01-what-is-an-agent/          # 강의 (번호-슬러그)
      lesson.md                   # 프론트매터 + 본문
      examples/01_basic.py        # 실행 가능한 예제 (1~3개, 이름순으로 IDE 탭)
      examples/02_advanced.py
      exercise.py                 # 실습 과제 (TODO 포함, 자가채점 assert)
      solution.py                 # 정답 (실행 시 모든 assert 통과 + "✅" 출력)
      quiz.json                   # 퀴즈 3~5문항
```

### lesson.md 프론트매터

```yaml
---
title: "LangGraph의 State와 Reducer"
summary: "한두 문장 요약"
duration: 25            # 분
level: 중급              # 입문 | 초급 | 중급 | 고급 | 전문가
tags: [langgraph, state, reducer]
requiresKey: false      # 실제 LLM 출력이 핵심이면 true (Mock에서도 실행은 되어야 함)
objectives:
  - 학습 목표 1
  - 학습 목표 2
---
```

### 본문 작성 원칙

- 한국어로 씁니다. 기술 용어는 영어를 병기합니다. 예: "상태(State)", "리듀서(Reducer)".
- 구성: **왜 필요한가 → 핵심 개념 → 동작 원리(다이어그램) → 코드 해설 → 현업 팁/안티패턴 → 정리**
- 분량: 강의당 본문 1,200~2,500 단어 수준으로 깊이 있게 씁니다. 개념 강의도 비유와 구체적인 예를 듭니다.
- 다이어그램은 ```` ```mermaid ```` 코드블록으로 그립니다(flowchart/sequenceDiagram). 노드 라벨에 따옴표와 괄호가 있으면 `["..."]`로 감쌉니다.
- 콜아웃은 GitHub alert 문법을 씁니다: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!IMPORTANT]`, `> [!CAUTION]`
- 본문 코드블록은 ```` ```python ```` 등 언어를 반드시 표시합니다.
- 오른쪽 IDE 예제를 가리킬 때는 "▶ 오른쪽 IDE의 `examples/01_basic.py`를 실행해 보세요"처럼 씁니다.
- "현업에서는"(In production) 섹션을 꼭 넣습니다. 비용, 지연, 관측성(LangSmith), 장애, 보안, 테스트 관점을 다룹니다.
- 정확하지 않은 사실(존재하지 않는 API, 가짜 벤치마크 수치)은 쓰지 않습니다.

### 코드 작성 원칙

- 각 예제는 **단독 실행 가능**합니다. 같은 강의 폴더의 다른 파일을 import할 수는 있습니다.
- 출력은 학습자가 흐름을 이해하도록 구분선, 단계 라벨, `pretty_print()` 등으로 읽기 좋게 만듭니다.
- 타입 힌트, docstring, 핵심 줄 주석(한국어)을 답니다. 현업 코드 스타일을 따릅니다.
- 네트워크가 필요한 외부 서비스(Tavily, Pinecone 클라우드, Postgres 등)는 실행 예제에 쓰지 않습니다.
  대신 인메모리 대체물(Qdrant `:memory:`, InMemoryVectorStore, InMemorySaver, SqliteSaver `:memory:`)을 쓰고,
  프로덕션 버전은 본문 코드블록으로 보여줍니다.
- 실행 시간은 예제당 30초 이내, 출력은 200줄 이내로 유지합니다.
- `exercise.py`: 맨 위 docstring에 과제 설명을 쓰고, `# TODO:` 빈칸을 둡니다. 맨 아래에는 결과를 검증하는 `assert`와
  `print("✅ 모든 테스트 통과!")`를 둡니다. assert는 Mock 모드에서도 통과할 수 있도록 **구조/흐름**을 검증합니다(LLM 텍스트 내용은 검증하지 않음).
- `solution.py`: exercise와 같은 파일에 빈칸이 모두 채워진 버전입니다.

### quiz.json

```json
[
  {"q": "질문", "options": ["A", "B", "C", "D"], "answer": 1, "explain": "해설"}
]
```

## 검증 (필수)

작성한 뒤 반드시 실행해 모든 항목이 ✅인지 확인하세요:

```bash
cd backend && uv run python scripts/check_content.py <모듈폴더명>
```

실패하면 고치고 다시 실행하세요. 개별 파일 디버깅:
`cd backend && AGENTLAB_MOCK=1 PYTHONPATH=sandbox:<lesson폴더> uv run python <파일>`
