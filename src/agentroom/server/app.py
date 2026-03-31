"""FastAPI application — REST API + WebSocket for room interaction."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from agentroom.agents.anthropic import AnthropicAdapter
from agentroom.agents.cli import CLIAdapter
from agentroom.agents.ollama import OllamaAdapter
from agentroom.agents.openai import OpenAIAdapter
from agentroom.broker.queue import MessageBroker
from agentroom.coordinator.room import Room
from agentroom.protocol.agent_config import AgentConfig
from agentroom.protocol.extensions import RoomPhase  # noqa: TCH001 (runtime: Pydantic model)
from agentroom.protocol.models import AgentCard, Message, RoomConfig

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

    from agentroom.agents.base import AgentAdapter

logger = logging.getLogger(__name__)

# --- In-memory room registry ---
_rooms: dict[str, Room] = {}
_ws_connections: dict[str, list[WebSocket]] = {}  # room_id -> websockets
_config_broker: MessageBroker | None = None


# --- Request/response models ---

class CreateRoomRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=5000)
    agents: list[AgentCard] = Field(min_length=1, max_length=10)
    lead_agent: str | None = None


class UserMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class PhaseChangeRequest(BaseModel):
    phase: RoomPhase


class RoomSummary(BaseModel):
    id: str
    goal: str
    phase: str
    turn: int
    agents: list[str]


class CreateAgentConfigRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    command: str | None = Field(default=None, max_length=200)
    cli_args: list[str] = Field(default_factory=list, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)


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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _config_broker  # noqa: PLW0603
    _config_broker = MessageBroker()
    yield
    for room in _rooms.values():
        await room.stop()
    _config_broker.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentRoom",
        version="0.1.0",
        description="Multi-agent collaboration platform",
        lifespan=_lifespan,
    )

    # --- Security headers middleware ---
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            response: Response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # --- Routes ---

    def _get_room(room_id: str) -> Room:
        if room_id not in _rooms:
            raise HTTPException(status_code=404, detail="Room not found")
        return _rooms[room_id]

    @app.post("/api/rooms")
    async def create_room(req: CreateRoomRequest) -> RoomSummary:
        config = RoomConfig(goal=req.goal, agents=req.agents, lead_agent=req.lead_agent)
        broker = MessageBroker()
        room = Room(config=config, broker=broker)

        try:
            for card in req.agents:
                adapter = _build_adapter(card)
                room.add_agent(adapter)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid agent configuration") from None

        # Wire up WebSocket push
        def on_msg(msg: Message) -> None:
            _broadcast_to_ws(room.room_id, msg)

        room.on_message(on_msg)

        await room.start()
        _rooms[room.room_id] = room

        return RoomSummary(
            id=room.room_id,
            goal=config.goal,
            phase=room.phase.value,
            turn=room.state.turn,
            agents=[a.name for a in config.agents],
        )

    @app.get("/api/rooms")
    async def list_rooms() -> list[RoomSummary]:
        return [
            RoomSummary(
                id=r.room_id,
                goal=r.state.config.goal,
                phase=r.phase.value,
                turn=r.state.turn,
                agents=list(r.adapters.keys()),
            )
            for r in _rooms.values()
        ]

    @app.get("/api/rooms/{room_id}")
    async def get_room(room_id: str) -> RoomSummary:
        room = _get_room(room_id)
        return RoomSummary(
            id=room.room_id,
            goal=room.state.config.goal,
            phase=room.phase.value,
            turn=room.state.turn,
            agents=list(room.adapters.keys()),
        )

    @app.get("/api/rooms/{room_id}/messages")
    async def get_messages(
        room_id: str, limit: int = Query(default=100, ge=1, le=1000)
    ) -> list[dict[str, Any]]:
        room = _get_room(room_id)
        messages = room.broker.get_history(room_id, limit=limit)
        return [m.model_dump() for m in messages]

    @app.post("/api/rooms/{room_id}/message")
    async def post_message(room_id: str, req: UserMessageRequest) -> dict[str, str]:
        room = _get_room(room_id)
        await room.user_message(req.content)
        return {"status": "sent"}

    @app.post("/api/rooms/{room_id}/turn")
    async def run_turn(room_id: str, agent: str | None = None) -> dict[str, Any]:
        room = _get_room(room_id)
        try:
            msg = await asyncio.wait_for(room.run_turn(agent), timeout=120.0)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Agent response timed out") from None
        if msg:
            return {"status": "ok", "message": msg.model_dump()}
        return {"status": "no_response"}

    @app.post("/api/rooms/{room_id}/round")
    async def run_round(room_id: str) -> dict[str, Any]:
        room = _get_room(room_id)
        try:
            messages = await asyncio.wait_for(room.run_round(), timeout=600.0)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Round timed out") from None
        return {"status": "ok", "messages": [m.model_dump() for m in messages]}

    @app.post("/api/rooms/{room_id}/phase")
    async def change_phase(room_id: str, req: PhaseChangeRequest) -> dict[str, str]:
        room = _get_room(room_id)
        room.set_phase(req.phase)
        return {"phase": req.phase.value}

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
        updated = existing.model_copy(update={
            "name": req.name,
            "provider": req.provider,
            "model": req.model,
            "command": req.command,
            "cli_args": req.cli_args,
            "base_url": req.base_url,
            "api_key": req.api_key,
            "updated_at": time.time(),
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

    # --- WebSocket ---

    @app.websocket("/ws/{room_id}")
    async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()

        if room_id not in _ws_connections:
            _ws_connections[room_id] = []
        _ws_connections[room_id].append(websocket)

        max_ws_payload = 32_768  # 32 KB

        try:
            # Send existing history
            if room_id in _rooms:
                history = _rooms[room_id].broker.get_history(room_id, limit=100)
                for msg in history:
                    await websocket.send_json(msg.model_dump())

            # Keep alive — listen for user messages
            while True:
                data = await websocket.receive_text()

                if len(data) > max_ws_payload:
                    await websocket.send_json({"error": "Message too large"})
                    continue

                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON"})
                    continue

                if not isinstance(parsed, dict):
                    await websocket.send_json({"error": "Expected JSON object"})
                    continue

                payload = cast("dict[str, Any]", parsed)
                msg_type = payload.get("type")
                if msg_type == "message" and room_id in _rooms:
                    content = payload.get("content")
                    if not isinstance(content, str) or len(content) > 10_000:
                        await websocket.send_json({"error": "Invalid or too-long content"})
                        continue
                    room = _rooms[room_id]
                    await room.user_message(content)
                elif msg_type == "turn" and room_id in _rooms:
                    room = _rooms[room_id]
                    agent_name: str | None = payload.get("agent")
                    await room.run_turn(agent_name)
                elif msg_type == "round" and room_id in _rooms:
                    room = _rooms[room_id]
                    await room.run_round()
                else:
                    await websocket.send_json({"error": "Unknown message type"})

        except WebSocketDisconnect:
            _ws_connections.get(room_id, []).remove(websocket)

    # --- Static files (web UI) ---
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


def _broadcast_to_ws(room_id: str, message: Message) -> None:
    """Push a message to all WebSocket clients watching this room."""
    connections = _ws_connections.get(room_id, [])
    data = message.model_dump()
    for ws in connections:
        try:
            asyncio.get_event_loop().create_task(ws.send_json(data))
        except Exception:
            logger.debug("Failed to send to WebSocket client")
