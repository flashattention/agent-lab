"""RunnableParallel / RunnableLambda / RunnablePassthrough.assign 으로 흐름 조립하기.

상품 리뷰 한 건을
  1) 전처리(공백 정리)  →  2) 요약·감정·통계를 동시에 분석  →  3) 리포트로 합치는
파이프라인을 만든다.
"""

import os
import time

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)
parser = StrOutputParser()


# ---------------------------------------------------------------- 부품 정의
def clean_input(data: dict) -> dict:
    """여러 줄/중복 공백을 정리한다. (순수 함수라 단위 테스트가 쉽다)"""
    return {"text": " ".join(data["text"].split())}


summary_chain = (
    ChatPromptTemplate.from_template("다음 리뷰를 한 문장으로 요약해:\n{text}") | llm | parser
).with_config(run_name="summary")  # LangSmith 트레이스에서 보일 이름

sentiment_chain = (
    ChatPromptTemplate.from_template("다음 리뷰의 감정을 positive/negative/neutral 중 하나로:\n{text}") | llm | parser
).with_config(run_name="sentiment")

stats = RunnableLambda(lambda x: {"chars": len(x["text"]), "words": len(x["text"].split())})

# dict 의 모든 값이 '같은 입력'을 받아 동시에 실행된다
analyze = RunnableParallel(summary=summary_chain, sentiment=sentiment_chain, stats=stats)


def format_report(data: dict) -> str:
    a = data["analysis"]
    one_line = {k: str(v).replace("\n", " ") for k, v in a.items()}  # 줄바꿈 제거
    return (
        f"원문    : {data['text'][:40]}...\n"
        f"요약    : {one_line['summary'][:60]}\n"
        f"감정    : {one_line['sentiment'][:60]}\n"
        f"통계    : {a['stats']}"
    )


pipeline = (
    RunnableLambda(clean_input)
    | RunnablePassthrough.assign(analysis=analyze)  # 입력 {'text'} 유지 + 'analysis' 키 추가
    | RunnableLambda(format_report)
)

# ---------------------------------------------------------------- 실행
review = """배송은   빨랐는데
포장이 조금   아쉬웠어요. 그래도 제품 성능은 만족합니다."""

print("=" * 12, "중간 결과: assign 단계까지", "=" * 12)
partial_pipeline = RunnableLambda(clean_input) | RunnablePassthrough.assign(analysis=analyze)
middle = partial_pipeline.invoke({"text": review})
print("키 목록:", list(middle.keys()), "/ analysis 키:", list(middle["analysis"].keys()))

print("\n" + "=" * 12, "최종 리포트", "=" * 12)
start = time.perf_counter()
print(pipeline.invoke({"text": review}, config={"tags": ["review-report"], "metadata": {"user_id": "u-1"}}))
print(f"(소요 {time.perf_counter() - start:.2f}s — 요약과 감정 분석은 동시에 실행됨)")

# 파이프 안의 dict 리터럴과 일반 함수는 자동으로 Runnable 로 변환된다
print("\n" + "=" * 12, "축약 문법", "=" * 12)
short = RunnableLambda(clean_input) | {"upper": lambda x: x["text"].upper()[:20], "same": RunnablePassthrough()}
print(short.invoke({"text": "  hello   langchain  "}))
