"""Core domain models — messages, agents, rooms."""

from __future__ import annotations

import secrets
import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field

from agentroom.protocol.extensions import AgentRole, RoomPhase


class MessageType(StrEnum):
    TEXT = "text"
    PROPOSAL = "proposal"
    VOTE = "vote"
    PHASE = "phase"
    SYSTEM = "system"
    REVIEW = "review"
    HANDOFF = "handoff"
    THOUGHT = "thought"


class Message(BaseModel):
    """A message in the room queue. Wraps content + extension metadata."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    room_id: str = Field(max_length=64)
    from_agent: str = Field(max_length=100)
    type: MessageType
    content: str = Field(max_length=100_000)
    extensions: dict[str, object] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCard(BaseModel):
    """Describes an agent's identity and capabilities."""

    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    role: AgentRole = AgentRole.RESEARCHER
    description: str = Field(default="", max_length=1000)
    capabilities: list[str] = Field(default_factory=list, max_length=20)


class RoomConfig(BaseModel):
    """Configuration for creating a room."""

    goal: str = Field(min_length=1, max_length=5000)
    agents: list[AgentCard] = Field(min_length=1, max_length=10)
    lead_agent: str | None = None
    max_turns: int = Field(default=100, ge=1, le=1000)
    auto_advance: bool = True


class RoomState(BaseModel):
    """Current state of a room."""

    id: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    config: RoomConfig
    phase: RoomPhase = RoomPhase.OPEN
    turn: int = 0
    created_at: float = Field(default_factory=time.time)

    @property
    def lead(self) -> str:
        return self.config.lead_agent or self.config.agents[0].name
