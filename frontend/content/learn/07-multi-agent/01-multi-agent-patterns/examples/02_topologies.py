"""멀티 에이전트 토폴로지 3종을 LLM 없이 '뼈대'만으로 비교한다.

- Supervisor  : 중앙 관리자가 매번 다음 작업자를 고른다 (별 모양)
- Network     : 각 에이전트가 직접 다음 에이전트를 고른다 (그물 모양)
- Hierarchical: 관리자 밑에 팀(서브그래프)이 있고, 팀 안에 다시 관리자가 있다

LLM 대신 정해진 규칙으로 라우팅하므로 결과가 항상 같다. 구조와 흐름에 집중하자.
"""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class State(TypedDict):
    trace: Annotated[list[str], operator.add]  # 방문 기록 (리듀서로 누적)
    steps: int  # 전체 단계 수 (무한 루프 방지용)


MAX_STEPS = 6


# ---------------------------------------------------------------------------
# 1) Supervisor 토폴로지
# ---------------------------------------------------------------------------
def supervisor(state: State) -> Command[Literal["researcher", "writer", "__end__"]]:
    done = set(state["trace"])
    if state["steps"] >= MAX_STEPS:  # 안전장치
        return Command(goto=END)
    if "researcher" not in done:
        nxt = "researcher"
    elif "writer" not in done:
        nxt = "writer"
    else:
        nxt = END
    return Command(goto=nxt, update={"steps": state["steps"] + 1})


def make_worker(name: str):
    def worker(state: State) -> Command[Literal["supervisor"]]:
        # 작업자는 일을 마치면 항상 관리자에게 돌아간다
        return Command(goto="supervisor", update={"trace": [name]})

    return worker


sup = StateGraph(State)
sup.add_node("supervisor", supervisor)
sup.add_node("researcher", make_worker("researcher"))
sup.add_node("writer", make_worker("writer"))
sup.add_edge(START, "supervisor")
supervisor_graph = sup.compile()


# ---------------------------------------------------------------------------
# 2) Network 토폴로지: 관리자 없이 서로 직접 넘긴다
# ---------------------------------------------------------------------------
def researcher_net(state: State) -> Command[Literal["writer", "reviewer", "__end__"]]:
    if state["steps"] >= MAX_STEPS:
        return Command(goto=END)
    return Command(goto="writer", update={"trace": ["researcher"], "steps": state["steps"] + 1})


def writer_net(state: State) -> Command[Literal["researcher", "reviewer", "__end__"]]:
    if state["steps"] >= MAX_STEPS:
        return Command(goto=END)
    return Command(goto="reviewer", update={"trace": ["writer"], "steps": state["steps"] + 1})


def reviewer_net(state: State) -> Command[Literal["researcher", "writer", "__end__"]]:
    if state["steps"] >= MAX_STEPS:
        return Command(goto=END)
    # 한 번 반려(writer로 되돌림)하고, 두 번째에는 승인
    rejected_before = state["trace"].count("reviewer") >= 1
    nxt = END if rejected_before else "writer"
    return Command(goto=nxt, update={"trace": ["reviewer"], "steps": state["steps"] + 1})


net = StateGraph(State)
net.add_node("researcher", researcher_net)
net.add_node("writer", writer_net)
net.add_node("reviewer", reviewer_net)
net.add_edge(START, "researcher")
network_graph = net.compile()


# ---------------------------------------------------------------------------
# 3) Hierarchical 토폴로지: 팀(서브그래프)을 노드로 넣는다
# ---------------------------------------------------------------------------
def team_lead(state: State) -> Command[Literal["analyst", "__end__"]]:
    if "analyst" in state["trace"]:
        return Command(goto=END)
    return Command(goto="analyst", update={"trace": ["team_lead"]})


def analyst(state: State) -> Command[Literal["team_lead"]]:
    return Command(goto="team_lead", update={"trace": ["analyst"]})


team = StateGraph(State)
team.add_node("team_lead", team_lead)
team.add_node("analyst", analyst)
team.add_edge(START, "team_lead")
research_team = team.compile()


def call_research_team(state: State) -> dict:
    """팀(서브그래프)을 '새 상태'로 실행하고, 결과 중 필요한 것만 부모에게 돌려준다.

    컴파일된 그래프를 add_node에 그대로 넣을 수도 있지만, 그러면 부모의 trace 전체가
    서브그래프로 들어갔다가 리듀서(operator.add)에 의해 '한 번 더' 더해져 중복된다.
    부모-자식 사이의 상태 경계를 함수로 명확히 정하는 것이 현업에서 더 안전하다.
    """
    out = research_team.invoke({"trace": [], "steps": 0}, {"recursion_limit": 10})
    return {"trace": out["trace"]}


def top_manager(state: State) -> Command[Literal["research_team", "__end__"]]:
    if "analyst" in state["trace"]:  # 팀이 일을 마쳤으면 종료
        return Command(goto=END)
    return Command(goto="research_team", update={"trace": ["top_manager"]})


top = StateGraph(State)
top.add_node("top_manager", top_manager)
top.add_node("research_team", call_research_team)
top.add_edge(START, "top_manager")
top.add_edge("research_team", "top_manager")
hierarchical_graph = top.compile()


if __name__ == "__main__":
    for title, graph in [
        ("Supervisor", supervisor_graph),
        ("Network", network_graph),
        ("Hierarchical", hierarchical_graph),
    ]:
        out = graph.invoke({"trace": [], "steps": 0}, {"recursion_limit": 25})
        print("=" * 60)
        print(f"[{title}] 실행 순서: {' → '.join(out['trace'])}")
        print("-" * 60)
        print(graph.get_graph().draw_mermaid().strip())
    print("=" * 60)
    print("세 그래프 모두 상한(MAX_STEPS / recursion_limit) 안에서 종료되었습니다.")
