"""Base agent adapter — the interface all providers implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agentroom.protocol.models import AgentCard, Message


class AgentAdapter(ABC):
    """Unified interface for all agent providers.

    Each adapter wraps a provider SDK (Anthropic, OpenAI, etc.) and translates
    room messages into provider-specific API calls.
    """

    def __init__(self, card: AgentCard, api_key: str | None = None) -> None:
        self.card = card
        self.api_key = api_key

    @property
    def name(self) -> str:
        return self.card.name

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> str:
        """Generate a complete response given conversation history + system prompt."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> AsyncGenerator[str]:
        """Stream a response token-by-token."""
        yield ""  # pragma: no cover

    async def connect(self) -> None:  # noqa: B027
        """Called when the adapter joins a room. Override for setup."""

    async def disconnect(self) -> None:  # noqa: B027
        """Called when the adapter leaves a room. Override for cleanup."""

    async def is_available(self) -> bool:
        """Health check — can this adapter reach its provider?"""
        return True
