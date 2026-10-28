"""실습: LLM 호출 유틸리티 4종 만들기

1. make_llm()                    : 환경변수 모델 ID로 timeout=30, max_retries=2 를 준 채팅 모델 생성
2. ask(llm, question, system)    : system + human 메시지로 호출하고
                                   {"text": str, "input_tokens": int, "output_tokens": int} 반환
3. stream_answer(llm, question)  : stream 으로 받은 청크를 + 로 합쳐 (청크 수, 전체 텍스트) 반환
4. ask_many(llm, questions)      : batch(max_concurrency=2, return_exceptions=True)로 호출하고
                                   성공은 텍스트, 실패는 "[error] 예외이름" 문자열로 바꾼 리스트 반환

힌트: examples/01_invoke.py, examples/02_stream_and_batch.py, examples/03_errors_and_retry.py
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model  # noqa: F401 (TODO에서 사용)
from langchain.messages import HumanMessage, SystemMessage  # noqa: F401 (TODO에서 사용)

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")


def make_llm():
    # TODO: init_chat_model 로 MODEL 을 초기화하세요. timeout=30, max_retries=2 를 함께 넘깁니다.
    return None


def ask(llm, question: str, system: str = "너는 간결하게 답하는 도우미야.") -> dict:
    # TODO: [SystemMessage(system), HumanMessage(question)] 으로 llm.invoke 하고,
    #       reply.text 와 reply.usage_metadata 의 input_tokens / output_tokens 를 담아 return 하세요.
    return {"text": "", "input_tokens": 0, "output_tokens": 0}


def stream_answer(llm, question: str) -> tuple[int, str]:
    count = 0
    full = None
    # TODO: llm.stream(question) 을 돌며 count 를 1씩 늘리고, 청크를 full 에 + 로 누적하세요.
    return count, (full.text if full is not None else "")


def ask_many(llm, questions: list[str]) -> list[str]:
    # TODO: llm.batch(questions, config={"max_concurrency": 2}, return_exceptions=True) 로 호출하고
    #       예외면 f"[error] {type(r).__name__}", 아니면 r.text 로 바꾼 리스트를 return 하세요.
    return []


if __name__ == "__main__":
    llm = make_llm()
    assert llm is not None and hasattr(llm, "invoke"), "make_llm 이 채팅 모델을 돌려줘야 합니다"

    r = ask(llm, "LangChain이 뭐야?")
    print("ask:", r)

    n, text = stream_answer(llm, "스트리밍 테스트")
    print(f"stream: {n}개 청크 → {text[:50]}")

    answers = ask_many(llm, ["질문1", "질문2", "질문3"])
    print("batch:", [a[:30] for a in answers])

    # --- 자가 채점 ---
    assert set(r) == {"text", "input_tokens", "output_tokens"}
    assert isinstance(r["text"], str) and r["text"], "응답 텍스트가 비어 있습니다"
    assert r["input_tokens"] > 0 and r["output_tokens"] > 0, "usage_metadata 에서 토큰 수를 읽어야 합니다"
    assert n >= 1 and isinstance(text, str) and text, "스트림 청크를 합쳐야 합니다"
    assert len(answers) == 3 and all(isinstance(a, str) and a for a in answers)
    print("✅ 모든 테스트 통과!")
