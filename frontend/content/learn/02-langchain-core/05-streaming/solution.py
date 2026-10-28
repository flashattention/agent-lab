"""실습: 스트리밍 수집기 만들기

채팅 UI 백엔드에 들어갈 두 가지 유틸리티를 완성하세요.

1. collect_stream(model, prompt) -> StreamResult
   - model.stream(prompt) 의 청크를 화면에 출력하면서(보여 주기)
   - + 로 누적해 완성 메시지를 만들고(모으기)
   - 청크 수, TTFT(첫 청크까지 ms), usage_metadata 를 함께 반환하세요.
2. async collect_tagged_tokens(chain, inputs, tag) -> str
   - chain.astream_events(inputs, version="v2", include_tags=[tag]) 를 순회하며
   - "on_chat_model_stream" 이벤트의 chunk 텍스트만 이어 붙여 반환하세요.
"""

import asyncio
import os
import time
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


@dataclass
class StreamResult:
    text: str
    n_chunks: int
    ttft_ms: float
    total_ms: float
    usage: dict | None


# 1. 동기 스트림 수집기
def collect_stream(model, prompt: str) -> StreamResult:
    start = time.perf_counter()
    ttft_ms = -1.0
    full: AIMessageChunk | None = None
    n_chunks = 0
    for chunk in model.stream(prompt):
        if n_chunks == 0:
            ttft_ms = (time.perf_counter() - start) * 1000
        print(chunk.text, end="", flush=True)
        full = chunk if full is None else full + chunk
        n_chunks += 1
    print()
    total_ms = (time.perf_counter() - start) * 1000
    return StreamResult(
        text=full.text if full else "",
        n_chunks=n_chunks,
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        usage=full.usage_metadata if full else None,
    )


# 2. 태그로 골라 받는 비동기 수집기
async def collect_tagged_tokens(chain, inputs: dict, tag: str) -> str:
    collected = ""
    async for event in chain.astream_events(inputs, version="v2", include_tags=[tag]):
        if event["event"] == "on_chat_model_stream":
            collected += event["data"]["chunk"].text
    return collected


# ------------------------------------------------------------------ 실행
question = "스트리밍 UX에서 TTFT가 중요한 이유는?"
result = collect_stream(llm, question)
print(f"청크 {result.n_chunks}개, TTFT {result.ttft_ms:.1f}ms, 전체 {result.total_ms:.1f}ms, usage={result.usage}")

chain = (
    ChatPromptTemplate.from_template("{q}")
    | llm.with_config(tags=["answer"])
    | StrOutputParser()
    | ChatPromptTemplate.from_template("요약해: {text}")
    | llm.with_config(tags=["summary"])
    | StrOutputParser()
)
answer_tokens = asyncio.run(collect_tagged_tokens(chain, {"q": "SSE와 WebSocket 차이"}, "answer"))
print("answer 태그 토큰:", answer_tokens[:60], "...")

# ------------------------------------------------------------------ 자가 채점
reference = llm.invoke(question).text
assert result.n_chunks > 1, "청크가 여러 개여야 합니다 (stream 을 썼나요?)"
assert result.text == reference, "누적한 텍스트가 invoke 결과와 같아야 합니다 (+ 로 모았나요?)"
assert result.usage and result.usage["total_tokens"] > 0, "usage_metadata 가 누적되어야 합니다"
assert 0 <= result.ttft_ms <= result.total_ms, "TTFT 는 0 이상, 전체 시간 이하여야 합니다"
assert answer_tokens.strip(), "answer 태그 모델의 토큰을 모아야 합니다"
assert "요약해" not in answer_tokens, "summary 단계 토큰이 섞이면 안 됩니다 (include_tags 확인)"
print("✅ 모든 테스트 통과!")
