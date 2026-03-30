"""OpenAI (GPT) adapter."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import openai

from agentroom.agents.base import AgentAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from openai.types.chat import ChatCompletionMessageParam

    from agentroom.protocol.models import AgentCard, Message


class OpenAIAdapter(AgentAdapter):
    """Adapter for OpenAI models (GPT-4o, etc.) and OpenAI-compatible APIs."""

    def __init__(
        self,
        card: AgentCard,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(card, api_key)
        self._base_url = base_url
        self._client: openai.AsyncOpenAI | None = None

    async def connect(self) -> None:
        key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required")
        self._client = openai.AsyncOpenAI(api_key=key, base_url=self._base_url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def is_available(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def generate(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> str:
        if not self._client:
            raise RuntimeError("Adapter not connected — call connect() first")

        api_messages = self._to_api_messages(messages, system_prompt)
        response = await self._client.chat.completions.create(
            model=self.card.model,
            messages=api_messages,
        )
        return response.choices[0].message.content or ""

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> AsyncGenerator[str]:
        if not self._client:
            raise RuntimeError("Adapter not connected — call connect() first")

        api_messages = self._to_api_messages(messages, system_prompt)
        stream = await self._client.chat.completions.create(
            model=self.card.model,
            messages=api_messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _to_api_messages(
        messages: list[Message], system_prompt: str
    ) -> list[ChatCompletionMessageParam]:
        """Convert room messages to OpenAI chat format."""
        api_msgs: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in messages:
            if msg.from_agent.startswith("@"):
                api_msgs.append({"role": "assistant", "content": msg.content})
            else:
                api_msgs.append({"role": "user", "content": msg.content})
        return api_msgs
