"""AgentLab 실행 샌드박스 부트스트랩.

- AGENTLAB_MOCK=1 이면 Mock LLM 을 설치한다.
- AGENTLAB_TRACE_FD 가 있으면 LangChain/LangGraph 실행 트레이서를 등록한다.
"""

import os
import sys

if os.environ.get("AGENTLAB_MOCK") == "1":
    try:
        import agentlab_mock

        agentlab_mock.install()
        sys.stderr.write("[AgentLab] OPENAI_API_KEY 없음 → Mock LLM 모드로 실행합니다.\n")
        sys.stderr.flush()
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"[AgentLab] mock 설치 실패: {exc}\n")

if os.environ.get("AGENTLAB_TRACE_FD"):
    try:
        import agentlab_trace

        agentlab_trace.install()
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"[AgentLab] 트레이서 설치 실패: {exc}\n")
