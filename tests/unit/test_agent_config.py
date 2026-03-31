"""Tests for agent config CRUD in the broker."""

from __future__ import annotations

import pytest

from agentroom.broker.queue import MessageBroker
from agentroom.protocol.agent_config import AgentConfig


@pytest.fixture
def broker() -> MessageBroker:
    return MessageBroker()


class TestAgentConfigCRUD:
    def test_save_and_get(self, broker: MessageBroker) -> None:
        config = AgentConfig(
            name="@claude-cli",
            provider="cli",
            model="sonnet-4",
            command="claude",
        )
        broker.save_agent_config(config)
        loaded = broker.get_agent_config(config.id)
        assert loaded is not None
        assert loaded.name == "@claude-cli"
        assert loaded.provider == "cli"
        assert loaded.command == "claude"

    def test_list_configs(self, broker: MessageBroker) -> None:
        c1 = AgentConfig(name="@a1", provider="cli", model="m1", command="claude")
        c2 = AgentConfig(name="@a2", provider="ollama", model="llama3")
        broker.save_agent_config(c1)
        broker.save_agent_config(c2)
        configs = broker.list_agent_configs()
        assert len(configs) == 2

    def test_update_config(self, broker: MessageBroker) -> None:
        config = AgentConfig(name="@old", provider="cli", model="m1", command="claude")
        broker.save_agent_config(config)
        config.name = "@new"
        broker.save_agent_config(config)
        loaded = broker.get_agent_config(config.id)
        assert loaded is not None
        assert loaded.name == "@new"

    def test_delete_config(self, broker: MessageBroker) -> None:
        config = AgentConfig(name="@del", provider="cli", model="m1", command="claude")
        broker.save_agent_config(config)
        broker.delete_agent_config(config.id)
        assert broker.get_agent_config(config.id) is None

    def test_get_nonexistent_returns_none(self, broker: MessageBroker) -> None:
        assert broker.get_agent_config("nonexistent") is None

    def test_redacted_api_key(self) -> None:
        config = AgentConfig(
            name="@gpt", provider="openai", model="gpt-4o", api_key="sk-abc123xyz789"
        )
        redacted = config.redacted()
        assert redacted.api_key == "...z789"
        assert config.api_key == "sk-abc123xyz789"  # original unchanged

    def test_redacted_no_api_key(self) -> None:
        config = AgentConfig(name="@llama", provider="ollama", model="llama3")
        redacted = config.redacted()
        assert redacted.api_key is None
