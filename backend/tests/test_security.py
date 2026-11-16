"""보안: 샌드박스 egress·프로세스 정책(sandbox/agentlab_guard.py)과 고도화 코드 정책(app/policy.py)."""

import json
from pathlib import Path

import pytest
from helpers import collect

from app.policy import check_files
from app.runner import RunError
from app.runner import check_files as check_upload

PATTERNS = json.loads((Path(__file__).parent / "fixtures" / "patterns.json").read_text(encoding="utf-8"))["patterns"]

PROBE = r"""
import socket, subprocess, sys, os

def t(name, fn):
    try:
        fn()
        print(name, "ALLOWED")
    except PermissionError:
        print(name, "BLOCKED")
    except OSError as e:  # 정책은 통과했지만 연결 자체가 실패한 경우
        print(name, "ALLOWED", type(e).__name__)

t("dns", lambda: socket.getaddrinfo("example.com", 443))
t("ip", lambda: socket.create_connection(("93.184.215.14", 443), timeout=2))
t("metadata", lambda: socket.create_connection(("169.254.169.254", 80), timeout=2))
t("curl", lambda: subprocess.run(["curl", "-s", "https://example.com"], timeout=5))
t("system", lambda: os.system("true"))
child = "import socket\ntry:\n socket.getaddrinfo('example.com', 443); print('ALLOWED')\nexcept PermissionError: print('BLOCKED')"
r = subprocess.run([sys.executable, "-I", "-c", child], env={}, capture_output=True, text=True, timeout=30)
print("child", r.stdout.strip())
"""


def _results(stdout: str) -> dict[str, str]:
    out = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


async def test_guard_blocks_network_and_processes_in_mock_mode():
    r = await collect({"main.py": PROBE}, timeout=60)
    assert r["exit"]["code"] == 0, r["stderr"]
    got = _results(r["stdout"])
    assert got == {k: "BLOCKED" for k in ("dns", "ip", "metadata", "curl", "system", "child")}, got


async def test_guard_allows_only_the_key_proxy_with_a_key():
    code = (
        PROBE
        + r"""
from urllib.parse import urlparse
u = urlparse(os.environ["OPENAI_BASE_URL"])
t("proxy", lambda: socket.create_connection((u.hostname, u.port), timeout=2).close())
"""
    )
    r = await collect({"main.py": code}, api_key="sk-test-not-real", timeout=60)
    assert r["exit"]["code"] == 0, r["stderr"]
    got = _results(r["stdout"])
    assert got.pop("proxy") == "ALLOWED"
    assert got == {k: "BLOCKED" for k in ("dns", "ip", "metadata", "curl", "system", "child")}, got


def test_policy_accepts_every_generated_pattern():
    for p in PATTERNS:
        assert check_files(p["files"]) == [], p["id"]


@pytest.mark.parametrize(
    "source",
    [
        "import requests\n",
        "from subprocess import run\n",
        "import importlib\n",
        "import os\nos.environ.get('OPENAI_API_KEY')\n",
        "import os\nos.getenv('MY_TOKEN')\n",
        "import os\nprint(dict(os.environ))\n",
        "import os\nos.system('id')\n",
        "eval('1')\n",
        "open('/etc/passwd')\n",
        "().__class__.__bases__[0].__subclasses__()\n",
        "getattr(object, name)\n",
    ],
)
def test_policy_rejects_dangerous_code(source):
    assert check_files({"agent/x.py": source}), source


def test_pytest_is_allowed_only_under_tests():
    assert check_files({"tests/test_graph.py": "import pytest\n"}) == []
    assert check_files({"agent/x.py": "import pytest\n"})


def test_upload_limits():
    with pytest.raises(RunError):
        check_upload({f"f{i}.py": "" for i in range(10_000)})
    with pytest.raises(RunError):
        check_upload({"a.py": "x" * 300_000})
    with pytest.raises(RunError):
        check_upload({"main.py": ""}, entry="missing.py")
