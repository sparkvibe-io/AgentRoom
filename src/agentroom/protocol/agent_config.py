"""Agent configuration model -- persisted to SQLite."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """A saved agent configuration."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    command: str | None = Field(default=None, max_length=200)
    cli_args: list[str] = Field(default_factory=list, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def redacted(self) -> AgentConfig:
        """Return a copy with the API key redacted for safe display."""
        key = self.api_key
        redacted_key = f"...{key[-4:]}" if key and len(key) >= 4 else "***" if key else None
        return self.model_copy(update={"api_key": redacted_key})
