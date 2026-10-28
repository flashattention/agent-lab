"""스트리밍 기초: 토큰 출력, 청크 누적, TTFT 측정, 체인 스트리밍, 도구 호출 청크.

Mock 모드에서는 응답이 단어 단위 청크로 나뉘어 온다. 실제 모델은 더 잘게(토큰 단위) 온다.
"""

import os
import time
from collections.abc import Iterator

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessageChunk
from langchain.tools import tool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableGenerator

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


# ---------------------------------------------------------------- 1. 토큰 스트리밍 + 누적 + TTFT
section("1. 보여 주면서 동시에 모으기")
start = time.perf_counter()
ttft: float | None = None
full: AIMessageChunk | None = None
n_chunks = 0

for chunk in llm.stream("스트리밍이 왜 중요한지 설명해 줘"):
    if ttft is None:
        ttft = time.perf_counter() - start  # 첫 청크까지 걸린 시간
    print(chunk.text, end="", flush=True)  # 보여 주기
    full = chunk if full is None else full + chunk  # 모으기
    n_chunks += 1

total = time.perf_counter() - start
print(f"\n\n청크 수: {n_chunks} | TTFT: {ttft * 1000:.1f}ms | 전체: {total * 1000:.1f}ms")
print("누적 결과 타입:", type(full).__name__)
print("완성 텍스트 길이:", len(full.text))
print("usage_metadata:", full.usage_metadata)  # 마지막 청크에 담겨 온 사용량이 합쳐져 있다

# ---------------------------------------------------------------- 2. 청크 덧셈의 원리
section("2. 청크는 + 로 합쳐진다")
a = AIMessageChunk(content="스트")
b = AIMessageChunk(content="리밍은 ")
c = AIMessageChunk(content="빠르다", usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8})
merged = a + b + c
print(repr(merged.text), merged.usage_metadata)

# ---------------------------------------------------------------- 3. 체인 스트리밍
section("3. prompt | llm | parser 체인 스트리밍")
prompt = ChatPromptTemplate.from_template("{topic}을(를) 초보자에게 한 문단으로 설명해 줘")
chain = prompt | llm | StrOutputParser()
pieces = list(chain.stream({"topic": "벡터 DB"}))
print(f"조각 {len(pieces)}개, 첫 3개: {pieces[:3]}")


# 마지막 단계도 스트리밍하려면 '입력 iterator → 출력 iterator' 제너레이터를 쓴다
def mark_numbers(chunks: Iterator[str]) -> Iterator[str]:
    """조각이 들어오는 즉시 숫자를 강조해 내보낸다."""
    for piece in chunks:
        yield "".join(f"[{ch}]" if ch.isdigit() else ch for ch in piece)


stream_chain = chain | RunnableGenerator(mark_numbers)
pieces2 = list(stream_chain.stream({"topic": "GPT-5 모델"}))
print(f"제너레이터 단계 뒤에도 조각 {len(pieces2)}개로 스트리밍됨: {pieces2[:3]}")

# ---------------------------------------------------------------- 4. 도구 호출 청크
section("4. 도구 호출도 조각으로 온다")


@tool
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회한다."""
    return f"{city}: 맑음"


full_tc: AIMessageChunk | None = None
for chunk in llm.bind_tools([get_weather]).stream("부산 날씨 알려줘"):
    for tcc in chunk.tool_call_chunks:
        # 실제 모델에서는 args 가 '{"ci' / 'ty": "부' / '산"}' 처럼 부분 문자열로 나뉘어 온다
        print(f"  조각: name={tcc['name']!r} args={tcc['args']!r} index={tcc['index']}")
    full_tc = chunk if full_tc is None else full_tc + chunk

print("합친 tool_calls:", full_tc.tool_calls)  # 파싱된 dict 완성본
