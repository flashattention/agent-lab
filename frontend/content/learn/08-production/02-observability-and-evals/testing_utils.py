"""그래프/에이전트 단위 테스트용 도구 모음.

ScriptedChatModel
    미리 정해 둔 AIMessage 를 순서대로 돌려주는 '대본' 모델.
    LLM 출력을 고정하면 '모델이 이렇게 답했을 때 그래프가 올바르게 움직이는가'를
    결정적으로(deterministic) 테스트할 수 있다. 네트워크도, 비용도 없다.

run_tests
    pytest 가 없는 환경에서 test_* 함수를 모아 실행하는 아주 작은 러너.
    실제 저장소에서는 pytest 를 그대로 쓰면 된다.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """responses 를 차례대로 반환하는 테스트용 채팅 모델.

    - bind_tools() 를 지원하므로 create_agent / ToolNode 그래프에 그대로 꽂을 수 있다.
    - 받은 입력 메시지를 calls 에 기록하므로 '모델에게 무엇이 전달됐는지'도 검증할 수 있다.
    """

    responses: list[AIMessage] = Field(default_factory=list)
    _index: int = PrivateAttr(default=0)
    _calls: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def calls(self) -> list[list[BaseMessage]]:
        return self._calls

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        # 도구 스키마는 무시하고 자기 자신을 돌려준다(대본은 이미 정해져 있으므로)
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        if self._index >= len(self.responses):
            raise AssertionError(f"대본이 바닥났습니다: 모델이 {self._index + 1}번째로 호출됐습니다")
        self._calls.append(list(messages))
        msg = self.responses[self._index]
        self._index += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_call(name: str, args: dict[str, Any], call_id: str | None = None) -> AIMessage:
    """도구 호출 하나를 담은 AIMessage 를 만든다."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id or f"call_{name}"}])


def run_tests(tests: list[Callable[[], None]]) -> tuple[int, int]:
    """test 함수 목록을 실행하고 (통과 수, 실패 수)를 돌려준다."""
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASSED  {fn.__name__}")
        except Exception:  # noqa: BLE001 - 테스트 러너는 모든 실패를 모은다
            failed += 1
            print(f"  FAILED  {fn.__name__}")
            print("    " + traceback.format_exc().strip().splitlines()[-1])
    print(f"\n{passed} passed, {failed} failed")
    return passed, failed
