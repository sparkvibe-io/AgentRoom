"""Room — the core orchestration unit. Manages agents, turns, and phases."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from agentroom.agents.base import AgentAdapter
from agentroom.broker.queue import MessageBroker
from agentroom.coordinator.prompt_builder import RoomPromptBuilder
from agentroom.protocol.extensions import RoomPhase
from agentroom.protocol.models import (
    Message,
    MessageType,
    RoomConfig,
    RoomState,
)

logger = logging.getLogger(__name__)


class Room:
    """A collaborative room where agents work together.

    The Room coordinates the lifecycle:
    1. Agents join and connect
    2. The user's goal is broadcast
    3. Agents take turns responding (round-robin for now)
    4. Phase transitions are managed by the coordinator
    """

    def __init__(
        self,
        config: RoomConfig,
        broker: MessageBroker | None = None,
    ) -> None:
        self.state = RoomState(config=config)
        self.broker = broker or MessageBroker()
        self.adapters: dict[str, AgentAdapter] = {}
        self._prompt_builder = RoomPromptBuilder()
        self._running = False
        self._message_callbacks: list[Any] = []

    @property
    def room_id(self) -> str:
        return self.state.id

    @property
    def phase(self) -> RoomPhase:
        return self.state.phase

    def on_message(self, callback: Any) -> None:
        """Register a callback for new messages (used by server for WebSocket push)."""
        self._message_callbacks.append(callback)

    async def start(self) -> None:
        """Connect all adapters and begin the room."""
        for adapter in self.adapters.values():
            await adapter.connect()

        # Publish the opening system message
        opening = Message(
            room_id=self.room_id,
            from_agent="system",
            type=MessageType.SYSTEM,
            content=f"Room created. Goal: {self.state.config.goal}",
        )
        self.broker.publish(opening)
        self._notify(opening)

        self.state.phase = RoomPhase.RESEARCHING
        phase_msg = Message(
            room_id=self.room_id,
            from_agent="system",
            type=MessageType.PHASE,
            content=f"Phase: {self.state.phase.value}",
            extensions={"agentroom/phase": {"current": self.state.phase.value}},
        )
        self.broker.publish(phase_msg)
        self._notify(phase_msg)

        self._running = True

    async def stop(self) -> None:
        """Disconnect all adapters and stop the room."""
        self._running = False
        for adapter in self.adapters.values():
            await adapter.disconnect()

    def add_agent(self, adapter: AgentAdapter) -> None:
        """Register an agent adapter."""
        self.adapters[adapter.name] = adapter

    def set_phase(self, phase: RoomPhase) -> None:
        """Manually transition to a new phase."""
        old = self.state.phase
        self.state.phase = phase
        msg = Message(
            room_id=self.room_id,
            from_agent="system",
            type=MessageType.PHASE,
            content=f"Phase transition: {old.value} → {phase.value}",
            extensions={
                "agentroom/phase": {
                    "current": phase.value,
                    "transition": {"from": old.value, "to": phase.value},
                }
            },
        )
        self.broker.publish(msg)
        self._notify(msg)

    async def user_message(self, content: str, from_user: str = "user") -> None:
        """Inject a message from the human director."""
        msg = Message(
            room_id=self.room_id,
            from_agent=from_user,
            type=MessageType.TEXT,
            content=content,
        )
        self.broker.publish(msg)
        self._notify(msg)

    async def run_turn(self, agent_name: str | None = None) -> Message | None:
        """Run a single agent turn. If agent_name is None, use round-robin."""
        if not self._running:
            return None

        # Pick the next agent
        if agent_name:
            adapter = self.adapters.get(agent_name)
        else:
            adapter = self._next_agent()

        if not adapter:
            return None

        # Build context
        history = self.broker.get_history(self.room_id, limit=50)
        agent_names = list(self.adapters.keys())
        system_prompt = self._prompt_builder.build(adapter, self.state, agent_names)

        # Generate response
        try:
            response_text = await adapter.generate(history, system_prompt)
        except Exception:
            logger.exception("Agent %s failed to generate", adapter.name)
            return None

        # Publish response
        response = Message(
            room_id=self.room_id,
            from_agent=adapter.name,
            type=MessageType.TEXT,
            content=response_text,
        )
        self.broker.publish(response)
        self._notify(response)

        self.state.turn += 1
        return response

    async def stream_turn(self, agent_name: str | None = None) -> AsyncIterator[tuple[str, str]]:
        """Stream a single agent turn, yielding (agent_name, token) tuples."""
        if not self._running:
            return

        adapter = self.adapters.get(agent_name) if agent_name else self._next_agent()
        if not adapter:
            return

        history = self.broker.get_history(self.room_id, limit=50)
        agent_names = list(self.adapters.keys())
        system_prompt = self._prompt_builder.build(adapter, self.state, agent_names)

        full_response: list[str] = []
        try:
            async for token in adapter.stream(history, system_prompt):
                full_response.append(token)
                yield (adapter.name, token)
        except Exception:
            logger.exception("Agent %s failed during streaming", adapter.name)
            return

        # Publish complete message to broker
        response = Message(
            room_id=self.room_id,
            from_agent=adapter.name,
            type=MessageType.TEXT,
            content="".join(full_response),
        )
        self.broker.publish(response)
        self._notify(response)
        self.state.turn += 1

    async def run_round(self) -> list[Message]:
        """Run one full round — every agent gets a turn."""
        messages: list[Message] = []
        for name in list(self.adapters.keys()):
            msg = await self.run_turn(name)
            if msg:
                messages.append(msg)
        return messages

    def _next_agent(self) -> AgentAdapter | None:
        """Round-robin agent selection."""
        agents = list(self.adapters.values())
        if not agents:
            return None
        return agents[self.state.turn % len(agents)]

    def _notify(self, message: Message) -> None:
        """Notify all registered callbacks of a new message."""
        for cb in self._message_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.get_event_loop().create_task(cb(message))
                else:
                    cb(message)
            except Exception:
                logger.exception("Message callback error")
