"""SQLite-backed FIFO message queue with cursor-based consumption."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from agentroom.protocol.agent_config import AgentConfig
from agentroom.protocol.models import Message

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT    NOT NULL UNIQUE,
    room_id    TEXT    NOT NULL,
    from_agent TEXT    NOT NULL,
    type       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    extensions TEXT    NOT NULL DEFAULT '{}',
    created_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_cursors (
    agent_id  TEXT NOT NULL,
    room_id   TEXT NOT NULL,
    last_seq  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (agent_id, room_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_room_seq ON messages (room_id, seq);

CREATE TABLE IF NOT EXISTS agent_configs (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    command    TEXT,
    cli_args   TEXT NOT NULL DEFAULT '[]',
    base_url   TEXT,
    api_key    TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class MessageBroker:
    """Durable FIFO message queue backed by SQLite.

    One broker per room. Agents publish messages and poll from their cursor.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._listeners: list[Callable[[Message, int], None]] = []

    def close(self) -> None:
        self._conn.close()

    # --- Publish ---

    def publish(self, message: Message) -> int:
        """Insert a message into the queue. Returns the sequence number."""
        cur = self._conn.execute(
            """INSERT INTO messages (id, room_id, from_agent, type, content, extensions, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                message.id,
                message.room_id,
                message.from_agent,
                message.type.value,
                message.content,
                json.dumps(message.extensions, default=str),
                message.created_at,
            ),
        )
        self._conn.commit()
        seq = cur.lastrowid or 0

        # Notify listeners
        for callback in self._listeners:
            callback(message, seq)

        return seq

    # --- Subscribe / Poll ---

    def poll(self, room_id: str, agent_id: str, limit: int = 50) -> list[tuple[int, Message]]:
        """Fetch new messages for an agent from their cursor position.

        Returns list of (seq, Message) tuples.
        """
        cursor_seq = self._get_cursor(agent_id, room_id)
        rows = self._conn.execute(
            """SELECT seq, id, room_id, from_agent, type, content, extensions, created_at
               FROM messages
               WHERE room_id = ? AND seq > ?
               ORDER BY seq ASC
               LIMIT ?""",
            (room_id, cursor_seq, limit),
        ).fetchall()

        messages: list[tuple[int, Message]] = []
        for row in rows:
            msg = Message(
                id=row[1],
                room_id=row[2],
                from_agent=row[3],
                type=row[4],
                content=row[5],
                extensions=json.loads(row[6]),
                created_at=row[7],
            )
            messages.append((row[0], msg))

        return messages

    def advance_cursor(self, agent_id: str, room_id: str, seq: int) -> None:
        """Advance an agent's cursor after processing messages."""
        self._conn.execute(
            """INSERT INTO agent_cursors (agent_id, room_id, last_seq)
               VALUES (?, ?, ?)
               ON CONFLICT (agent_id, room_id)
               DO UPDATE SET last_seq = excluded.last_seq""",
            (agent_id, room_id, seq),
        )
        self._conn.commit()

    def get_history(self, room_id: str, limit: int = 200) -> list[Message]:
        """Get recent message history for a room."""
        rows = self._conn.execute(
            """SELECT id, room_id, from_agent, type, content, extensions, created_at
               FROM messages
               WHERE room_id = ?
               ORDER BY seq DESC
               LIMIT ?""",
            (room_id, limit),
        ).fetchall()

        messages = [
            Message(
                id=row[0],
                room_id=row[1],
                from_agent=row[2],
                type=row[3],
                content=row[4],
                extensions=json.loads(row[5]),
                created_at=row[6],
            )
            for row in reversed(rows)
        ]
        return messages

    def on_message(self, callback: Callable[[Message, int], None]) -> None:
        """Register a listener called on every publish."""
        self._listeners.append(callback)

    # --- Internal ---

    def _get_cursor(self, agent_id: str, room_id: str) -> int:
        row = self._conn.execute(
            "SELECT last_seq FROM agent_cursors WHERE agent_id = ? AND room_id = ?",
            (agent_id, room_id),
        ).fetchone()
        return row[0] if row else 0

    # --- Agent Config CRUD ---

    def save_agent_config(self, config: AgentConfig) -> None:
        """Insert or update an agent configuration."""
        self._conn.execute(
            """INSERT INTO agent_configs (id, name, provider, model, command, cli_args,
                   base_url, api_key, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (id) DO UPDATE SET
                   name=excluded.name, provider=excluded.provider, model=excluded.model,
                   command=excluded.command, cli_args=excluded.cli_args,
                   base_url=excluded.base_url, api_key=excluded.api_key,
                   updated_at=excluded.updated_at""",
            (
                config.id,
                config.name,
                config.provider,
                config.model,
                config.command,
                json.dumps(config.cli_args),
                config.base_url,
                config.api_key,
                config.created_at,
                config.updated_at,
            ),
        )
        self._conn.commit()

    def get_agent_config(self, config_id: str) -> AgentConfig | None:
        """Fetch an agent configuration by ID."""
        row = self._conn.execute(
            """SELECT id, name, provider, model, command, cli_args, base_url, api_key,
                   created_at, updated_at
               FROM agent_configs WHERE id = ?""",
            (config_id,),
        ).fetchone()
        if not row:
            return None
        return AgentConfig(
            id=row[0], name=row[1], provider=row[2], model=row[3], command=row[4],
            cli_args=json.loads(row[5]), base_url=row[6], api_key=row[7],
            created_at=row[8], updated_at=row[9],
        )

    def list_agent_configs(self) -> list[AgentConfig]:
        """List all saved agent configurations."""
        rows = self._conn.execute(
            """SELECT id, name, provider, model, command, cli_args, base_url, api_key,
                   created_at, updated_at
               FROM agent_configs ORDER BY created_at"""
        ).fetchall()
        return [
            AgentConfig(
                id=r[0], name=r[1], provider=r[2], model=r[3], command=r[4],
                cli_args=json.loads(r[5]), base_url=r[6], api_key=r[7],
                created_at=r[8], updated_at=r[9],
            )
            for r in rows
        ]

    def delete_agent_config(self, config_id: str) -> None:
        """Delete an agent configuration by ID."""
        self._conn.execute("DELETE FROM agent_configs WHERE id = ?", (config_id,))
        self._conn.commit()
