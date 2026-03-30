"""Tests for protocol models and extensions."""

from agentroom.protocol.extensions import (
    ConfidenceExtension,
    PhaseExtension,
    PhaseTransition,
    RoomPhase,
    VoteExtension,
    VoteValue,
)
from agentroom.protocol.models import AgentCard, Message, MessageType, RoomConfig, RoomState


def test_message_defaults() -> None:
    msg = Message(room_id="r1", from_agent="@claude", type=MessageType.TEXT, content="Hello")
    assert msg.id  # auto-generated
    assert msg.created_at > 0
    assert msg.extensions == {}


def test_phase_extension() -> None:
    ext = PhaseExtension(
        current=RoomPhase.CONSENSUS,
        transition=PhaseTransition(**{"from": "researching", "to": "consensus"}),
    )
    assert ext.current == RoomPhase.CONSENSUS
    assert ext.transition is not None
    assert ext.transition.from_phase == RoomPhase.RESEARCHING


def test_vote_extension() -> None:
    ext = VoteExtension(value=VoteValue.AGREE, rationale="Looks good", target_message_id="msg123")
    assert ext.value == 1


def test_confidence_validation() -> None:
    ext = ConfidenceExtension(value=0.85)
    assert ext.value == 0.85
    import pytest

    with pytest.raises(ValueError):
        ConfidenceExtension(value=1.5)  # out of range


def test_room_state_lead() -> None:
    config = RoomConfig(
        goal="Test",
        agents=[
            AgentCard(name="@claude", provider="anthropic", model="claude-sonnet-4-20250514"),
            AgentCard(name="@gpt4o", provider="openai", model="gpt-4o"),
        ],
    )
    state = RoomState(config=config)
    assert state.lead == "@claude"  # first agent is lead by default
    assert state.phase == RoomPhase.OPEN


def test_room_state_explicit_lead() -> None:
    config = RoomConfig(
        goal="Test",
        agents=[
            AgentCard(name="@claude", provider="anthropic", model="claude-sonnet-4-20250514"),
            AgentCard(name="@gpt4o", provider="openai", model="gpt-4o"),
        ],
        lead_agent="@gpt4o",
    )
    state = RoomState(config=config)
    assert state.lead == "@gpt4o"
