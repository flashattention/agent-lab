"""TypedDict / JSON Schema 로 구조화 출력하기, 그리고 include_raw.

- TypedDict: 결과가 dict, 런타임 검증 없음, LangGraph 상태와 궁합이 좋다
- JSON Schema: 스키마를 데이터로 다룰 수 있다(설정 파일, 다른 언어와 공유)
- include_raw=True: 원본 AIMessage 와 파싱 결과를 함께 받는다
"""

import json
import os

from langchain.chat_models import init_chat_model
from typing_extensions import Annotated, TypedDict

MODEL = os.getenv("LAB_MODEL", "openai:gpt-5-mini")
llm = init_chat_model(MODEL)


# ---------------------------------------------------------------- 1. TypedDict
class Movie(TypedDict):
    """영화 정보."""

    title: Annotated[str, ..., "영화 제목"]  # (타입, ... = 필수, 설명)
    year: Annotated[int, ..., "개봉 연도"]
    genre: Annotated[str | None, None, "장르. 모르면 null"]  # 기본값 None = 선택 필드


print("=" * 12, "1. TypedDict", "=" * 12)
movie = llm.with_structured_output(Movie).invoke("2019년 개봉한 기생충에 대해 알려줘")
print(type(movie).__name__, movie)  # 평범한 dict

# ---------------------------------------------------------------- 2. JSON Schema
print("\n" + "=" * 12, "2. JSON Schema", "=" * 12)
# 실무에서는 이 스키마를 설정 파일/DB 에서 불러오기도 한다
schema_text = """
{
  "title": "WeatherQuery",
  "description": "날씨 질의에서 뽑아낸 파라미터",
  "type": "object",
  "properties": {
    "city": {"type": "string", "description": "도시 이름"},
    "days": {"type": "integer", "description": "며칠 치 예보인지"}
  },
  "required": ["city", "days"]
}
"""
weather_schema = json.loads(schema_text)
query = llm.with_structured_output(weather_schema).invoke("부산 3일치 날씨 예보 보여줘")
print(type(query).__name__, query)

# ---------------------------------------------------------------- 3. include_raw
print("\n" + "=" * 12, "3. include_raw=True", "=" * 12)
result = llm.with_structured_output(weather_schema, include_raw=True).invoke("도쿄 5일 예보")
print("키:", list(result.keys()))
print("parsed        :", result["parsed"])
print("parsing_error :", result["parsing_error"])
raw = result["raw"]
print("raw 타입      :", type(raw).__name__)
# 방식(method)에 따라 원본은 tool_call 이거나 JSON 텍스트다. 디버깅 시 확인할 것.
print("raw.tool_calls:", raw.tool_calls)
print("raw 토큰 사용 :", raw.usage_metadata)
