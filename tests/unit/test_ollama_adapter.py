"""Tests for Ollama adapter -- local LLMs, no API key."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentroom.agents.ollama import OllamaAdapter
from agentroom.protocol.extensions import AgentRole
from agentroom.protocol.models import AgentCard, Message, MessageType


def _make_card(
    name: str = "@llama", model: str = "llama3", provider: str = "ollama"
) -> AgentCard:
    return AgentCard(name=name, provider=provider, model=model, role=AgentRole.RESEARCHER)


def _make_messages() -> list[Message]:
    return [
        Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
        Message(room_id="room1", from_agent="@llama", type=MessageType.TEXT, content="Hi!"),
    ]


class TestOllamaAdapter:
    def test_default_base_url_ollama(self) -> None:
        card = _make_card(provider="ollama")
        adapter = OllamaAdapter(card)
        assert adapter._base_url == "http://localhost:11434/v1"

    def test_default_base_url_lmstudio(self) -> None:
        card = _make_card(provider="lmstudio")
        adapter = OllamaAdapter(card, provider_type="lmstudio")
        assert adapter._base_url == "http://localhost:1234/v1"

    def test_custom_base_url(self) -> None:
        card = _make_card()
        card.base_url = "http://custom:9999/v1"
        adapter = OllamaAdapter(card)
        assert adapter._base_url == "http://custom:9999/v1"

    @pytest.mark.asyncio
    async def test_connect_no_key_required(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()
        assert adapter._client is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_generate(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()

        mock_message = MagicMock()
        mock_message.content = "Ollama response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        result = await adapter.generate(_make_messages(), "system prompt")
        assert result == "Ollama response"
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_clears_client(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()
        await adapter.disconnect()
        assert adapter._client is None

    def test_role_mapping_uses_adapter_name(self) -> None:
        messages = [
            Message(room_id="r", from_agent="user", type=MessageType.TEXT, content="Hi"),
            Message(room_id="r", from_agent="@llama", type=MessageType.TEXT, content="Hello"),
            Message(room_id="r", from_agent="@claude", type=MessageType.TEXT, content="Hey"),
        ]
        card = _make_card(name="@llama")
        adapter = OllamaAdapter(card)
        api_msgs = adapter._to_api_messages(messages, "sys", adapter_name="@llama")

        assert api_msgs[0]["role"] == "system"
        assert api_msgs[1]["role"] == "user"       # user
        assert api_msgs[2]["role"] == "assistant"   # @llama (self)
        assert api_msgs[3]["role"] == "user"        # @claude (other)
