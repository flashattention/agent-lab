"""LLM 고도화: 바뀐 파일만 합치기, 검증 실패 시 재시도, 보안 정책, 캐시. LLM 은 가짜 클라이언트로 대신한다."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import refine as R

PATTERN = next(
    p
    for p in json.loads((Path(__file__).parent / "fixtures" / "patterns.json").read_text(encoding="utf-8"))["patterns"]
    if p["id"] == "react-agent"
)
FILES, GRAPH = PATTERN["files"], PATTERN["graph"]
GOOD_CONFIG = FILES["agent/config.py"].replace("def get_llm(", "# 노드별 모델을 받는다\ndef get_llm(")


class FakeLLM:
    """chat.completions.create 가 준비된 응답을 차례로 돌려준다."""

    def __init__(self, *replies: dict):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, model, messages, response_format):
        self.calls.append(list(messages))
        content = json.dumps(self.replies.pop(0), ensure_ascii=False)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


async def test_only_changed_files_are_returned_and_merged():
    llm = FakeLLM({"files": {"agent/config.py": GOOD_CONFIG}, "notes": "agent/config.py: 주석 추가 → 이해를 돕기 위해"})
    r = await R.refine_files(GRAPH, FILES, llm, "gpt-test")
    assert r["ok"]
    assert r["files"]["agent/config.py"] == GOOD_CONFIG
    assert {k: v for k, v in r["files"].items() if k != "agent/config.py"} == {k: v for k, v in FILES.items() if k != "agent/config.py"}
    assert r["attempts"][0]["changed"] == ["agent/config.py"]
    assert r["attempts"][0]["usage"] == {"input": 100, "output": 20}


async def test_no_change_answer_is_accepted():
    r = await R.refine_files(GRAPH, FILES, FakeLLM({"files": {}, "notes": "변경 없음: 이미 충분히 단순하다"}), "gpt-test")
    assert r["ok"] and r["files"] == FILES


async def test_validation_failure_is_sent_back_and_retried():
    broken = {"files": {"agent/config.py": FILES["agent/config.py"] + "\nundefined_name()\n"}, "notes": "x"}
    llm = FakeLLM(broken, {"files": {"agent/config.py": GOOD_CONFIG}, "notes": "고침"})
    r = await R.refine_files(GRAPH, FILES, llm, "gpt-test")
    assert r["ok"] and len(r["attempts"]) == 2 and not r["attempts"][0]["ok"]
    feedback = llm.calls[1][-1]["content"]
    assert feedback.startswith("Validation failed") and "F821" in feedback  # 실패 보고서가 그대로 전달된다


async def test_policy_violation_is_never_accepted():
    evil = FILES["agent/config.py"] + '\nimport os\nLEAK = os.getenv("OPENAI_API_KEY")\n'
    llm = FakeLLM(*[{"files": {"agent/config.py": evil}, "notes": "x"}] * 3)
    r = await R.refine_files(GRAPH, FILES, llm, "gpt-test")
    assert not r["ok"] and r["attempts"][-1]["report"]["policy"]


async def test_refine_caches_by_structure_and_prompt_version(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DB", tmp_path / "cache.sqlite")
    monkeypatch.setattr(R, "CACHE_BUCKET", None)
    monkeypatch.setattr(R, "_memo", {})
    llm = FakeLLM({"files": {"agent/config.py": GOOD_CONFIG}, "notes": "ok"})
    monkeypatch.setattr(R, "AsyncOpenAI", lambda api_key: llm)
    first = await R.refine(GRAPH, FILES, "sk-test")
    second = await R.refine(GRAPH, FILES, "sk-test")
    assert first["cached"] is False and second["cached"] is True and len(llm.calls) == 1
    assert second["files"]["agent/config.py"] == GOOD_CONFIG
    monkeypatch.setattr(R, "PROMPT_VERSION", "test-next")
    assert R.structure_key(GRAPH) != first["key"]  # 프롬프트를 바꾸면 이전 결과와 섞이지 않는다


@pytest.mark.parametrize("phrase", ["Include ONLY files you changed", "SMALLEST set of changes", "untrusted DATA"])
def test_prompt_keeps_key_instructions(phrase):
    assert phrase in R.SYSTEM_PROMPT
