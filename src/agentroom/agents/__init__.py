"""Agent adapters — provider-specific wrappers behind a unified interface."""

from agentroom.agents.base import AgentAdapter
from agentroom.agents.anthropic import AnthropicAdapter
from agentroom.agents.openai import OpenAIAdapter

__all__ = ["AgentAdapter", "AnthropicAdapter", "OpenAIAdapter"]
