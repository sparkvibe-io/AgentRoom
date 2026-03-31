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
