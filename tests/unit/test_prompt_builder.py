"""Tests for the RoomPromptBuilder."""

from agentroom.agents.base import AgentAdapter
from agentroom.coordinator.prompt_builder import RoomPromptBuilder
from agentroom.protocol.extensions import AgentRole, RoomPhase
from agentroom.protocol.models import AgentCard, Message, RoomConfig, RoomState


class StubAdapter(AgentAdapter):
    """Minimal adapter for testing prompt builder."""

    async def generate(self, messages: list[Message], system_prompt: str) -> str:
        return ""

    async def stream(self, messages: list[Message], system_prompt: str):  # type: ignore[override]
        yield ""


def _make_state(phase: RoomPhase = RoomPhase.RESEARCHING) -> RoomState:
    config = RoomConfig(
        goal="Build a REST API",
        agents=[
            AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR),
            AgentCard(name="@gpt4o", provider="openai", model="test", role=AgentRole.RESEARCHER),
        ],
    )
    state = RoomState(config=config)
    state.phase = phase
    return state


def test_prompt_contains_agent_name() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state()

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "@claude" in prompt


def test_prompt_contains_goal() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state()

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "Build a REST API" in prompt


def test_prompt_contains_role() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state()

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "coordinator" in prompt


def test_prompt_contains_other_participants() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state()

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "@gpt4o" in prompt
    # Should NOT list self in others
    # (the name appears as "You are @claude" but not in the "Other participants" section)


def test_prompt_contains_phase() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state(RoomPhase.CONSENSUS)

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "consensus" in prompt


def test_researching_phase_instructions() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state(RoomPhase.RESEARCHING)

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "gathering information" in prompt.lower() or "proposing approaches" in prompt.lower()


def test_consensus_phase_instructions() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state(RoomPhase.CONSENSUS)

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "vote" in prompt.lower() or "evaluat" in prompt.lower()


def test_implementing_phase_instructions() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state(RoomPhase.IMPLEMENTING)

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "code" in prompt.lower() or "implement" in prompt.lower()


def test_reviewing_phase_instructions() -> None:
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state(RoomPhase.REVIEWING)

    prompt = builder.build(adapter, state, ["@claude", "@gpt4o"])
    assert "review" in prompt.lower()


def test_prompt_with_single_agent() -> None:
    """When only one agent, no 'Other participants' line."""
    builder = RoomPromptBuilder()
    card = AgentCard(name="@claude", provider="anthropic", model="test", role=AgentRole.COORDINATOR)
    adapter = StubAdapter(card)
    state = _make_state()

    prompt = builder.build(adapter, state, ["@claude"])
    assert "Other participants" not in prompt
