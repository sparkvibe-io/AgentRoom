# Multi-Mode Agent Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CLI agent and local LLM (Ollama/LM Studio) support so AgentRoom works without API keys, plus fix the role mapping bug in existing adapters.

**Architecture:** Three new adapter types behind the existing `AgentAdapter` ABC. CLIAdapter spawns subprocesses in print-mode-per-turn using `asyncio.create_subprocess_exec` (list-based args, no shell interpolation). OllamaAdapter wraps OpenAI-compatible local servers without requiring keys. Agent configs stored in SQLite, exposed via REST API. The Room coordinator remains unchanged — it only sees the ABC interface.

**Tech Stack:** Python 3.13, asyncio.create_subprocess_exec, shutil.which, OpenAI SDK (keyless), SQLite, FastAPI, Pydantic v2, pytest + pytest-asyncio

---

### Task 1: Fix Role Mapping Bug in Existing Adapters

**Files:**
- Modify: `src/agentroom/agents/anthropic.py:80-90`
- Modify: `src/agentroom/agents/openai.py:87-100`
- Modify: `tests/unit/test_adapters.py:103-113, 193-199`

- [ ] **Step 1: Write failing test for Anthropic multi-agent role mapping**

Add to `tests/unit/test_adapters.py` in the `TestAnthropicAdapter` class:

```python
def test_to_api_messages_multi_agent_role_mapping(self) -> None:
    """In a multi-agent room, only the adapter's own messages are 'assistant'."""
    messages = [
        Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
        Message(room_id="room1", from_agent="@claude", type=MessageType.TEXT, content="I think..."),
        Message(room_id="room1", from_agent="@gpt4o", type=MessageType.TEXT, content="I disagree..."),
    ]
    api_msgs = AnthropicAdapter._to_api_messages(messages, adapter_name="@claude")

    assert api_msgs[0]["role"] == "user"      # user -> user
    assert api_msgs[1]["role"] == "assistant"  # @claude (self) -> assistant
    assert api_msgs[2]["role"] == "user"       # @gpt4o (other agent) -> user
```

- [ ] **Step 2: Write failing test for OpenAI multi-agent role mapping**

Add to `tests/unit/test_adapters.py` in the `TestOpenAIAdapter` class:

```python
def test_to_api_messages_multi_agent_role_mapping(self) -> None:
    """In a multi-agent room, only the adapter's own messages are 'assistant'."""
    messages = [
        Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
        Message(room_id="room1", from_agent="@gpt4o", type=MessageType.TEXT, content="I think..."),
        Message(room_id="room1", from_agent="@claude", type=MessageType.TEXT, content="I disagree..."),
    ]
    api_msgs = OpenAIAdapter._to_api_messages(messages, "sys", adapter_name="@gpt4o")

    assert api_msgs[1]["role"] == "user"       # user -> user
    assert api_msgs[2]["role"] == "assistant"   # @gpt4o (self) -> assistant
    assert api_msgs[3]["role"] == "user"        # @claude (other agent) -> user
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_adapters.py::TestAnthropicAdapter::test_to_api_messages_multi_agent_role_mapping tests/unit/test_adapters.py::TestOpenAIAdapter::test_to_api_messages_multi_agent_role_mapping -v`
Expected: FAIL -- `_to_api_messages` doesn't accept `adapter_name` parameter yet.

- [ ] **Step 4: Fix AnthropicAdapter role mapping**

In `src/agentroom/agents/anthropic.py`, change `_to_api_messages` from a static method to accept `adapter_name`:

```python
@staticmethod
def _to_api_messages(
    messages: list[Message], adapter_name: str = ""
) -> list[anthropic.types.MessageParam]:
    """Convert room messages to Anthropic API format."""
    api_msgs: list[anthropic.types.MessageParam] = []
    for msg in messages:
        role: anthropic.types.MessageParam = {  # type: ignore[assignment]
            "role": "assistant" if msg.from_agent == adapter_name else "user",
            "content": msg.content,
        }
        api_msgs.append(role)
    return api_msgs
```

Update the callers in `generate()` (line 53) and `stream()` (line 70):

```python
api_messages = self._to_api_messages(messages, adapter_name=self.name)
```

- [ ] **Step 5: Fix OpenAIAdapter role mapping**

In `src/agentroom/agents/openai.py`, change `_to_api_messages`:

```python
@staticmethod
def _to_api_messages(
    messages: list[Message], system_prompt: str, adapter_name: str = ""
) -> list[ChatCompletionMessageParam]:
    """Convert room messages to OpenAI chat format."""
    api_msgs: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]
    for msg in messages:
        if msg.from_agent == adapter_name:
            api_msgs.append({"role": "assistant", "content": msg.content})
        else:
            api_msgs.append({"role": "user", "content": msg.content})
    return api_msgs
```

