"""Reflection: 작성자(generator)와 비평가(reflector)가 번갈아 초안을 다듬는다

흐름
  START → generate → reflect → generate → reflect → … (MAX_ROUNDS) → END

핵심 트릭
- 비평은 작성자 입장에서 '사람(HumanMessage)의 피드백'으로 넣는다.
  작성자는 피드백에 답하듯 다음 초안을 쓰게 된다(역할 뒤집기).
- 반복 횟수 상한(MAX_ROUNDS)이 종료 조건이다. 비평가는 '평가'가 아니라 '조언'만 한다.
"""

import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
MAX_ROUNDS = 3  # 초안 작성 횟수 상한 (초안 1 + 개선 2)

llm = init_chat_model(MODEL)

WRITER_PROMPT = "당신은 기술 블로그 작가입니다. 요청에 맞는 3문장 이내의 글을 쓰세요. 피드백이 오면 반영해 전체를 다시 쓰세요."
CRITIC_PROMPT = (
    "당신은 깐깐한 편집자입니다. 아래 글의 문제점 2가지와 구체적인 개선 방법을 짧게 제시하세요. "
    "칭찬은 하지 말고, 글을 직접 고쳐 쓰지도 마세요."
)


class ReflectionState(MessagesState):
    rounds: int  # 지금까지 작성한 초안 수


def generate(state: ReflectionState) -> dict:
    draft = llm.invoke([SystemMessage(WRITER_PROMPT), *state["messages"]])
    rounds = state.get("rounds", 0) + 1
    print(f"\n[generate #{rounds}] {draft.text[:90]!r}")
    return {"messages": [AIMessage(draft.text, name="writer")], "rounds": rounds}


def reflect(state: ReflectionState) -> dict:
    request = state["messages"][0].text
    latest_draft = state["messages"][-1].text
    # 비평가는 대화 기록 전체가 아니라 '요청 + 최신 초안'만 본다 (짧은 컨텍스트)
    critique = llm.invoke([SystemMessage(CRITIC_PROMPT), HumanMessage(f"요청: {request}\n\n글:\n{latest_draft}")])
    print(f"[reflect ] {critique.text[:90]!r}")
    # 작성자에게는 '사람의 피드백'으로 전달
    return {"messages": [HumanMessage(f"편집자 피드백: {critique.text}", name="critic")]}


def should_continue(state: ReflectionState) -> Literal["reflect", "__end__"]:
    return END if state["rounds"] >= MAX_ROUNDS else "reflect"


builder = StateGraph(ReflectionState)
builder.add_node("generate", generate)
builder.add_node("reflect", reflect)
builder.add_edge(START, "generate")
builder.add_conditional_edges("generate", should_continue)
builder.add_edge("reflect", "generate")
graph = builder.compile()


if __name__ == "__main__":
    out = graph.invoke(
        {"messages": [HumanMessage("LangGraph 체크포인터가 왜 필요한지 초보자에게 설명하는 글")], "rounds": 0},
        {"recursion_limit": 2 * MAX_ROUNDS + 3},  # 그래프 단계 수로 계산한 상한
    )
    print("\n" + "=" * 60)
    print(f"초안 작성 {out['rounds']}회, 메시지 {len(out['messages'])}개")
    for m in out["messages"]:
        print(f"  - {m.name or 'user':7} | {m.text[:60].replace(chr(10), ' ')}")
