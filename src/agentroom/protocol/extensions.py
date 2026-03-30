"""AgentRoom A2A extension models — room-specific metadata on A2A messages."""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


class RoomPhase(StrEnum):
    OPEN = "open"
    RESEARCHING = "researching"
    CONSENSUS = "consensus"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    DONE = "done"


class AgentRole(StrEnum):
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    OBSERVER = "observer"
    DIRECTOR = "director"


class VoteValue(IntEnum):
    BLOCK = -1
    NEUTRAL = 0
    AGREE = 1


class ReviewSeverity(StrEnum):
    COMMENT = "comment"
    SUGGESTION = "suggestion"
    BLOCKING = "blocking"


# --- Extension models attached to A2A message metadata ---


class PhaseTransition(BaseModel):
    from_phase: RoomPhase = Field(alias="from")
    to_phase: RoomPhase = Field(alias="to")

    model_config = {"populate_by_name": True}


class PhaseExtension(BaseModel):
    current: RoomPhase
    transition: PhaseTransition | None = None


class VoteExtension(BaseModel):
    value: VoteValue
    rationale: str
    target_message_id: str


class ProposalExtension(BaseModel):
    title: str
    summary: str


class ReviewExtension(BaseModel):
    severity: ReviewSeverity
    file: str | None = None
    line: int | None = None


class LgtmExtension(BaseModel):
    approved_at: float


class HandoffExtension(BaseModel):
    from_role: AgentRole
    to_role: AgentRole
    to_agent: str


class ThoughtExtension(BaseModel):
    visible: bool


class ConfidenceExtension(BaseModel):
    value: float = Field(ge=0.0, le=1.0)


class CostExtension(BaseModel):
    tokens_used: int
    estimated_cost: float
    tools_used: list[str] = Field(default_factory=list)