Update the callers in `generate()` (line 61) and `stream()` (line 76):

```python
api_messages = self._to_api_messages(messages, system_prompt, adapter_name=self.name)
```

- [ ] **Step 6: Update existing role mapping tests**

Update the existing `test_to_api_messages_role_mapping` tests to pass the new `adapter_name` parameter:

In `TestAnthropicAdapter`:
```python
def test_to_api_messages_role_mapping(self) -> None:
    messages = _make_messages()
    api_msgs = AnthropicAdapter._to_api_messages(messages, adapter_name="@claude")

    assert len(api_msgs) == 2
    assert api_msgs[0]["role"] == "user"
    assert api_msgs[0]["content"] == "Hello"
    assert api_msgs[1]["role"] == "assistant"
    assert api_msgs[1]["content"] == "Hi there!"
```

In `TestOpenAIAdapter`:
```python
def test_to_api_messages_role_mapping(self) -> None:
    messages = _make_messages()
    api_msgs = OpenAIAdapter._to_api_messages(messages, "sys", adapter_name="@claude")

    assert api_msgs[1]["role"] == "user"
    assert api_msgs[2]["role"] == "assistant"
```

- [ ] **Step 7: Run all adapter tests**

Run: `uv run python -m pytest tests/unit/test_adapters.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run full test suite to check for regressions**

Run: `uv run python -m pytest tests/ -v`
Expected: All 64 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/agentroom/agents/anthropic.py src/agentroom/agents/openai.py tests/unit/test_adapters.py
git commit -m "fix: role mapping uses adapter name instead of @ prefix for multi-agent rooms"
```

---

### Task 2: Add Optional Fields to AgentCard

**Files:**
- Modify: `src/agentroom/protocol/models.py:45-53`
- Modify: `tests/unit/test_protocol.py`

- [ ] **Step 1: Write failing test for new AgentCard fields**

Add to `tests/unit/test_protocol.py`:

```python
def test_agent_card_cli_fields() -> None:
    card = AgentCard(
        name="@claude-cli",
        provider="cli",
        model="sonnet-4",
        command="claude",
        cli_args=["--model", "sonnet-4"],
    )
    assert card.command == "claude"
    assert card.cli_args == ["--model", "sonnet-4"]
    assert card.base_url is None
    assert card.api_key is None


def test_agent_card_ollama_fields() -> None:
    card = AgentCard(
        name="@llama",
        provider="ollama",
        model="llama3",
        base_url="http://localhost:11434/v1",
    )
    assert card.base_url == "http://localhost:11434/v1"
    assert card.command is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_protocol.py::test_agent_card_cli_fields tests/unit/test_protocol.py::test_agent_card_ollama_fields -v`
Expected: FAIL -- AgentCard doesn't have `command`, `cli_args`, `base_url`, `api_key` fields.

- [ ] **Step 3: Add optional fields to AgentCard**

In `src/agentroom/protocol/models.py`, update the `AgentCard` class:

```python
class AgentCard(BaseModel):
    """Describes an agent's identity and capabilities."""

    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    role: AgentRole = AgentRole.RESEARCHER
    description: str = Field(default="", max_length=1000)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    # CLI adapter fields
    command: str | None = Field(default=None, max_length=200)
    cli_args: list[str] = Field(default_factory=list, max_length=50)
    # Local LLM / OpenAI-compat fields
    base_url: str | None = Field(default=None, max_length=500)
    # API key (optional -- not needed for CLI or local LLMs)
    api_key: str | None = Field(default=None, max_length=500)
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest tests/unit/test_protocol.py -v`
Expected: All PASS

- [ ] **Step 5: Run type checker**

Run: `uv run python -m pyright src/agentroom/protocol/models.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add src/agentroom/protocol/models.py tests/unit/test_protocol.py
git commit -m "feat: add optional CLI, base_url, and api_key fields to AgentCard"
```

---

### Task 3: Implement OllamaAdapter

**Files:**
- Create: `src/agentroom/agents/ollama.py`
- Create: `tests/unit/test_ollama_adapter.py`

- [ ] **Step 1: Write failing tests for OllamaAdapter**

Create `tests/unit/test_ollama_adapter.py`:

