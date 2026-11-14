"""테스트 공통 설정.

개발 PC·CI 에서는 같은 계정의 스레드 수가 많아 RLIMIT_NPROC(기본 256)에 걸릴 수 있으므로 끈다.
(운영 컨테이너에서는 기본값을 그대로 쓴다.)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("AGENTLAB_NPROC_LIMIT", "0")
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_ANON_KEY", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sandbox"))
