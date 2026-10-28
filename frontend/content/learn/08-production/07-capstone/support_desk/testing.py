"""테스트 지원: 대본(scripted) 모델 (8.2강).

전문가 에이전트에 주입해 '모델이 이렇게 답하면 시스템이 이렇게 동작한다'를 결정적으로 검증한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """responses 를 순서대로 반환. 대본이 바닥나면 AssertionError."""

    responses: list[AIMessage] = Field(default_factory=list)
    _i: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def calls_made(self) -> int:
        return self._i

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        if self._i >= len(self.responses):
            raise AssertionError(f"대본 초과: {self._i + 1}번째 모델 호출")
        msg = self.responses[self._i]
        self._i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def call(name: str, **args: Any) -> AIMessage:
    """도구 호출 한 개짜리 AIMessage."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])
