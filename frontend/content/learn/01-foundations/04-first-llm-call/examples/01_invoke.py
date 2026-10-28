"""첫 LLM 호출: init_chat_model + invoke, 그리고 응답(AIMessage) 해부.

API 키가 없으면 Mock 모델이 응답한다. 키를 넣으면 같은 코드로 실제 모델이 응답한다.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage

# 모델 ID는 항상 환경변수에서 읽는다 (설정 패널에서 바꿀 수 있도록). "제공자:모델명" 형식.
MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def section(title: str) -> None:
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


if __name__ == "__main__":
    # timeout / max_retries 는 현업에서 사실상 필수 설정이다 (기본값에 기대지 말 것)
    llm = init_chat_model(MODEL, timeout=30, max_retries=2)
    print("모델 클래스:", type(llm).__name__, "| 모델:", MODEL)

    section("1) 가장 단순한 호출: 문자열 하나")
    reply = llm.invoke("에이전트를 한 문장으로 정의해줘.")
    print(reply.text)

    section("2) 메시지 리스트로 호출 (system + human)")
    reply = llm.invoke(
        [
            SystemMessage("너는 AI 엔지니어링 튜터야. 초보자 눈높이로 두 문장 이내로 답해."),
            HumanMessage("토큰이 뭐야?"),
        ]
    )
    reply.pretty_print()

    section("3) 같은 내용을 튜플 / 딕셔너리 형식으로")
    # LangChain 은 (role, content) 튜플과 OpenAI 스타일 dict 도 메시지로 받아 준다
    llm.invoke([("system", "짧게 답해."), ("human", "안녕?")]).pretty_print()
    llm.invoke([{"role": "user", "content": "LangGraph가 뭐야?"}]).pretty_print()

    section("4) 응답 객체(AIMessage) 해부")
    print("type              :", reply.type)  # "ai"
    print("text              :", reply.text[:60], "...")  # 텍스트만 꺼낸 편의 속성
    print("content           :", type(reply.content).__name__)  # str 또는 콘텐츠 블록 list (→ 2.1)
    print("id                :", reply.id)
    print("usage_metadata    :", reply.usage_metadata)  # 토큰 사용량 (비용 계산의 근거)
    print("response_metadata :", reply.response_metadata)  # 모델명, 종료 사유 등 제공자 정보
    print("tool_calls        :", reply.tool_calls)  # 도구 호출 요청 (→ 2.4)

    section("5) config: 태그/메타데이터/실행 이름 (트레이싱에서 검색·필터용)")
    reply = llm.invoke(
        "안녕!",
        config={"run_name": "greeting", "tags": ["lesson-1.4"], "metadata": {"user_id": "u-123"}},
    )
    print("✅ config 와 함께 호출 완료 →", reply.text[:50])
