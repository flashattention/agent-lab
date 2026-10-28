"""AgentLab 실행 샌드박스 부트스트랩 (AGENTLAB_MOCK=1 일 때만 활성화)."""

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
