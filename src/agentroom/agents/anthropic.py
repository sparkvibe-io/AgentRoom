"""Anthropic (Claude) adapter."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import anthropic

from agentroom.agents.base import AgentAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agentroom.protocol.models import AgentCard, Message


class AnthropicAdapter(AgentAdapter):
    """Adapter for Anthropic's Claude models."""

    def __init__(self, card: AgentCard, api_key: str | None = None) -> None:
        super().__init__(card, api_key)
        self._client: anthropic.AsyncAnthropic | None = None

    async def connect(self) -> None:
        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        self._client = anthropic.AsyncAnthropic(api_key=key)

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

        api_messages = self._to_api_messages(messages)
        response = await self._client.messages.create(
            model=self.card.model,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
        )
        return response.content[0].text  # type: ignore[union-attr]

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> AsyncGenerator[str]:
        if not self._client:
            raise RuntimeError("Adapter not connected — call connect() first")

        api_messages = self._to_api_messages(messages)
        async with self._client.messages.stream(
            model=self.card.model,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    @staticmethod
    def _to_api_messages(messages: list[Message]) -> list[anthropic.types.MessageParam]:
        """Convert room messages to Anthropic API format."""
        api_msgs: list[anthropic.types.MessageParam] = []
        for msg in messages:
            role: anthropic.types.MessageParam = {  # type: ignore[assignment]
                "role": "assistant" if msg.from_agent.startswith("@") else "user",
                "content": msg.content,
            }
            api_msgs.append(role)
        return api_msgs
