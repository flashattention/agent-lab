"""비동기 스트리밍(astream)과 astream_events.

- 두 사용자의 요청을 asyncio 로 '동시에' 스트리밍한다 (웹 서버 상황)
- astream_events(version="v2")로 체인 내부 이벤트를 관찰한다
- 태그(include_tags)로 여러 모델 중 '답변 모델'의 토큰만 골라낸다
"""

import asyncio
import os
from collections import Counter

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. astream 동시 처리
async def stream_for_user(user: str, question: str, log: list[str]) -> str:
    """한 사용자의 응답을 스트리밍한다. 토큰을 기다리는 동안 다른 요청이 처리된다."""
    text = ""
    async for chunk in llm.astream(question):
        text += chunk.text
        log.append(user)  # 어떤 사용자의 청크가 도착했는지 순서를 기록
    return text


async def demo_concurrent() -> None:
    section("1. astream: 두 요청을 동시에 스트리밍")
    log: list[str] = []
    a, b = await asyncio.gather(
        stream_for_user("A", "파이썬 비동기 설명해 줘", log),
        stream_for_user("B", "SSE가 뭐야?", log),
    )
    print("청크 도착 순서(앞 20개):", "".join(log[:20]))
    print("A 완성:", a[:50], "...")
    print("B 완성:", b[:50], "...")


# ---------------------------------------------------------------- 2. astream_events
draft_prompt = ChatPromptTemplate.from_template("{topic}에 대한 짧은 답변을 써 줘")
answer_llm = llm.with_config(tags=["answer"])  # 사용자에게 보여 줄 모델
review_llm = llm.with_config(tags=["review"])  # 내부 검토용 모델 (사용자에게 숨김)

chain = (
    draft_prompt
    | answer_llm
    | StrOutputParser()
    | RunnableLambda(lambda draft: f"다음 답변을 검토해 줘: {draft[:40]}")
    | review_llm
    | StrOutputParser()
)


async def demo_events() -> None:
    section("2. astream_events: 어떤 이벤트가 흐르나")
    counts: Counter = Counter()
    async for event in chain.astream_events({"topic": "RAG"}, version="v2"):
        counts[event["event"]] += 1
    for name, n in sorted(counts.items()):
        print(f"  {name:<24} {n}")

    section("3. 'answer' 태그 모델의 토큰만 골라 받기")
    print("  화면 출력: ", end="")
    async for event in chain.astream_events({"topic": "RAG"}, version="v2", include_tags=["answer"]):
        if event["event"] == "on_chat_model_stream":
            print(event["data"]["chunk"].text, end="", flush=True)
        elif event["event"] == "on_chat_model_end":
            usage = event["data"]["output"].usage_metadata
            print(f"\n  [답변 모델 완료] tags={event['tags']} usage={usage}")

    section("4. chain.astream 은 '마지막 단계'만 흘려보낸다")
    last = [piece async for piece in chain.astream({"topic": "RAG"})]
    print("  마지막(review) 단계 출력 앞부분:", "".join(last)[:60], "...")


async def main() -> None:
    await demo_concurrent()
    await demo_events()


asyncio.run(main())
