# AgentRoom — Project Instructions

## What is AgentRoom?
Multi-agent collaboration platform. AI agents (Claude, GPT-4o, Gemini, Grok) work together in **Rooms** to research, debate, reach consensus, implement, and review — while users watch or participate.

## Tech Stack
- **Python 3.13** / **FastAPI** + **uvicorn** / **uv** (package manager)
- **Pydantic v2** (validation with `max_length`/`Field` constraints), **sse-starlette** (SSE streaming)
- **SQLite** (message broker + agent config storage, WAL mode) — stdlib, zero dependency
- **Provider SDKs**: `anthropic`, `openai` (+ OpenAI-compatible via base_url)
- **CLI**: `click` + `rich`
- **Web UI**: Alpine.js 3 + Tailwind CSS (both CDN, zero build step) — static files served by FastAPI
- **Lint/Type**: `ruff` (py313, line-length=100), `pyright` (strict mode) — both at 0 errors
- **Tests**: `pytest` + `pytest-asyncio` (auto mode) — 102 tests
- **Security**: `bandit` (low-only: assert guards), security headers middleware, input validation

## Project Structure
```
src/agentroom/
├── __init__.py          # Package root, __version__
├── __main__.py          # `python -m agentroom` entry
├── cli.py               # Click CLI: `agentroom start`
├── protocol/
│   ├── extensions.py    # A2A extension Pydantic models (phases, votes, reviews)
│   ├── models.py        # Core models: Message, AgentCard, RoomConfig, RoomState
│   └── agent_config.py  # AgentConfig model for persistent agent storage
├── broker/
│   └── queue.py         # SQLite FIFO message broker + agent config CRUD
├── agents/
│   ├── base.py          # AgentAdapter ABC (AsyncGenerator-based streaming)
│   ├── anthropic.py     # Claude adapter (API key)
│   ├── openai.py        # GPT-4o + OpenAI-compatible adapter (API key)
│   ├── ollama.py        # Ollama/LM Studio adapter (no key, OpenAI-compat)
│   └── cli.py           # CLI adapter (subprocess: claude, gemini, codex)
├── coordinator/
│   ├── room.py          # Room orchestration (lifecycle, turns, phases)
│   └── prompt_builder.py # Per-agent system prompt assembly
├── server/
│   ├── app.py           # FastAPI + WebSocket + security middleware + agent config API
│   └── static/          # Web UI (zero build step)
│       ├── index.html   # Alpine.js single-page app
│       ├── app.js       # Alpine.js store, API calls, WebSocket
│       └── styles.css   # Custom styles (Tailwind handles most)
└── context/             # (planned) Context management / compaction
docs/
├── SECURITY.md          # Security posture, protections, known limitations
└── specs/               # Design specs and implementation plans
tests/
├── unit/
│   ├── test_adapters.py     # 19 tests (Anthropic + OpenAI adapters, role mapping)
│   ├── test_broker.py       # 4 tests (SQLite broker)
│   ├── test_cli_adapter.py  # 12 tests (CLI subprocess adapter)
│   ├── test_ollama_adapter.py # 7 tests (Ollama/LM Studio adapter)
│   ├── test_agent_config.py # 7 tests (agent config CRUD + redaction)
│   ├── test_prompt_builder.py # 10 tests (prompt construction)
│   ├── test_protocol.py     # 8 tests (models, extensions, new fields)
│   ├── test_room.py         # 15 tests (room lifecycle, turns, streaming)
│   └── test_server.py       # 20 tests (REST endpoints, agent config, provider routing)
└── integration/             # (planned)
```

## Commands
```bash
uv sync                                  # Install dependencies
uv run python -m pytest tests/ -v        # Run tests (102 tests, all passing)
uv run ruff check src/ tests/            # Lint (0 errors)
uv run python -m pyright src/            # Type check strict (0 errors)
uv run bandit -r src/                    # Security scan (low-only: assert guards)
uv run agentroom start                   # Start server on http://127.0.0.1:4000
uv run agentroom start --port 8000 --reload  # Dev mode
```

**Important**: Use `uv run python -m pytest` (not `uv run pytest`) to avoid import resolution issues.

