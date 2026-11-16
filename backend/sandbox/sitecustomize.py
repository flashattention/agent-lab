"""AgentLab 실행 샌드박스 부트스트랩 (AGENTLAB_MOCK=1 일 때만 활성화)."""

import os
import sys

# 보안 정책: 보통은 site-packages 의 .pth 로 먼저 설치되지만, 없을 때를 대비해 여기서도 건다.
try:
    import agentlab_guard  # noqa: F401  (import 시 install)
except Exception as exc:  # pragma: no cover
    sys.stderr.write(f"[AgentLab] 보안 정책 설치 실패: {exc}\n")

if os.environ.get("AGENTLAB_MOCK") == "1":
    try:
        import agentlab_mock

        agentlab_mock.install()
        sys.stderr.write("[AgentLab] OPENAI_API_KEY 없음 → Mock LLM 모드로 실행합니다.\n")
        sys.stderr.flush()
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"[AgentLab] mock 설치 실패: {exc}\n")