```python
"""Tests for Ollama adapter -- local LLMs, no API key."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentroom.agents.ollama import OllamaAdapter
from agentroom.protocol.extensions import AgentRole
from agentroom.protocol.models import AgentCard, Message, MessageType


def _make_card(
    name: str = "@llama", model: str = "llama3", provider: str = "ollama"
) -> AgentCard:
    return AgentCard(name=name, provider=provider, model=model, role=AgentRole.RESEARCHER)


def _make_messages() -> list[Message]:
    return [
        Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
        Message(room_id="room1", from_agent="@llama", type=MessageType.TEXT, content="Hi!"),
    ]


class TestOllamaAdapter:
    def test_default_base_url_ollama(self) -> None:
        card = _make_card(provider="ollama")
        adapter = OllamaAdapter(card)
        assert adapter._base_url == "http://localhost:11434/v1"

    def test_default_base_url_lmstudio(self) -> None:
        card = _make_card(provider="lmstudio")
        adapter = OllamaAdapter(card, provider_type="lmstudio")
        assert adapter._base_url == "http://localhost:1234/v1"

    def test_custom_base_url(self) -> None:
        card = _make_card()
        card.base_url = "http://custom:9999/v1"
        adapter = OllamaAdapter(card)
        assert adapter._base_url == "http://custom:9999/v1"

    @pytest.mark.asyncio
    async def test_connect_no_key_required(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()
        assert adapter._client is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_generate(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()

        mock_message = MagicMock()
        mock_message.content = "Ollama response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)  # type: ignore[union-attr]

        result = await adapter.generate(_make_messages(), "system prompt")
        assert result == "Ollama response"
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_clears_client(self) -> None:
        card = _make_card()
        adapter = OllamaAdapter(card)
        await adapter.connect()
        await adapter.disconnect()
        assert adapter._client is None

    def test_role_mapping_uses_adapter_name(self) -> None:
        messages = [
            Message(room_id="r", from_agent="user", type=MessageType.TEXT, content="Hi"),
            Message(room_id="r", from_agent="@llama", type=MessageType.TEXT, content="Hello"),
            Message(room_id="r", from_agent="@claude", type=MessageType.TEXT, content="Hey"),
        ]
        card = _make_card(name="@llama")
        adapter = OllamaAdapter(card)
        api_msgs = adapter._to_api_messages(messages, "sys", adapter_name="@llama")

        assert api_msgs[0]["role"] == "system"
        assert api_msgs[1]["role"] == "user"       # user
        assert api_msgs[2]["role"] == "assistant"   # @llama (self)
        assert api_msgs[3]["role"] == "user"        # @claude (other)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_ollama_adapter.py -v`
Expected: FAIL -- `agentroom.agents.ollama` module doesn't exist.

- [ ] **Step 3: Implement OllamaAdapter**

Create `src/agentroom/agents/ollama.py`:

