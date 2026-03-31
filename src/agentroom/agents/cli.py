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
        # Gemini does not support --system-prompt; embed in the prompt
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
