"""CLI entry point — `agentroom start`, `agentroom room create`, etc."""

from __future__ import annotations

import click
import uvicorn


@click.group()
@click.version_option(package_name="agentroom")
def main() -> None:
    """AgentRoom — Multi-agent collaboration platform."""


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=4000, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def start(host: str, port: int, reload: bool) -> None:
    """Start the AgentRoom server."""
    click.echo(f"Starting AgentRoom on http://{host}:{port}")
    uvicorn.run(
        "agentroom.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