```python
"""Ollama adapter -- local LLMs via OpenAI-compatible API, no key required."""

from __future__ import annotations

from typing import TYPE_CHECKING

import openai

from agentroom.agents.base import AgentAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from openai.types.chat import ChatCompletionMessageParam

    from agentroom.protocol.models import AgentCard, Message

_DEFAULT_URLS: dict[str, str] = {
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}


class OllamaAdapter(AgentAdapter):
    """Adapter for local LLMs via Ollama, LM Studio, or any OpenAI-compatible server."""

    def __init__(
        self,
        card: AgentCard,
        provider_type: str = "ollama",
    ) -> None:
        super().__init__(card, api_key=None)
        self._base_url = card.base_url or _DEFAULT_URLS.get(provider_type, _DEFAULT_URLS["ollama"])
        self._client: openai.AsyncOpenAI | None = None

    async def connect(self) -> None:
        self._client = openai.AsyncOpenAI(
            api_key="not-needed",
            base_url=self._base_url,
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def is_available(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def generate(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> str:
        if not self._client:
            raise RuntimeError("Adapter not connected -- call connect() first")

        api_messages = self._to_api_messages(messages, system_prompt, adapter_name=self.name)
        response = await self._client.chat.completions.create(
            model=self.card.model,
            messages=api_messages,
        )
        return response.choices[0].message.content or ""

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> AsyncGenerator[str]:
        if not self._client:
            raise RuntimeError("Adapter not connected -- call connect() first")

        api_messages = self._to_api_messages(messages, system_prompt, adapter_name=self.name)
        stream = await self._client.chat.completions.create(
            model=self.card.model,
            messages=api_messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _to_api_messages(
        messages: list[Message], system_prompt: str, adapter_name: str = ""
    ) -> list[ChatCompletionMessageParam]:
        """Convert room messages to OpenAI chat format."""
        api_msgs: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in messages:
            if msg.from_agent == adapter_name:
                api_msgs.append({"role": "assistant", "content": msg.content})
            else:
                api_msgs.append({"role": "user", "content": msg.content})
        return api_msgs
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest tests/unit/test_ollama_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Run type checker and linter**

Run: `uv run python -m pyright src/agentroom/agents/ollama.py && uv run ruff check src/agentroom/agents/ollama.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add src/agentroom/agents/ollama.py tests/unit/test_ollama_adapter.py
git commit -m "feat: add OllamaAdapter for local LLMs (Ollama, LM Studio) -- no API key required"
```

---

### Task 4: Implement CLIAdapter

**Files:**
- Create: `src/agentroom/agents/cli.py`
- Create: `tests/unit/test_cli_adapter.py`

- [ ] **Step 1: Write failing tests for CLIAdapter**

Create `tests/unit/test_cli_adapter.py`:

```python
"""Tests for CLI adapter -- subprocess-based agents."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agentroom.agents.cli import CLIAdapter
from agentroom.protocol.extensions import AgentRole
from agentroom.protocol.models import AgentCard, Message, MessageType


def _make_card(
    name: str = "@claude-cli",
    command: str = "claude",
    cli_args: list[str] | None = None,
) -> AgentCard:
    return AgentCard(
        name=name,
        provider="cli",
        model="sonnet-4",
        role=AgentRole.RESEARCHER,
        command=command,
        cli_args=cli_args or [],
    )


def _make_messages() -> list[Message]:
    return [
        Message(room_id="room1", from_agent="user", type=MessageType.TEXT, content="Hello"),
    ]


class TestCLIAdapter:
    def test_adapter_name(self) -> None:
        card = _make_card(name="@my-claude")
        adapter = CLIAdapter(card)
        assert adapter.name == "@my-claude"

    @pytest.mark.asyncio
    async def test_connect_validates_command_exists(self) -> None:
        card = _make_card(command="claude")
        adapter = CLIAdapter(card)
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            await adapter.connect()
            assert adapter._command_path == "/usr/local/bin/claude"

    @pytest.mark.asyncio
    async def test_connect_fails_for_missing_command(self) -> None:
        card = _make_card(command="nonexistent-tool")
        adapter = CLIAdapter(card)
        with patch("shutil.which", return_value=None), pytest.raises(
            ValueError, match="not found on PATH"
        ):
            await adapter.connect()

    @pytest.mark.asyncio
    async def test_generate_claude(self) -> None:
        card = _make_card(command="claude")
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/claude"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Claude response here", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_run:
            result = await adapter.generate(_make_messages(), "You are helpful")
            assert result == "Claude response here"
            # Verify claude is called with -p flag
            call_args = mock_run.call_args[0]
            assert call_args[0] == "/usr/local/bin/claude"
            assert "-p" in call_args

    @pytest.mark.asyncio
    async def test_generate_gemini(self) -> None:
        card = _make_card(name="@gemini-cli", command="gemini")
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/gemini"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Gemini response", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_run:
            result = await adapter.generate(_make_messages(), "You are helpful")
            assert result == "Gemini response"
            call_args = mock_run.call_args[0]
            assert call_args[0] == "/usr/local/bin/gemini"
            assert "-p" in call_args

    @pytest.mark.asyncio
    async def test_generate_codex(self) -> None:
        card = _make_card(name="@codex-cli", command="codex")
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/codex"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Codex response", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_run:
            result = await adapter.generate(_make_messages(), "You are helpful")
            assert result == "Codex response"
            call_args = mock_run.call_args[0]
            assert call_args[0] == "/usr/local/bin/codex"
            assert "exec" in call_args

    @pytest.mark.asyncio
    async def test_generate_nonzero_exit_raises(self) -> None:
        card = _make_card(command="claude")
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/claude"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Error: something broke"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), pytest.raises(
            RuntimeError, match="something broke"
        ):
            await adapter.generate(_make_messages(), "system")

    @pytest.mark.asyncio
    async def test_generate_timeout(self) -> None:
        card = _make_card(command="claude")
        adapter = CLIAdapter(card, timeout=0.01)
        adapter._command_path = "/usr/local/bin/claude"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError)
        mock_proc.kill = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), pytest.raises(
            TimeoutError
        ):
            await adapter.generate(_make_messages(), "system")

    @pytest.mark.asyncio
    async def test_generate_with_cli_args(self) -> None:
        card = _make_card(command="claude", cli_args=["--model", "opus-4"])
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/claude"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_run:
            await adapter.generate(_make_messages(), "system")
            call_args = mock_run.call_args[0]
            assert "--model" in call_args
            assert "opus-4" in call_args

    @pytest.mark.asyncio
    async def test_disconnect_is_noop(self) -> None:
        card = _make_card()
        adapter = CLIAdapter(card)
        await adapter.disconnect()  # should not raise

    @pytest.mark.asyncio
    async def test_is_available_when_connected(self) -> None:
        card = _make_card()
        adapter = CLIAdapter(card)
        adapter._command_path = "/usr/local/bin/claude"
        assert await adapter.is_available()

    @pytest.mark.asyncio
    async def test_is_available_when_not_connected(self) -> None:
        card = _make_card()
        adapter = CLIAdapter(card)
        assert not await adapter.is_available()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_cli_adapter.py -v`
Expected: FAIL -- `agentroom.agents.cli` module doesn't exist.

- [ ] **Step 3: Implement CLIAdapter**

Create `src/agentroom/agents/cli.py`.

NOTE: This adapter uses `asyncio.create_subprocess_exec` (not `create_subprocess_shell`) to prevent command injection. All arguments are passed as a list, never interpolated into a shell string.

```python
"""CLI adapter -- runs agents as subprocesses in print-mode-per-turn."""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING

from agentroom.agents.base import AgentAdapter

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agentroom.protocol.models import AgentCard, Message


def _build_command(
    command_path: str,
    command_name: str,
    prompt: str,
    system_prompt: str,
    cli_args: list[str],
) -> list[str]:
    """Build the subprocess argument list based on the CLI tool.

    All arguments are passed as list elements to create_subprocess_exec,
    which does not invoke a shell -- preventing command injection.
    """
    base_name = command_name.lower()

    if base_name == "claude":
        cmd = [command_path, "-p", "--system-prompt", system_prompt, *cli_args, prompt]
    elif base_name == "gemini":
        # Gemini doesn't support --system-prompt; embed in the prompt
        combined = f"System instructions: {system_prompt}\n\n{prompt}"
        cmd = [command_path, "-p", combined, *cli_args]
    elif base_name == "codex":
        cmd = [command_path, "exec", *cli_args, prompt]
    else:
        # Generic: assume -p flag for print mode
        cmd = [command_path, "-p", *cli_args, prompt]

    return cmd


class CLIAdapter(AgentAdapter):
    """Adapter that runs CLI agents as subprocesses.

    Supports claude, gemini, codex, and any CLI with a print/non-interactive mode.
    Each call to generate() spawns a fresh subprocess -- no persistent process.
    """

    def __init__(
        self,
        card: AgentCard,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(card, api_key=None)
        self._command = card.command or card.provider
        self._cli_args = list(card.cli_args)
        self._timeout = timeout
        self._command_path: str | None = None

    async def connect(self) -> None:
        """Validate that the CLI command exists on PATH."""
        path = shutil.which(self._command)
        if not path:
            raise ValueError(f"CLI command '{self._command}' not found on PATH")
        self._command_path = path

    async def disconnect(self) -> None:
        """No-op -- no persistent process to clean up."""
        self._command_path = None

    async def is_available(self) -> bool:
        return self._command_path is not None

    async def generate(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> str:
        if not self._command_path:
            raise RuntimeError("Adapter not connected -- call connect() first")

        prompt = self._format_prompt(messages)
        cmd = _build_command(
            self._command_path, self._command, prompt, system_prompt, self._cli_args
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except TimeoutError:
            proc.kill()
            raise

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise RuntimeError(f"CLI agent exited with code {proc.returncode}: {error_msg}")

        return stdout.decode().strip()

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> AsyncGenerator[str]:
        if not self._command_path:
            raise RuntimeError("Adapter not connected -- call connect() first")

        prompt = self._format_prompt(messages)
        cmd = _build_command(
            self._command_path, self._command, prompt, system_prompt, self._cli_args
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if proc.stdout:
            async for line in proc.stdout:
                yield line.decode()

        await proc.wait()

    @staticmethod
    def _format_prompt(messages: list[Message]) -> str:
        """Format conversation history into a single prompt string."""
        if not messages:
            return ""

        lines: list[str] = []
        for msg in messages:
            lines.append(f"[{msg.from_agent}]: {msg.content}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest tests/unit/test_cli_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Run type checker and linter**

Run: `uv run python -m pyright src/agentroom/agents/cli.py && uv run ruff check src/agentroom/agents/cli.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add src/agentroom/agents/cli.py tests/unit/test_cli_adapter.py
git commit -m "feat: add CLIAdapter for subprocess-based agents (claude, gemini, codex)"
```

---

### Task 5: Add Agent Config Storage to Broker

**Files:**
- Modify: `src/agentroom/broker/queue.py:15-35, 44-50`
- Create: `src/agentroom/protocol/agent_config.py`
- Create: `tests/unit/test_agent_config.py`

- [ ] **Step 1: Write the AgentConfig Pydantic model**

Create `src/agentroom/protocol/agent_config.py`:

```python
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
```

- [ ] **Step 2: Write failing tests for agent config storage**

Create `tests/unit/test_agent_config.py`:

```python
"""Tests for agent config CRUD in the broker."""

from __future__ import annotations

import pytest

from agentroom.broker.queue import MessageBroker
from agentroom.protocol.agent_config import AgentConfig


@pytest.fixture
def broker() -> MessageBroker:
    return MessageBroker()


class TestAgentConfigCRUD:
    def test_save_and_get(self, broker: MessageBroker) -> None:
        config = AgentConfig(
            name="@claude-cli",
            provider="cli",
            model="sonnet-4",
            command="claude",
        )
        broker.save_agent_config(config)
        loaded = broker.get_agent_config(config.id)
        assert loaded is not None
        assert loaded.name == "@claude-cli"
        assert loaded.provider == "cli"
        assert loaded.command == "claude"

    def test_list_configs(self, broker: MessageBroker) -> None:
        c1 = AgentConfig(name="@a1", provider="cli", model="m1", command="claude")
        c2 = AgentConfig(name="@a2", provider="ollama", model="llama3")
        broker.save_agent_config(c1)
        broker.save_agent_config(c2)
        configs = broker.list_agent_configs()
        assert len(configs) == 2

    def test_update_config(self, broker: MessageBroker) -> None:
        config = AgentConfig(name="@old", provider="cli", model="m1", command="claude")
        broker.save_agent_config(config)
        config.name = "@new"
        broker.save_agent_config(config)
        loaded = broker.get_agent_config(config.id)
        assert loaded is not None
        assert loaded.name == "@new"

    def test_delete_config(self, broker: MessageBroker) -> None:
        config = AgentConfig(name="@del", provider="cli", model="m1", command="claude")
        broker.save_agent_config(config)
        broker.delete_agent_config(config.id)
        assert broker.get_agent_config(config.id) is None

    def test_get_nonexistent_returns_none(self, broker: MessageBroker) -> None:
        assert broker.get_agent_config("nonexistent") is None

    def test_redacted_api_key(self) -> None:
        config = AgentConfig(
            name="@gpt", provider="openai", model="gpt-4o", api_key="sk-abc123xyz789"
        )
        redacted = config.redacted()
        assert redacted.api_key == "...z789"
        assert config.api_key == "sk-abc123xyz789"  # original unchanged

    def test_redacted_no_api_key(self) -> None:
        config = AgentConfig(name="@llama", provider="ollama", model="llama3")
        redacted = config.redacted()
        assert redacted.api_key is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_agent_config.py -v`
Expected: FAIL -- `save_agent_config` method doesn't exist on MessageBroker.

- [ ] **Step 4: Add agent_configs table and CRUD methods to broker**

In `src/agentroom/broker/queue.py`, add to `_SCHEMA` string after the `CREATE INDEX` line:

```sql

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
```

Add the import at top of file (alongside existing imports):

```python
from agentroom.protocol.agent_config import AgentConfig
```

Add CRUD methods to `MessageBroker` class after the `_get_cursor` method:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `uv run python -m pytest tests/unit/test_agent_config.py -v`
Expected: All PASS

- [ ] **Step 6: Run type checker and linter**

Run: `uv run python -m pyright src/agentroom/broker/queue.py src/agentroom/protocol/agent_config.py && uv run ruff check src/agentroom/broker/queue.py src/agentroom/protocol/agent_config.py`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add src/agentroom/protocol/agent_config.py src/agentroom/broker/queue.py tests/unit/test_agent_config.py
git commit -m "feat: add agent config persistence -- SQLite CRUD for saved agent configurations"
```

---

### Task 6: Update Server -- Provider Routing and Agent Config Endpoints

**Files:**
- Modify: `src/agentroom/server/app.py:16-17, 60-68, 109-137`
- Modify: `tests/unit/test_server.py`

- [ ] **Step 1: Write failing tests for new provider routing**

Add to `tests/unit/test_server.py`:

```python
@pytest.mark.asyncio
async def test_create_room_with_cli_provider(client: AsyncClient) -> None:
    with patch("agentroom.server.app.CLIAdapter") as mock_cli:
        instance = AsyncMock()
        instance.name = "@claude-cli"
        mock_cli.return_value = instance

        resp = await client.post("/api/rooms", json={
            "goal": "CLI test",
            "agents": [
                {"name": "@claude-cli", "provider": "cli", "model": "sonnet-4", "command": "claude"},
            ],
        })
        assert resp.status_code == 200
        assert "@claude-cli" in resp.json()["agents"]


@pytest.mark.asyncio
async def test_create_room_with_ollama_provider(client: AsyncClient) -> None:
    with patch("agentroom.server.app.OllamaAdapter") as mock_ollama:
        instance = AsyncMock()
        instance.name = "@llama"
        mock_ollama.return_value = instance

        resp = await client.post("/api/rooms", json={
            "goal": "Ollama test",
            "agents": [
                {"name": "@llama", "provider": "ollama", "model": "llama3"},
            ],
        })
        assert resp.status_code == 200
        assert "@llama" in resp.json()["agents"]
```

- [ ] **Step 2: Write failing tests for agent config CRUD endpoints**

Add to `tests/unit/test_server.py`:

```python
@pytest.mark.asyncio
async def test_create_agent_config(client: AsyncClient) -> None:
    resp = await client.post("/api/agents", json={
        "name": "@claude-cli",
        "provider": "cli",
        "model": "sonnet-4",
        "command": "claude",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "@claude-cli"
    assert data["api_key"] is None  # no key, no redaction needed


@pytest.mark.asyncio
async def test_list_agent_configs(client: AsyncClient) -> None:
    await client.post("/api/agents", json={
        "name": "@a1", "provider": "cli", "model": "m1", "command": "claude",
    })
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_agent_config(client: AsyncClient) -> None:
    create_resp = await client.post("/api/agents", json={
        "name": "@a1", "provider": "cli", "model": "m1", "command": "claude",
    })
    agent_id = create_resp.json()["id"]
    resp = await client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "@a1"


@pytest.mark.asyncio
async def test_delete_agent_config(client: AsyncClient) -> None:
    create_resp = await client.post("/api/agents", json={
        "name": "@del", "provider": "cli", "model": "m1", "command": "claude",
    })
    agent_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    # Verify deleted
    resp = await client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_config_redacts_api_key(client: AsyncClient) -> None:
    await client.post("/api/agents", json={
        "name": "@gpt", "provider": "openai", "model": "gpt-4o", "api_key": "sk-abc123xyz789",
    })
    resp = await client.get("/api/agents")
    agents = resp.json()
    gpt_agent = next(a for a in agents if a["name"] == "@gpt")
    assert gpt_agent["api_key"] == "...z789"


@pytest.mark.asyncio
async def test_test_agent_connectivity(client: AsyncClient) -> None:
    with patch("agentroom.server.app._build_adapter") as mock_build:
        instance = AsyncMock()
        instance.is_available = AsyncMock(return_value=True)
        mock_build.return_value = instance

        create_resp = await client.post("/api/agents", json={
            "name": "@claude-cli", "provider": "cli", "model": "sonnet-4", "command": "claude",
        })
        agent_id = create_resp.json()["id"]
        resp = await client.post(f"/api/agents/{agent_id}/test")
        assert resp.status_code == 200
        assert resp.json()["available"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run python -m pytest tests/unit/test_server.py::test_create_room_with_cli_provider tests/unit/test_server.py::test_create_agent_config -v`
Expected: FAIL

- [ ] **Step 4: Update imports and provider routing in app.py**

At the top of `src/agentroom/server/app.py`, add imports after existing adapter imports:

```python
from agentroom.agents.cli import CLIAdapter
from agentroom.agents.ollama import OllamaAdapter
from agentroom.protocol.agent_config import AgentConfig
```

Update `_build_adapter` function to replace the existing one:

```python
def _build_adapter(card: AgentCard) -> AgentAdapter:
    """Create the right adapter based on provider name."""
    match card.provider:
        case "anthropic":
            return AnthropicAdapter(card, api_key=card.api_key)
        case "openai":
            return OpenAIAdapter(card, api_key=card.api_key)
        case "openai-compat":
            return OpenAIAdapter(card, api_key=card.api_key, base_url=card.base_url)
        case "ollama":
            return OllamaAdapter(card, provider_type="ollama")
        case "lmstudio":
            return OllamaAdapter(card, provider_type="lmstudio")
        case "cli":
            return CLIAdapter(card)
        case _:
            raise ValueError("Unsupported agent provider")
```

- [ ] **Step 5: Add a shared broker for agent config storage**

In `app.py`, add a module-level config broker alongside the existing `_rooms` dict:

```python
_config_broker: MessageBroker | None = None
```

Update `_lifespan` to initialize and clean up:

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _config_broker  # noqa: PLW0603
    _config_broker = MessageBroker()
    yield
    for room in _rooms.values():
        await room.stop()
    _config_broker.close()
```

- [ ] **Step 6: Add agent config request model and CRUD endpoints**

Add the request model alongside existing request models:

```python
class CreateAgentConfigRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    command: str | None = Field(default=None, max_length=200)
    cli_args: list[str] = Field(default_factory=list, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
```

Add inside `create_app()`, after existing room routes but before the WebSocket endpoint:

```python
# --- Agent Config CRUD ---

@app.post("/api/agents")
async def create_agent_config(req: CreateAgentConfigRequest) -> dict[str, Any]:
    assert _config_broker is not None
    config = AgentConfig(
        name=req.name,
        provider=req.provider,
        model=req.model,
        command=req.command,
        cli_args=req.cli_args,
        base_url=req.base_url,
        api_key=req.api_key,
    )
    _config_broker.save_agent_config(config)
    return config.redacted().model_dump()

@app.get("/api/agents")
async def list_agent_configs() -> list[dict[str, Any]]:
    assert _config_broker is not None
    configs = _config_broker.list_agent_configs()
    return [c.redacted().model_dump() for c in configs]

@app.get("/api/agents/{agent_id}")
async def get_agent_config(agent_id: str) -> dict[str, Any]:
    assert _config_broker is not None
    config = _config_broker.get_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    return config.redacted().model_dump()

@app.put("/api/agents/{agent_id}")
async def update_agent_config(
    agent_id: str, req: CreateAgentConfigRequest
) -> dict[str, Any]:
    assert _config_broker is not None
    existing = _config_broker.get_agent_config(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent config not found")
    import time as _time
    updated = existing.model_copy(update={
        "name": req.name,
        "provider": req.provider,
        "model": req.model,
        "command": req.command,
        "cli_args": req.cli_args,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "updated_at": _time.time(),
    })
    _config_broker.save_agent_config(updated)
    return updated.redacted().model_dump()

@app.delete("/api/agents/{agent_id}")
async def delete_agent_config(agent_id: str) -> dict[str, str]:
    assert _config_broker is not None
    _config_broker.delete_agent_config(agent_id)
    return {"status": "deleted"}

@app.post("/api/agents/{agent_id}/test")
async def test_agent_connectivity(agent_id: str) -> dict[str, Any]:
    assert _config_broker is not None
    config = _config_broker.get_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    card = AgentCard(
        name=config.name,
        provider=config.provider,
        model=config.model,
        command=config.command,
        cli_args=config.cli_args,
        base_url=config.base_url,
        api_key=config.api_key,
    )
    adapter = _build_adapter(card)
    try:
        await adapter.connect()
        available = await adapter.is_available()
        await adapter.disconnect()
    except Exception as e:
        return {"available": False, "error": str(e)}
    return {"available": available}
```

- [ ] **Step 7: Run new server tests**

Run: `uv run python -m pytest tests/unit/test_server.py -v`
Expected: All PASS (old + new)

- [ ] **Step 8: Run type checker and linter**

Run: `uv run python -m pyright src/agentroom/server/app.py && uv run ruff check src/agentroom/server/app.py`
Expected: 0 errors

- [ ] **Step 9: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add src/agentroom/server/app.py tests/unit/test_server.py
git commit -m "feat: add CLI/Ollama provider routing and agent config CRUD endpoints"
```

---

### Task 7: Fix Weak Test Assertion

**Files:**
- Modify: `tests/unit/test_server.py:118-124`

- [ ] **Step 1: Fix the assertion**

In `tests/unit/test_server.py`, update `test_create_room_empty_agents`:

```python
@pytest.mark.asyncio
async def test_create_room_empty_agents(client: AsyncClient) -> None:
    resp = await client.post("/api/rooms", json={
        "goal": "Test",
        "agents": [],
    })
    assert resp.status_code == 422  # Pydantic min_length=1 rejects empty list
```

- [ ] **Step 2: Run the test**

Run: `uv run python -m pytest tests/unit/test_server.py::test_create_room_empty_agents -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_server.py
git commit -m "fix: assert exact 422 status for empty agents list"
```

---

### Task 8: Final Verification

**Files:** None -- verification only.

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS (64 original + new tests)

- [ ] **Step 2: Run linter**

Run: `uv run ruff check src/ tests/`
Expected: 0 errors

- [ ] **Step 3: Run type checker**

Run: `uv run python -m pyright src/`
Expected: 0 errors

- [ ] **Step 4: Run security scan**

Run: `uv run bandit -r src/`
Expected: 0 issues

- [ ] **Step 5: Verify new adapter count**

Run: `uv run python -c "from agentroom.agents.cli import CLIAdapter; from agentroom.agents.ollama import OllamaAdapter; print('All adapters importable')"`
Expected: "All adapters importable"
