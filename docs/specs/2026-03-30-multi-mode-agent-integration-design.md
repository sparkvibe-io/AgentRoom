# Multi-Mode Agent Integration Design

**Date:** 2026-03-30
**Status:** Approved
**Scope:** CLI adapter, local LLM support (Ollama/LM Studio), agent configuration storage

## Problem

AgentRoom only supports API-key-based agent integration. Users without API keys — those using CLI agents (claude, gemini, codex) or local LLMs (Ollama, LM Studio) — cannot use the platform. API keys must not be the only way to use agents.

## Design Principle

Three integration modes are first-class equals:

1. **API keys** — Anthropic, OpenAI (existing)
2. **CLI agents** — claude, gemini, codex via subprocess
3. **Local LLMs** — Ollama, LM Studio via OpenAI-compatible HTTP (no key)

The Room coordinator sees no difference between adapter types. All adapters implement the same `AgentAdapter` ABC.

## Architecture

### Adapter Hierarchy

```
AgentAdapter (ABC) — unchanged
├── AnthropicAdapter   — API key required (existing, role mapping fix)
├── OpenAIAdapter      — API key optional (existing, fix for local servers)
├── OllamaAdapter      — local LLMs, no key, OpenAI-compat protocol
└── CLIAdapter         — subprocess, print-mode-per-turn
```

### File Structure

```
src/agentroom/agents/
├── base.py              # AgentAdapter ABC (unchanged)
├── anthropic.py         # AnthropicAdapter (fix role mapping)
├── openai.py            # OpenAIAdapter (make api_key optional)
├── ollama.py            # OllamaAdapter — local LLMs, no key
└── cli.py               # CLIAdapter — subprocess, print-mode-per-turn
```

### Provider Routing

| `provider` value | Adapter | Key required? |
|---|---|---|
| `"anthropic"` | AnthropicAdapter | Yes |
| `"openai"` | OpenAIAdapter | Yes |
| `"openai-compat"` | OpenAIAdapter | Optional |
| `"ollama"` | OllamaAdapter | No |
| `"lmstudio"` | OllamaAdapter | No (different default base_url) |
| `"cli"` | CLIAdapter | No |

## CLIAdapter

Wraps any CLI agent that supports a non-interactive print mode.

### Configuration

```python
provider: "cli"
command: str          # "claude", "gemini", "codex"
cli_args: list[str]   # ["--model", "sonnet-4"]
```

### Command Construction

| CLI | Command |
|---|---|
| Claude | `claude -p --system-prompt "{system}" "{turn_message}"` |
| Gemini | `gemini -p "{turn_message}"` (system prompt embedded in prompt) |
| Codex | `codex exec "{turn_message}"` |

### Lifecycle

- `connect()` — validates command exists on PATH via `shutil.which()`, runs version check
- `generate(messages, system_prompt)` — builds command with flags, spawns via `asyncio.create_subprocess_exec()`, reads stdout, returns response string. Note: uses `create_subprocess_exec` (not `create_subprocess_shell`) to avoid shell injection — arguments are passed as a list, never interpolated into a shell string.
- `stream()` — same subprocess, reads stdout line-by-line, yields chunks
- `disconnect()` — no-op (no persistent process)

### Conversation History

Passed as part of the system prompt content. The `prompt_builder` already assembles room context — message history is included there. The CLI agent gets the full picture each turn, same as API agents.

### Timeout

Reuses existing room-level operation timeout (120s). Subprocess exceeding timeout is killed and raises an error.

### Error Handling

Non-zero exit code raises `RuntimeError` with stderr content. Adapter becomes unavailable; coordinator can skip or retry.

## OllamaAdapter

Thin specialization of the OpenAI-compatible path for local LLMs.

### Defaults

| Provider | Base URL | API Key |
|---|---|---|
| `"ollama"` | `http://localhost:11434/v1` | None (dummy string for SDK) |
| `"lmstudio"` | `http://localhost:1234/v1` | None (dummy string for SDK) |
| `"openai-compat"` | User-provided | Optional |

### Why Separate from OpenAIAdapter

- Cleaner defaults — users don't need to know base URLs or dummy key workarounds
- Health check uses Ollama's native `/api/tags` endpoint
- Future extensibility for Ollama-specific features (model pulling, GPU status)

### Changes to OpenAIAdapter

- `api_key` becomes truly optional in `connect()` — no raise when absent
- When no key provided, passes dummy string to satisfy SDK requirement
- `is_available()` uses simpler HTTP GET health check for local servers

## Agent Configuration Storage

### SQLite Table

```sql
CREATE TABLE agent_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    command TEXT,
    cli_args TEXT,
    base_url TEXT,
    api_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Stored in the same SQLite database as the message broker. API keys stored as plaintext for v1 — encryption at rest is a future hardening item. API keys are never returned in GET responses (redacted to last 4 chars).

### REST Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/agents` | List all saved agent configs |
| `POST` | `/api/agents` | Create a new agent config |
| `GET` | `/api/agents/{id}` | Get one agent config |
| `PUT` | `/api/agents/{id}` | Update an agent config |
| `DELETE` | `/api/agents/{id}` | Remove an agent config |
| `POST` | `/api/agents/{id}/test` | Test connectivity |

### Room Integration

`POST /api/rooms` accepts `agent_ids: list[str]` referencing saved configs. Server loads configs, builds adapters, starts the room. Inline agent definitions still supported for ad-hoc use.

## Bug Fix: Role Mapping

Both existing adapters use `msg.from_agent.startswith("@")` to determine assistant role. This breaks in multi-agent rooms where all agents use `@` names.

**Fix:** Pass adapter's own name into `_to_api_messages()`. Compare `msg.from_agent == self.name` for `"assistant"`, everything else is `"user"`.

## Changes Summary

### Modified Files

| File | Change |
|---|---|
| `protocol/models.py` | Add optional fields to AgentCard: `command`, `cli_args`, `base_url`. Add `AgentConfig` model. |
| `agents/anthropic.py` | Fix role mapping. |
| `agents/openai.py` | Fix role mapping. Make `api_key` optional. |
| `server/app.py` | Agent config CRUD endpoints. Update `_build_adapter()` routing. Accept `agent_ids` in room creation. |
| `broker/queue.py` | Add `agent_configs` table. CRUD methods for configs. |

### New Files

| File | Purpose |
|---|---|
| `agents/ollama.py` | OllamaAdapter |
| `agents/cli.py` | CLIAdapter |

### Unchanged

- `agents/base.py` — ABC stays as-is
- `coordinator/room.py` — transport-agnostic, no changes needed
- `coordinator/prompt_builder.py` — already produces system prompts CLI adapter needs
- `cli.py` — Click CLI unchanged
- `protocol/extensions.py` — untouched

### New Tests

| File | Coverage |
|---|---|
| `tests/unit/test_cli_adapter.py` | Subprocess mocking, timeout, error handling, command construction |
| `tests/unit/test_ollama_adapter.py` | Keyless connect, health check, default URLs |
| `tests/unit/test_agent_config.py` | CRUD operations, SQLite persistence, key redaction |
| `tests/unit/test_adapters.py` | Additional tests for role mapping fix |

## Known Limitations (v1)

- API keys stored as plaintext in SQLite (encryption at rest planned)
- CLI adapter spawns a new subprocess per turn (no persistent sessions)
- Gemini CLI does not support a separate `--system-prompt` flag; system prompt is embedded in the prompt text
- No auto-discovery of installed CLI agents; users configure them manually
