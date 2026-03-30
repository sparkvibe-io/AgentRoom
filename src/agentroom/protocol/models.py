"""Core domain models — messages, agents, rooms."""

from __future__ import annotations

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
    room_id: str
    from_agent: str
    type: MessageType
    content: str
    extensions: dict[str, object] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCard(BaseModel):
    """Describes an agent's identity and capabilities."""

    name: str
    provider: str  # anthropic, openai, google, xai, openai-compat, local
    model: str
    role: AgentRole = AgentRole.RESEARCHER
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)


class RoomConfig(BaseModel):
    """Configuration for creating a room."""

    goal: str
    agents: list[AgentCard]
    lead_agent: str | None = None  # name of the lead; first agent if None
    max_turns: int = 100
    auto_advance: bool = True  # auto-advance phases when consensus reached


class RoomState(BaseModel):
    """Current state of a room."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: RoomConfig
    phase: RoomPhase = RoomPhase.OPEN
    turn: int = 0
    created_at: float = Field(default_factory=time.time)

    @property
    def lead(self) -> str:
        return self.config.lead_agent or self.config.agents[0].name
