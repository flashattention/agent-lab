"""실행 트레이서: LangGraph 실행을 사용자 코드 수정 없이 트리 이벤트로 수집한다."""

import agentlab_trace as tr
from helpers import REACT_AGENT, collect


async def test_react_agent_trace_tree():
    r = await collect({"main.py": REACT_AGENT}, timeout=60)
    assert r["exit"]["code"] == 0, r["stderr"]
    starts = [e for e in r["trace"] if e["ev"] == "start"]
    ends = {e["id"]: e for e in r["trace"] if e["ev"] == "end"}
    by_id = {e["id"]: e for e in starts}

    # 모든 부모가 존재하고, 루트는 그래프 하나
    roots = [e for e in starts if e["parent"] is None]
    assert len(roots) == 1 and roots[0]["kind"] == "graph"
    assert all(e["parent"] in by_id for e in starts if e["parent"])

    # 노드 실행 순서: agent → tools → agent
    nodes = [e for e in starts if e["kind"] == "node"]
    assert [n["name"] for n in nodes] == ["agent", "tools", "agent"]
    assert [n["meta"]["langgraph_step"] for n in nodes] == [1, 2, 3]
    assert all(by_id[n["parent"]]["kind"] == "graph" for n in nodes)

    # LangGraph 내부 실행 단위(ChannelWrite 등)는 보이지 않는다
    assert not any(e["name"].startswith(("ChannelWrite", "_write", "Branch")) for e in starts)

    # 노드 입력 State 와 반환값
    tools_node = nodes[1]
    assert tools_node["inputs"]["messages"][-1]["tool_calls"][0]["name"] == "get_weather"
    assert ends[tools_node["id"]]["outputs"]["messages"][0]["role"] == "tool"

    # LLM: tool_calls 와 토큰 사용량
    llms = [e for e in starts if e["kind"] == "llm"]
    assert len(llms) == 2
    first = ends[llms[0]["id"]]
    assert first["message"]["tool_calls"][0]["args"] == {"city": "서울"}
    assert first["usage"]["total"] > 0

    # 도구 인자와 결과
    tool = next(e for e in starts if e["kind"] == "tool")
    assert tool["name"] == "get_weather"
    assert "맑음" in str(ends[tool["id"]]["outputs"])

    # 모든 시작 이벤트가 끝났다
    assert set(by_id) == set(ends)


async def test_trace_does_not_pollute_stdout():
    r = await collect({"main.py": REACT_AGENT}, timeout=60)
    assert '"ev"' not in r["stdout"]
    assert "agentlab" not in r["stdout"].lower()


async def test_plain_python_has_no_trace():
    r = await collect({"main.py": "print(1 + 1)"})
    assert r["trace"] == []
    assert r["stdout"] == "2\n"


def test_serializer_truncates_large_values():
    long = "가" * (tr.MAX_STR + 500)
    out = tr._ser({"s": long, "items": list(range(tr.MAX_ITEMS + 10))})
    assert len(out["s"]) < len(long) and out["s"].endswith("(+500자)")
    assert len(out["items"]) == tr.MAX_ITEMS + 1 and str(out["items"][-1]).startswith("…")


def test_serializer_handles_messages_and_usage():
    from langchain_core.messages import AIMessage

    m = AIMessage(
        content="",
        tool_calls=[{"id": "c1", "name": "f", "args": {"a": 1}}],
        usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
    )
    d = tr._ser(m)
    assert d["role"] == "ai"
    assert d["tool_calls"] == [{"id": "c1", "name": "f", "args": {"a": 1}}]
    assert d["usage"] == {"input": 3, "output": 2, "total": 5}
