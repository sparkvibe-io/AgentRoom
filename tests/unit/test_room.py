"""Tests for the Room coordinator — lifecycle, turns, phases."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agentroom.agents.base import AgentAdapter
from agentroom.broker.queue import MessageBroker
from agentroom.coordinator.room import Room
from agentroom.protocol.extensions import AgentRole, RoomPhase
from agentroom.protocol.models import AgentCard, Message, MessageType, RoomConfig


def _make_config(
    goal: str = "Test goal",
    agents: list[AgentCard] | None = None,
) -> RoomConfig:
    if agents is None:
        agents = [
            AgentCard(name="@alice", provider="anthropic", model="test-model", role=AgentRole.COORDINATOR),
            AgentCard(name="@bob", provider="openai", model="test-model", role=AgentRole.RESEARCHER),
        ]
    return RoomConfig(goal=goal, agents=agents)


class FakeAdapter(AgentAdapter):
    """A minimal adapter that returns a canned response."""

    def __init__(self, card: AgentCard, response: str = "I agree.") -> None:
        super().__init__(card)
        self._response = response
        self.connected = False

    async def generate(self, messages: list[Message], system_prompt: str) -> str:
        return self._response

    async def stream(self, messages: list[Message], system_prompt: str):
        for word in self._response.split():
            yield word + " "

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False


@pytest.fixture
def room() -> Room:
    config = _make_config()
    broker = MessageBroker(":memory:")
    r = Room(config=config, broker=broker)
    for card in config.agents:
        r.add_agent(FakeAdapter(card, response=f"Response from {card.name}"))
    return r


def test_room_initial_state(room: Room) -> None:
    assert room.phase == RoomPhase.OPEN
    assert room.state.turn == 0
    assert len(room.room_id) == 12


def test_room_has_agents(room: Room) -> None:
    assert "@alice" in room.adapters
    assert "@bob" in room.adapters


@pytest.mark.asyncio
async def test_room_start_publishes_messages(room: Room) -> None:
    await room.start()
    history = room.broker.get_history(room.room_id)

    # Should have at least the opening system message + phase message
    assert len(history) >= 2

    system_msg = history[0]
    assert system_msg.type == MessageType.SYSTEM
    assert "Test goal" in system_msg.content

    phase_msg = history[1]
    assert phase_msg.type == MessageType.PHASE
    assert room.phase == RoomPhase.RESEARCHING


@pytest.mark.asyncio
async def test_room_start_connects_adapters(room: Room) -> None:
    await room.start()
    for adapter in room.adapters.values():
        assert isinstance(adapter, FakeAdapter)
        assert adapter.connected


@pytest.mark.asyncio
async def test_room_stop_disconnects_adapters(room: Room) -> None:
    await room.start()
    await room.stop()
    for adapter in room.adapters.values():
        assert isinstance(adapter, FakeAdapter)
        assert not adapter.connected


@pytest.mark.asyncio
async def test_run_turn_round_robin(room: Room) -> None:
    await room.start()

    msg1 = await room.run_turn()
    assert msg1 is not None
    assert msg1.from_agent == "@alice"
    assert msg1.content == "Response from @alice"
    assert room.state.turn == 1

    msg2 = await room.run_turn()
    assert msg2 is not None
    assert msg2.from_agent == "@bob"
    assert room.state.turn == 2


@pytest.mark.asyncio
async def test_run_turn_specific_agent(room: Room) -> None:
    await room.start()

    msg = await room.run_turn("@bob")
    assert msg is not None
    assert msg.from_agent == "@bob"


@pytest.mark.asyncio
async def test_run_turn_unknown_agent(room: Room) -> None:
    await room.start()

    msg = await room.run_turn("@unknown")
    assert msg is None


@pytest.mark.asyncio
async def test_run_turn_when_not_running(room: Room) -> None:
    # Don't start the room
    msg = await room.run_turn()
    assert msg is None


@pytest.mark.asyncio
async def test_run_round(room: Room) -> None:
    await room.start()

    messages = await room.run_round()
    assert len(messages) == 2
    assert messages[0].from_agent == "@alice"
    assert messages[1].from_agent == "@bob"
    assert room.state.turn == 2


@pytest.mark.asyncio
async def test_set_phase(room: Room) -> None:
    await room.start()

    room.set_phase(RoomPhase.CONSENSUS)
    assert room.phase == RoomPhase.CONSENSUS

    # Phase message should be published
    history = room.broker.get_history(room.room_id)
    phase_msgs = [m for m in history if m.type == MessageType.PHASE]
    latest_phase = phase_msgs[-1]
    assert "consensus" in latest_phase.content.lower()
    assert latest_phase.extensions.get("agentroom/phase", {}).get("current") == "consensus"


@pytest.mark.asyncio
async def test_user_message(room: Room) -> None:
    await room.start()

    await room.user_message("Hello agents!")
    history = room.broker.get_history(room.room_id)
    user_msgs = [m for m in history if m.from_agent == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0].content == "Hello agents!"


@pytest.mark.asyncio
async def test_message_callback_fired(room: Room) -> None:
    received: list[Message] = []
    room.on_message(lambda msg: received.append(msg))

    await room.start()

    # start() publishes system + phase messages
    assert len(received) >= 2


@pytest.mark.asyncio
async def test_run_turn_handles_adapter_error(room: Room) -> None:
    await room.start()

    # Replace adapter generate with an error
    adapter = room.adapters["@alice"]
    adapter.generate = AsyncMock(side_effect=RuntimeError("API Error"))  # type: ignore[assignment]

    msg = await room.run_turn("@alice")
    assert msg is None  # Should return None, not raise


@pytest.mark.asyncio
async def test_stream_turn(room: Room) -> None:
    await room.start()

    tokens: list[str] = []
    async for agent_name, token in room.stream_turn("@alice"):
        tokens.append(token)
        assert agent_name == "@alice"

    assert len(tokens) > 0
    assert room.state.turn == 1

    # Message should be in history
    history = room.broker.get_history(room.room_id)
    agent_msgs = [m for m in history if m.from_agent == "@alice"]
    assert len(agent_msgs) == 1
