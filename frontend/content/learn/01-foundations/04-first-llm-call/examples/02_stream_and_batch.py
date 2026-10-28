"""stream / batch / async: 같은 모델을 세 가지 방식으로 호출하기.

- stream: 토큰이 생성되는 대로 받아 화면에 바로 보여준다 (체감 속도↑)
- batch : 여러 입력을 동시에 처리한다 (처리량↑)
- async : ainvoke / astream / abatch — 웹 서버에서 동시 요청을 다룰 때
"""

from __future__ import annotations

import asyncio
import os
import time

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessageChunk

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL, timeout=30, max_retries=2)


def section(title: str) -> None:
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


def demo_stream() -> None:
    section("1) stream: 청크를 받는 대로 출력 + 하나로 합치기")
    start = time.perf_counter()
    first_token_at: float | None = None
    full: AIMessageChunk | None = None
    for chunk in llm.stream("스트리밍이 왜 필요한지 설명해줘"):
        if first_token_at is None:
            first_token_at = time.perf_counter() - start  # TTFT: 첫 토큰까지 걸린 시간
        print(chunk.text, end="|", flush=True)  # '|' 로 청크 경계를 표시
        full = chunk if full is None else full + chunk  # 청크는 + 로 합칠 수 있다
    print()
    assert full is not None
    print(f"\n청크 합친 결과: {full.text[:60]}...")
    print(f"usage(마지막 청크에 담김): {full.usage_metadata}")
    print(f"TTFT ≈ {first_token_at or 0:.3f}s")


def demo_batch() -> None:
    section("2) batch: 여러 질문을 동시에 (max_concurrency 로 동시성 제한)")
    questions = ["LLM이 뭐야?", "토큰이 뭐야?", "에이전트가 뭐야?", "RAG가 뭐야?"]
    start = time.perf_counter()
    replies = llm.batch(questions, config={"max_concurrency": 2})  # 입력 순서대로 결과가 온다
    for q, r in zip(questions, replies):
        print(f"  Q: {q:<12} → {r.text[:45]}")
    print(f"총 {len(replies)}건, {time.perf_counter() - start:.2f}s")

    print("\n  batch_as_completed: 끝나는 순서대로 (index, 결과)")
    for idx, r in llm.batch_as_completed(questions[:2]):
        print(f"  #{idx} 완료 → {r.text[:40]}")


async def demo_async() -> None:
    section("3) async: ainvoke / astream / asyncio.gather")
    r = await llm.ainvoke("비동기로 안녕!")
    print("ainvoke:", r.text[:50])
    pieces = [c.text async for c in llm.astream("비동기 스트리밍")]
    print(f"astream: {len(pieces)}개 청크")
    rs = await asyncio.gather(llm.ainvoke("질문 A"), llm.ainvoke("질문 B"))  # 동시 실행
    print("gather:", [x.text[:20] for x in rs])


if __name__ == "__main__":
    demo_stream()
    demo_batch()
    asyncio.run(demo_async())
