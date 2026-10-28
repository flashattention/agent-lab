"""프롬프트 템플릿과 LCEL 기본.

- ChatPromptTemplate + MessagesPlaceholder 로 프롬프트 양식 만들기
- partial 로 변수 일부 고정하기
- prompt | llm | StrOutputParser 체인을 invoke / batch / stream / ainvoke 로 호출하기
"""

import asyncio
import os

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 템플릿
section("1. 프롬프트 템플릿")
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "너는 {company}의 상담원이다. {tone} 말투로 두 문장 이내로 답한다."),
        MessagesPlaceholder("history"),  # 대화 기록 리스트가 통째로 들어갈 자리
        ("human", "{question}"),
    ]
)
print("필요한 변수:", prompt.input_variables)

# 배포 시점에 정해지는 값은 partial 로 미리 고정
shop_prompt = prompt.partial(company="AgentMall", tone="공손한")
print("partial 후 남은 변수:", shop_prompt.input_variables)

rendered = shop_prompt.invoke(
    {
        "history": [HumanMessage("안녕하세요"), AIMessage("안녕하세요! 무엇을 도와드릴까요?")],
        "question": "주문한 노트북은 언제 도착하나요?",
    }
)
for m in rendered.to_messages():
    print(f"  [{m.type}] {m.content}")

# 변수를 빠뜨리면 조용히 넘어가지 않고 즉시 에러가 난다
try:
    shop_prompt.invoke({"question": "history를 빠뜨림"})
except KeyError as e:
    print("변수 누락 → KeyError:", e)

# ---------------------------------------------------------------- 2. LCEL 체인
section("2. LCEL 체인: prompt | llm | parser")
chain = shop_prompt | llm | StrOutputParser()
print("체인 타입:", type(chain).__name__)

answer = chain.invoke({"history": [], "question": "환불은 며칠 걸리나요?"})
print("invoke → str 인가?", isinstance(answer, str), "|", answer[:70])

# ---------------------------------------------------------------- 3. batch
section("3. batch: 여러 입력을 병렬로")
questions = ["배송비는 얼마인가요?", "교환은 어떻게 하나요?", "영업시간이 언제인가요?"]
answers = chain.batch(
    [{"history": [], "question": q} for q in questions],
    config={"max_concurrency": 2},  # rate limit 을 고려해 동시 요청 수 제한
)
for q, a in zip(questions, answers):
    print(f"  Q: {q}\n  A: {a[:50]}...")

# ---------------------------------------------------------------- 4. stream
section("4. stream: 조각 단위로 받기")
for i, piece in enumerate(chain.stream({"history": [], "question": "추천 상품 알려줘"})):
    print(f"[{i}]{piece}", end="|")
    if i >= 7:  # 출력이 길어지지 않게 앞부분만
        print(" ...")
        break


# ---------------------------------------------------------------- 5. ainvoke
section("5. ainvoke: 비동기 호출")


async def main() -> None:
    # 비동기 서버(FastAPI 등)에서는 ainvoke/abatch/astream 을 쓴다
    results = await asyncio.gather(
        chain.ainvoke({"history": [], "question": "포인트 적립률은?"}),
        chain.ainvoke({"history": [], "question": "회원 등급 혜택은?"}),
    )
    for r in results:
        print("  async →", r[:60])


asyncio.run(main())
