"""실습: 프롬프트 템플릿 + LCEL + 장애 대비

고객 문의를 처리하는 작은 파이프라인을 완성하세요.

1. inquiry_prompt
   - system: "너는 {shop} 고객센터 상담원이다."
   - human : "{question}"
   형태의 ChatPromptTemplate 을 만드세요. (input_variables 는 shop, question)
2. # TODO: inquiry_prompt, llm, StrOutputParser() 를 | 로 연결하세요.
answer_chain = RunnableLambda(lambda x: "")
3. analyze = RunnableParallel(
       answer=answer_chain,
       category=<RunnableLambda: question 에 '환불'이 있으면 'refund', 아니면 'general'>,
   )
4. unstable_lookup 함수는 처음 2번 ConnectionError 를 냅니다.
   with_retry 로 감싸 3번째에 성공하게 만드세요. (ConnectionError 만 재시도, 대기 없음)
5. broken 은 항상 실패합니다. with_fallbacks 로 safe_reply 로 넘어가게 하세요.
"""

import os

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)

# 1. 프롬프트 템플릿
# TODO: ("system", ...), ("human", ...) 두 메시지로 ChatPromptTemplate 을 만드세요.
inquiry_prompt = ChatPromptTemplate.from_messages([("human", "TODO")])

# 2. LCEL 체인
# TODO: inquiry_prompt, llm, StrOutputParser() 를 | 로 연결하세요.
answer_chain = RunnableLambda(lambda x: "")


# 3. 병렬 분석
def categorize(data: dict) -> str:
    # TODO: question 에 '환불'이 있으면 'refund', 아니면 'general'
    return ""


# TODO: answer=answer_chain, category=RunnableLambda(categorize) 로 RunnableParallel 을 만드세요.
analyze = RunnableParallel(answer=answer_chain)

# 4. 재시도
attempts = {"n": 0}


def unstable_lookup(order_id: str) -> str:
    attempts["n"] += 1
    if attempts["n"] < 3:
        raise ConnectionError("timeout")
    return f"{order_id}: 배송 중"


# TODO: .with_retry(...) 로 ConnectionError 만 최대 3번, 대기 없이 재시도하게 하세요.
robust_lookup = RunnableLambda(unstable_lookup)

# 5. 폴백
def always_fail(_: str) -> str:
    raise RuntimeError("model down")


broken = RunnableLambda(always_fail)
safe_reply = RunnableLambda(lambda _: "잠시 후 다시 시도해 주세요.")
# TODO: broken 이 실패하면 safe_reply 로 넘어가도록 with_fallbacks 를 쓰세요.
safe_chain = broken

# ------------------------------------------------------------------ 실행
inputs = [
    {"shop": "AgentMall", "question": "환불은 언제 되나요?"},
    {"shop": "AgentMall", "question": "영업시간 알려주세요"},
]
results = analyze.batch(inputs, config={"max_concurrency": 2})
for r in results:
    print(f"[{r.get('category')}] {r['answer'][:60]}")
try:
    lookup = robust_lookup.invoke("ORD-77")
except ConnectionError as e:
    lookup = None
    print("조회 실패 (재시도가 설정되지 않았나요?):", e)
print("조회:", lookup, f"(시도 {attempts['n']}회)")
try:
    fallback_answer = safe_chain.invoke("hi")
except RuntimeError as e:
    fallback_answer = None
    print("폴백 실패 (with_fallbacks 를 설정했나요?):", e)
print("폴백:", fallback_answer)

# ------------------------------------------------------------------ 자가 채점
assert sorted(inquiry_prompt.input_variables) == ["question", "shop"], "프롬프트 변수는 shop, question 이어야 합니다"
assert len(inquiry_prompt.invoke(inputs[0]).to_messages()) == 2, "system + human 두 메시지여야 합니다"
assert all(isinstance(r["answer"], str) and r["answer"] for r in results), "answer 는 비어있지 않은 문자열이어야 합니다"
assert [r["category"] for r in results] == ["refund", "general"], "category 분류가 올바르지 않습니다"
assert lookup == "ORD-77: 배송 중" and attempts["n"] == 3, "3번째 시도에서 성공해야 합니다"
assert fallback_answer == "잠시 후 다시 시도해 주세요.", "폴백 응답이 나와야 합니다"
print("✅ 모든 테스트 통과!")
