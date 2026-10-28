"""토큰(Token) 눈으로 보기: tiktoken 으로 텍스트를 토큰으로 쪼개 본다.

- o200k_base 는 GPT-4o / GPT-5 계열이 쓰는 토크나이저 인코딩이다.
- tiktoken 은 처음 쓸 때 인코딩 파일을 내려받는다. 네트워크가 막힌 환경이면
  근사치(문자 수 기반)로 대체해 예제가 끝까지 실행되도록 한다.
"""

from __future__ import annotations

from typing import Callable


def load_tokenizer() -> tuple[str, Callable[[str], list[int]], Callable[[list[int]], str] | None]:
    """(이름, encode 함수, decode 함수) 를 돌려준다. 실패하면 근사 토크나이저."""
    try:
        import socket

        socket.setdefaulttimeout(5)  # 다운로드가 막혀 있을 때 오래 기다리지 않도록
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        return "tiktoken/o200k_base", enc.encode, enc.decode
    except Exception as exc:  # 오프라인 등
        print(f"⚠️ tiktoken 인코딩을 불러오지 못해 근사치를 사용합니다: {type(exc).__name__}")

        def approx(text: str) -> list[int]:
            # 경험칙: 영어는 ~4글자당 1토큰. 한글은 1글자당 ~1토큰 안팎으로 잡는다.
            ascii_chars = sum(1 for c in text if ord(c) < 128)
            other = len(text) - ascii_chars
            return list(range(max(1, ascii_chars // 4 + other)))

        return "approx", approx, None


if __name__ == "__main__":
    name, encode, decode = load_tokenizer()
    print(f"토크나이저: {name}\n")

    samples = [
        "Hello, world!",
        "안녕하세요, 세상!",
        "The agent called the weather tool.",
        "에이전트가 날씨 도구를 호출했습니다.",
        "def add(a, b): return a + b",
        '{"city": "Seoul", "unit": "celsius"}',
    ]

    print(f"{'텍스트':<40} {'글자':>4} {'토큰':>4}")
    print("-" * 56)
    for s in samples:
        print(f"{s:<40} {len(s):>4} {len(encode(s)):>4}")

    # 토큰이 실제로 어떻게 잘리는지 확인 (decode 가능할 때만)
    if decode is not None:
        print("\n🔍 토큰 단위로 쪼개 보기")
        for s in ["unbelievable", "토크나이저", "ChatGPT"]:
            ids = encode(s)
            pieces = [decode([i]) for i in ids]
            print(f"  {s!r:>16} → ids={ids} → pieces={pieces}")

    # 같은 의미라도 언어/형식에 따라 토큰 수(=비용, 컨텍스트 사용량)가 다르다
    en = "Please summarize the following customer complaint in three bullet points."
    ko = "다음 고객 불만 사항을 세 개의 글머리 기호로 요약해 주세요."
    print(f"\n같은 지시문 — 영어 {len(encode(en))}토큰 vs 한국어 {len(encode(ko))}토큰")
    print("💡 토큰 수가 곧 비용과 컨텍스트 윈도우 사용량입니다.")
