"""Tests for agent adapters — mocked SDK calls, no real API keys."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentroom.agents.anthropic import AnthropicAdapter
from agentroom.agents.openai import OpenAIAdapter
from agentroom.protocol.extensions import AgentRole
from agentroom.protocol.models import AgentCard, Message, MessageType


def _make_card(provider: str = "anthropic", name: str = "@claude") -> AgentCard:
    return AgentCard(
        name=name,
        provider=provider,
        model="test-model",
        role=AgentRole.RESEARCHER,
    )


def _make_messages() -> list[Message]:
    return [
        Message(
            room_id="room1",
            from_agent="user",
            type=MessageType.TEXT,
            content="Hello",
        ),
        Message(
            room_id="room1",
            from_agent="@claude",
            type=MessageType.TEXT,
            content="Hi there!",
        ),
    ]


# --- AnthropicAdapter ---


class TestAnthropicAdapter:
    def test_adapter_name(self) -> None:
        card = _make_card("anthropic", "@claude")
        adapter = AnthropicAdapter(card)
        assert adapter.name == "@claude"

    @pytest.mark.asyncio
    async def test_connect_requires_api_key(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card, api_key=None)
        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            await adapter.connect()

    @pytest.mark.asyncio
    async def test_connect_with_explicit_key(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card, api_key="test-key-123")
        await adapter.connect()
        assert adapter._client is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_clears_client(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card, api_key="test-key-123")
        await adapter.connect()
        await adapter.disconnect()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_generate_requires_connection(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card)
        with pytest.raises(RuntimeError, match="not connected"):
            await adapter.generate([], "system prompt")

    @pytest.mark.asyncio
    async def test_generate_calls_api(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card, api_key="test-key")
        await adapter.connect()

        # Mock the API response
        mock_content = MagicMock()
        mock_content.text = "Generated response"
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        adapter._client.messages.create = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        result = await adapter.generate(_make_messages(), "You are a helper")
        assert result == "Generated response"

        adapter._client.messages.create.assert_called_once()  # type: ignore[union-attr]
        call_kwargs = adapter._client.messages.create.call_args  # type: ignore[union-attr]
        assert call_kwargs.kwargs["model"] == "test-model"
        assert call_kwargs.kwargs["system"] == "You are a helper"
        await adapter.disconnect()

    def test_to_api_messages_role_mapping(self) -> None:
        messages = _make_messages()
        api_msgs = AnthropicAdapter._to_api_messages(messages, adapter_name="@claude")

        assert len(api_msgs) == 2
        assert api_msgs[0]["role"] == "user"
        assert api_msgs[0]["content"] == "Hello"
        assert api_msgs[1]["role"] == "assistant"
        assert api_msgs[1]["content"] == "Hi there!"

    def test_to_api_messages_multi_agent_role_mapping(self) -> None:
        """In a multi-agent room, only the adapter's own messages are 'assistant'."""
        messages = [
            Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
            Message(room_id="room1", from_agent="@claude", type=MessageType.TEXT, content="I think..."),
            Message(room_id="room1", from_agent="@gpt4o", type=MessageType.TEXT, content="I disagree..."),
        ]
        api_msgs = AnthropicAdapter._to_api_messages(messages, adapter_name="@claude")

        assert api_msgs[0]["role"] == "user"      # user -> user
        assert api_msgs[1]["role"] == "assistant"  # @claude (self) -> assistant
        assert api_msgs[2]["role"] == "user"       # @gpt4o (other agent) -> user

    @pytest.mark.asyncio
    async def test_is_available_when_disconnected(self) -> None:
        card = _make_card("anthropic")
        adapter = AnthropicAdapter(card)
        assert not await adapter.is_available()


# --- OpenAIAdapter ---


class TestOpenAIAdapter:
    def test_adapter_name(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card)
        assert adapter.name == "@gpt4o"

    @pytest.mark.asyncio
    async def test_connect_requires_api_key(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card, api_key=None)
        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValueError, match="OPENAI_API_KEY"):
            await adapter.connect()

    @pytest.mark.asyncio
    async def test_connect_with_explicit_key(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card, api_key="test-key-123")
        await adapter.connect()
        assert adapter._client is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_with_base_url(self) -> None:
        card = _make_card("openai", "@local")
        adapter = OpenAIAdapter(card, api_key="test-key", base_url="http://localhost:8080/v1")
        await adapter.connect()
        assert adapter._client is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_generate_requires_connection(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card)
        with pytest.raises(RuntimeError, match="not connected"):
            await adapter.generate([], "system prompt")

    @pytest.mark.asyncio
    async def test_generate_calls_api(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card, api_key="test-key")
        await adapter.connect()

        # Mock the API response
        mock_message = MagicMock()
        mock_message.content = "GPT response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        result = await adapter.generate(_make_messages(), "You are a helper")
        assert result == "GPT response"

        adapter._client.chat.completions.create.assert_called_once()  # type: ignore[union-attr]
        call_kwargs = adapter._client.chat.completions.create.call_args  # type: ignore[union-attr]
        assert call_kwargs.kwargs["model"] == "test-model"
        await adapter.disconnect()

    def test_to_api_messages_includes_system(self) -> None:
        messages = _make_messages()
        api_msgs = OpenAIAdapter._to_api_messages(messages, "System prompt", adapter_name="@claude")

        assert api_msgs[0]["role"] == "system"
        assert api_msgs[0]["content"] == "System prompt"
        assert len(api_msgs) == 3  # system + 2 messages

    def test_to_api_messages_role_mapping(self) -> None:
        messages = _make_messages()
        api_msgs = OpenAIAdapter._to_api_messages(messages, "sys", adapter_name="@claude")

        assert api_msgs[1]["role"] == "user"
        assert api_msgs[2]["role"] == "assistant"

    def test_to_api_messages_multi_agent_role_mapping(self) -> None:
        """In a multi-agent room, only the adapter's own messages are 'assistant'."""
        messages = [
            Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
            Message(room_id="room1", from_agent="@gpt4o", type=MessageType.TEXT, content="I think..."),
            Message(room_id="room1", from_agent="@claude", type=MessageType.TEXT, content="I disagree..."),
        ]
        api_msgs = OpenAIAdapter._to_api_messages(messages, "sys", adapter_name="@gpt4o")

        assert api_msgs[1]["role"] == "user"       # user -> user
        assert api_msgs[2]["role"] == "assistant"   # @gpt4o (self) -> assistant
        assert api_msgs[3]["role"] == "user"        # @claude (other agent) -> user

    @pytest.mark.asyncio
    async def test_is_available_when_disconnected(self) -> None:
        card = _make_card("openai", "@gpt4o")
        adapter = OpenAIAdapter(card)
        assert not await adapter.is_available()