## Architecture
- **A2A Protocol**: Wire format for inter-agent messages. AgentRoom extensions (`agentroom/phase`, `agentroom/vote`, etc.) on A2A message metadata.
- **SQLite Broker**: Durable FIFO queue with cursor-based consumption per agent + agent config CRUD. WAL mode for concurrent reads. Parameterized SQL (no injection risk).
- **Room Coordinator**: Round-robin turns, phase management (OPEN → RESEARCHING → CONSENSUS → IMPLEMENTING → REVIEWING → DONE). Currently sequential — free-for-all parallel execution is the next priority.
- **Adapters**: Thin wrappers behind unified `AgentAdapter` ABC. Four adapter types: AnthropicAdapter (API), OpenAIAdapter (API), OllamaAdapter (local LLM, no key), CLIAdapter (subprocess: claude/gemini/codex). Streaming via `AsyncGenerator`.
- **Agent Integration**: Three first-class modes — API keys, CLI agents (subprocess), local LLMs (Ollama/LM Studio). API keys are NOT required.
- **Web UI**: Alpine.js + Tailwind (CDN). Static files served by FastAPI. Agent library + room chat in a single page.
- **Security**: Input validation (max_length on all fields), WebSocket payload validation, security headers middleware, operation timeouts, cryptographic room IDs. CLI adapter uses `create_subprocess_exec` (not shell) to prevent injection.

## Design Decisions
- DD-1: Hybrid ESB inside room / A2A between rooms
- DD-2: Rooms are A2A agents; inter-room = peer-to-peer
- DD-3: Core session = **Room**
- DD-4: Lead failure = passive-first 4-tier heartbeat + succession
- DD-6: Python + FastAPI (switched from TypeScript)
- Product name: **AgentRoom** (renamed from AgentTalk)

## Type System Notes
- All files use `from __future__ import annotations` for deferred evaluation
- Type-only imports go in `if TYPE_CHECKING:` blocks (enforced by ruff TC002/TC003)
- `AsyncGenerator[str]` (not `AsyncGenerator[str, None]`) — ruff UP043 enforces no default args
- Abstract `stream()` method must be `async def` with `yield ""` stub for pyright compatibility
- `cast("dict[str, Any]", ...)` with quoted type arg — ruff TC006 enforces quotes in cast()

## Current Status (v0.2-dev)
- ✅ Protocol models, SQLite broker, agent adapters (4 types), room coordinator, FastAPI server, CLI
- ✅ CLI adapter: claude, gemini, codex via subprocess — tested with real agents
- ✅ Ollama adapter: local LLMs, no API key required
- ✅ Agent config persistence: SQLite CRUD + REST API + key redaction
- ✅ Web UI: Alpine.js + Tailwind, agent library, room chat, thinking indicator
- ✅ 102 unit tests (all passing)
- ✅ Ruff lint: 0 errors | Pyright strict: 0 errors | Bandit: low-only (assert guards)
- ✅ Role mapping fix: multi-agent rooms correctly distinguish self vs other agents
- ❌ No free-for-all coordination (agents run sequentially, not in parallel) — **NEXT PRIORITY**
- ❌ No auto-trigger (user must click Run Round; should auto-respond after user message)
- ❌ No agent workspace (agents can't read/write files, execute code) — future
- ❌ Not tested with real API keys yet
- ❌ No authentication (all endpoints public)
- ❌ No consensus/voting logic in coordinator
- ❌ No context management / compaction
- ❌ No MCP server integration
- ❌ No cost tracking
- ❌ No rate limiting
- ❌ No A2A external facade (/.well-known/agent-card.json) — roadmap

## Next Priority: Free-for-All Coordination
The coordinator currently runs agents sequentially (round-robin). The next task is to redesign it for parallel, free-for-all execution:
1. After a user message, automatically trigger all agents concurrently (`asyncio.gather` / `create_task`)
2. First agent to finish posts first (first-come-first-serve)
3. User can send messages anytime (agents react to new context)
4. Remove "Next Turn" / "Run Round" buttons — single "Send" button only
5. Lead agent can optionally coordinate who responds
Design spec needed before implementation. See `docs/specs/` for prior specs.

## Key Design Docs
- `BRAINSTORM.md` — original design document (~1900+ lines)
- `docs/specs/2026-03-30-multi-mode-agent-integration-design.md` — CLI/Ollama adapter design
- `docs/specs/2026-03-30-web-ui-alpine-design.md` — Alpine.js web UI design
