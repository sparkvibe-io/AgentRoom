# AgentRoom

Multi-agent collaboration platform — AI agents research, debate, reach consensus, and build together in **Rooms**, while you watch or participate.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-64%20passing-brightgreen.svg)]()
[![Ruff](https://img.shields.io/badge/ruff-0%20errors-brightgreen.svg)]()
[![Pyright](https://img.shields.io/badge/pyright%20strict-0%20errors-brightgreen.svg)]()
[![Bandit](https://img.shields.io/badge/bandit-0%20issues-brightgreen.svg)]()

## What is AgentRoom?

You post a problem to a room full of AI agents. They take turns through structured phases — researching, debating, implementing, and reviewing — collaboratively. You can watch in real-time or intervene at any point.

**Supported providers:** Anthropic (Claude), OpenAI (GPT-4o), and any OpenAI-compatible endpoint.

### How it works

1. **Create a Room** with a goal and a set of agents
2. Agents take turns through phases: **Research → Consensus → Implement → Review**
3. Watch the conversation in real-time via the web UI or WebSocket
4. Intervene anytime with your own messages

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Web UI /   │────▶│  FastAPI      │────▶│  Room         │
│  WebSocket  │◀────│  Server       │◀────│  Coordinator  │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                    ┌──────────────┐     ┌────────▼────────┐
                    │  SQLite      │◀───▶│  Agent Adapters │
                    │  Broker      │     │  (Claude, GPT…) │
                    └──────────────┘     └─────────────────┘
```

- **Room Coordinator** — Orchestrates agent turns, phase lifecycle, and message flow
- **SQLite Broker** — Durable FIFO message queue with per-agent cursor tracking (WAL mode)
- **Agent Adapters** — Thin wrappers around provider SDKs behind a unified `AgentAdapter` ABC
- **A2A Protocol** — Wire format for inter-agent messages with AgentRoom extension metadata

## Quick Start

### Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- API key for at least one provider (Anthropic or OpenAI)

### Install & Run

```bash
git clone https://github.com/sparkvibe-io/AgentRoom.git
cd AgentRoom
uv sync
```

Set your API keys:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

Start the server:

```bash
uv run agentroom start
# → http://127.0.0.1:4000
```

### CLI Options

```bash
uv run agentroom start --host 0.0.0.0 --port 8000   # Custom host/port
uv run agentroom start --reload                       # Auto-reload for development
uv run agentroom --version                            # Show version
```

## API

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/rooms` | Create a new room |
| `GET` | `/api/rooms` | List all rooms |
| `GET` | `/api/rooms/{id}` | Get room details |
| `GET` | `/api/rooms/{id}/messages` | Fetch message history |
| `POST` | `/api/rooms/{id}/message` | Send a user message |
| `POST` | `/api/rooms/{id}/turn` | Run a single agent turn |
| `POST` | `/api/rooms/{id}/round` | Run a full round (all agents) |
| `POST` | `/api/rooms/{id}/phase` | Transition to a new phase |

### WebSocket

Connect to `/ws/{room_id}` for real-time message streaming.

**Client → Server:**
```json
{ "type": "message", "content": "your message" }
{ "type": "turn", "agent": "@claude" }
{ "type": "round" }
```

### Example: Create a Room

```bash
curl -X POST http://127.0.0.1:4000/api/rooms \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Design a REST API for a todo app",
    "agents": [
      { "name": "@claude", "provider": "anthropic", "model": "claude-sonnet-4-20250514", "role": "coordinator" },
      { "name": "@gpt4o", "provider": "openai", "model": "gpt-4o", "role": "researcher" }
    ]
  }'
```

## Room Phases

| Phase | Description |
|-------|-------------|
| **OPEN** | Room created, agents joining |
| **RESEARCHING** | Information gathering, approach proposals |
| **CONSENSUS** | Evaluation and voting on proposals |
| **IMPLEMENTING** | Writing code and solutions |
| **REVIEWING** | Structured code/design review |
| **DONE** | Complete |

## Development

```bash
uv sync                                  # Install all dependencies
uv run python -m pytest tests/ -v        # Run 64 tests
uv run ruff check src/ tests/            # Lint (0 errors)
uv run python -m pyright src/            # Type check strict (0 errors)
uv run bandit -r src/                    # Security scan (0 issues)
uv run agentroom start --reload          # Dev server with auto-reload
```

> **Note**: Use `uv run python -m pytest` (not `uv run pytest`) to avoid import resolution issues.

## Project Structure

```
src/agentroom/
├── protocol/          # Core models + A2A extension metadata
│   ├── models.py      # Message, AgentCard, RoomConfig, RoomState
│   └── extensions.py  # Phase, Vote, Review, Cost extensions
├── broker/
│   └── queue.py       # SQLite FIFO message broker
├── agents/
│   ├── base.py        # AgentAdapter ABC
│   ├── anthropic.py   # Claude adapter
│   └── openai.py      # GPT-4o + OpenAI-compatible adapter
├── coordinator/
│   ├── room.py        # Room orchestration (lifecycle, turns, phases)
│   └── prompt_builder.py
├── server/
│   └── app.py         # FastAPI + WebSocket + security middleware + embedded web UI
├── context/           # (planned) Context management / compaction
└── cli.py             # Click CLI entry point

docs/
└── SECURITY.md        # Security posture and known limitations
tests/
└── unit/              # 64 tests (adapters, broker, protocol, room, server)
```

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for full details. Key protections:

- **Input validation** — `max_length` on all Pydantic fields, bounded query params
- **WebSocket hardening** — payload size limits, JSON schema validation
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- **Operation timeouts** — 120s per turn, 600s per round
- **Cryptographic room IDs** — `secrets.token_urlsafe(16)`
- **SQL injection prevention** — all queries parameterized
- **Error sanitization** — no internal state in error messages

## Roadmap

- [ ] Authentication and authorization
- [ ] Rate limiting
- [ ] Consensus/voting logic in room coordinator
- [ ] Context compaction for long conversations
- [ ] React web UI (replacing embedded HTML v1)
- [ ] MCP server integration
- [ ] Cost tracking per agent/room
- [ ] Lead agent failover (heartbeat)
- [ ] Inter-room communication (A2A peer-to-peer)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
