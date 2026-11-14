"""샌드박스 러너: 실행 결과, 시간·출력 상한, 경로·환경변수 격리."""

import os
import time

import pytest
from helpers import collect

from app import runner
from app.runner import RunError


async def test_runs_and_reports_exit_code():
    r = await collect({"main.py": "print('hello')\n"})
    assert r["start"]["mock"] is True  # 키가 없으면 Mock 모드
    assert r["stdout"] == "hello\n"
    assert r["exit"]["code"] == 0
    assert r["exit"]["timed_out"] is False


async def test_nonzero_exit_and_traceback_paths_are_relative():
    r = await collect({"main.py": "raise ValueError('boom')\n"})
    assert r["exit"]["code"] == 1
    assert "ValueError: boom" in r["stderr"]
    assert "agentlab-" not in r["stderr"]  # 임시 디렉터리 절대경로를 노출하지 않는다


async def test_sibling_files_are_importable():
    r = await collect({"main.py": "from util import x\nprint(x)\n", "pkg/util.py": "", "util.py": "x = 42\n"})
    assert r["stdout"].strip() == "42"


async def test_timeout_kills_process_group():
    started = time.perf_counter()
    r = await collect({"main.py": "import time\nprint('start', flush=True)\ntime.sleep(30)\n"}, timeout=1)
    assert time.perf_counter() - started < 10
    assert r["exit"]["timed_out"] is True
    assert "초과하여 중단" in r["stderr"]


async def test_output_is_capped(monkeypatch):
    monkeypatch.setattr(runner, "MAX_OUTPUT", 2000)
    r = await collect({"main.py": "print('x' * 100_000)\n"})
    assert len(r["stdout"]) <= 2000
    assert "출력이 너무 길어 잘렸습니다" in r["stderr"]


async def test_server_secrets_are_not_inherited(monkeypatch):
    monkeypatch.setenv("SERVER_ONLY_SECRET", "top-secret")
    r = await collect({"main.py": "import os\nprint(sorted(os.environ))\nprint(os.environ.get('SERVER_ONLY_SECRET'))\n"})
    assert "top-secret" not in r["stdout"]
    assert "SERVER_ONLY_SECRET" not in r["stdout"]


async def test_stdin_is_passed():
    r = await collect({"main.py": "print(input().upper())\n"}, stdin="abc\n")
    assert r["stdout"].strip() == "ABC"


@pytest.mark.parametrize("path", ["../escape.py", "a/../../b.py", "../../tmp/x.py"])
async def test_path_traversal_is_rejected(path):
    with pytest.raises(RunError):
        await collect({"main.py": "print(1)", path: "x"})


async def test_absolute_paths_stay_inside_workdir():
    # 앞의 / 는 떼고 작업 디렉터리 안에 만든다 (호스트의 /etc 를 건드리지 않는다)
    r = await collect({"main.py": "import os\nprint(os.path.exists('etc/agentlab-test'))\n", "/etc/agentlab-test": "x"})
    assert r["stdout"].strip() == "True"
    assert not os.path.exists("/etc/agentlab-test")


async def test_missing_entry_is_rejected():
    with pytest.raises(RunError):
        await collect({"other.py": "print(1)"})


async def test_too_many_or_too_large_files_are_rejected():
    with pytest.raises(RunError):
        await collect({f"f{i}.py": "" for i in range(runner.MAX_FILES + 1)} | {"main.py": ""})
    with pytest.raises(RunError):
        await collect({"main.py": "#" * (runner.MAX_FILE_BYTES + 1)})


async def test_workdir_is_removed_after_run():
    r = await collect({"main.py": "import os\nprint(os.getcwd())\n"})
    assert not os.path.exists(r["stdout"].strip())


async def test_default_limits_allow_many_threads():
    # 회귀: RLIMIT_AS 1GB 에서는 LangGraph 스레드 풀(최대 32개)이 스레드를 만들지 못해 멀티 에이전트 예제가 실패했다
    code = (
        "import threading, time, langgraph.graph, langchain_openai\n"
        "ts = [threading.Thread(target=time.sleep, args=(0.5,)) for _ in range(32)]\n"
        "[t.start() for t in ts]\n[t.join() for t in ts]\nprint('ok')\n"
    )
    r = await collect({"main.py": code})
    assert r["stdout"].strip() == "ok", r["stderr"]
