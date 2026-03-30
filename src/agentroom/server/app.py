"""FastAPI application — REST API + WebSocket for room interaction."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agentroom.agents.anthropic import AnthropicAdapter
from agentroom.agents.base import AgentAdapter
from agentroom.agents.openai import OpenAIAdapter
from agentroom.broker.queue import MessageBroker
from agentroom.coordinator.room import Room
from agentroom.protocol.extensions import RoomPhase
from agentroom.protocol.models import AgentCard, Message, RoomConfig

logger = logging.getLogger(__name__)

# --- In-memory room registry ---
_rooms: dict[str, Room] = {}
_ws_connections: dict[str, list[WebSocket]] = {}  # room_id -> websockets


# --- Request/response models ---

class CreateRoomRequest(BaseModel):
    goal: str
    agents: list[AgentCard]
    lead_agent: str | None = None


class UserMessageRequest(BaseModel):
    content: str


class PhaseChangeRequest(BaseModel):
    phase: RoomPhase


class RoomSummary(BaseModel):
    id: str
    goal: str
    phase: str
    turn: int
    agents: list[str]


def _build_adapter(card: AgentCard) -> AgentAdapter:
    """Create the right adapter based on provider name."""
    match card.provider:
        case "anthropic":
            return AnthropicAdapter(card)
        case "openai" | "openai-compat":
            return OpenAIAdapter(card)
        case _:
            raise ValueError(f"Unknown provider: {card.provider}")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    # Cleanup: stop all rooms
    for room in _rooms.values():
        await room.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentRoom",
        version="0.1.0",
        description="Multi-agent collaboration platform",
        lifespan=_lifespan,
    )

    # --- Routes ---

    def _get_room(room_id: str) -> Room:
        if room_id not in _rooms:
            raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
        return _rooms[room_id]

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse(_INDEX_HTML)

    @app.post("/api/rooms")
    async def create_room(req: CreateRoomRequest) -> RoomSummary:
        config = RoomConfig(goal=req.goal, agents=req.agents, lead_agent=req.lead_agent)
        broker = MessageBroker()
        room = Room(config=config, broker=broker)

        try:
            for card in req.agents:
                adapter = _build_adapter(card)
                room.add_agent(adapter)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

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
    async def get_messages(room_id: str, limit: int = 100) -> list[dict[str, Any]]:
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
        msg = await room.run_turn(agent)
        if msg:
            return {"status": "ok", "message": msg.model_dump()}
        return {"status": "no_response"}

    @app.post("/api/rooms/{room_id}/round")
    async def run_round(room_id: str) -> dict[str, Any]:
        room = _get_room(room_id)
        messages = await room.run_round()
        return {"status": "ok", "messages": [m.model_dump() for m in messages]}

    @app.post("/api/rooms/{room_id}/phase")
    async def change_phase(room_id: str, req: PhaseChangeRequest) -> dict[str, str]:
        room = _get_room(room_id)
        room.set_phase(req.phase)
        return {"phase": req.phase.value}

    # --- WebSocket ---

    @app.websocket("/ws/{room_id}")
    async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()

        if room_id not in _ws_connections:
            _ws_connections[room_id] = []
        _ws_connections[room_id].append(websocket)

        try:
            # Send existing history
            if room_id in _rooms:
                history = _rooms[room_id].broker.get_history(room_id, limit=100)
                for msg in history:
                    await websocket.send_json(msg.model_dump())

            # Keep alive — listen for user messages
            while True:
                data = await websocket.receive_text()
                parsed = json.loads(data)

                if parsed.get("type") == "message" and room_id in _rooms:
                    room = _rooms[room_id]
                    await room.user_message(parsed["content"])
                elif parsed.get("type") == "turn" and room_id in _rooms:
                    room = _rooms[room_id]
                    await room.run_turn(parsed.get("agent"))
                elif parsed.get("type") == "round" and room_id in _rooms:
                    room = _rooms[room_id]
                    await room.run_round()

        except WebSocketDisconnect:
            _ws_connections.get(room_id, []).remove(websocket)

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


# --- Embedded index page (v1 — will be replaced by React app) ---

_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgentRoom</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  .agent-msg { animation: fadeIn 0.3s ease-in; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen flex flex-col">

<!-- Header -->
<header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
  <div>
    <h1 class="text-xl font-bold">AgentRoom</h1>
    <p id="room-info" class="text-sm text-gray-400">No room active</p>
  </div>
  <div id="phase-badge" class="px-3 py-1 rounded-full text-xs font-medium bg-gray-800 text-gray-400">
    —
  </div>
</header>

<!-- Main layout -->
<div class="flex flex-1 overflow-hidden">

  <!-- Sidebar: Agents -->
  <aside class="w-56 border-r border-gray-800 p-4 hidden md:block">
    <h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Agents</h2>
    <div id="agents-list" class="space-y-2"></div>
    <div class="mt-6">
      <h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Controls</h2>
      <button onclick="runRound()" class="w-full px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium transition">
        Run Round
      </button>
      <button onclick="runTurn()" class="w-full mt-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium transition">
        Next Turn
      </button>
    </div>
  </aside>

  <!-- Chat area -->
  <main class="flex-1 flex flex-col">
    <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-4"></div>

    <!-- Input -->
    <div class="border-t border-gray-800 p-4">
      <form id="msg-form" class="flex gap-3">
        <input id="msg-input" type="text" placeholder="Send a message to the room..."
               class="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500 transition">
        <button type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition">
          Send
        </button>
      </form>
    </div>
  </main>
</div>

<!-- Create Room Modal -->
<div id="create-modal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
  <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg">
    <h2 class="text-lg font-bold mb-4">Create a Room</h2>
    <form id="create-form" class="space-y-4">
      <div>
        <label class="block text-sm text-gray-400 mb-1">Goal</label>
        <input id="goal-input" type="text" placeholder="What should the agents work on?"
               class="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500">
      </div>
      <p class="text-xs text-gray-500">Default agents: @claude (Claude 3.5 Sonnet) + @gpt4o (GPT-4o)</p>
      <button type="submit" class="w-full px-4 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-medium transition">
        Start Room
      </button>
    </form>
  </div>
</div>

<script>
const COLORS = {
  'system': 'text-gray-500',
  '@claude': 'text-orange-400',
  '@gpt4o': 'text-green-400',
  '@gemini': 'text-blue-400',
  '@grok': 'text-purple-400',
  'user': 'text-yellow-300',
};

let ws = null;
let currentRoomId = null;

// Create room
document.getElementById('create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const goal = document.getElementById('goal-input').value.trim();
  if (!goal) return;

  const resp = await fetch('/api/rooms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      goal,
      agents: [
        { name: '@claude', provider: 'anthropic', model: 'claude-sonnet-4-20250514', role: 'coordinator' },
        { name: '@gpt4o', provider: 'openai', model: 'gpt-4o', role: 'researcher' },
      ]
    })
  });
  const room = await resp.json();
  currentRoomId = room.id;
  document.getElementById('create-modal').classList.add('hidden');
  connectWs(room.id);
  updateRoomUI(room);
});

function connectWs(roomId) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/${roomId}`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    appendMessage(msg);
  };
  ws.onclose = () => { ws = null; };
}

function appendMessage(msg) {
  const el = document.getElementById('messages');
  const colorClass = COLORS[msg.from_agent] || 'text-gray-300';
  const isSystem = msg.type === 'system' || msg.type === 'phase';

  const div = document.createElement('div');
  div.className = 'agent-msg';

  if (isSystem) {
    div.innerHTML = `<p class="text-xs text-gray-500 italic">${escapeHtml(msg.content)}</p>`;
  } else {
    div.innerHTML = `
      <div class="flex items-start gap-3">
        <span class="font-mono text-xs ${colorClass} font-bold whitespace-nowrap pt-1">${escapeHtml(msg.from_agent)}</span>
        <div class="text-sm text-gray-200 leading-relaxed prose prose-invert prose-sm max-w-none">${formatContent(msg.content)}</div>
      </div>`;
  }

  el.appendChild(div);
  el.scrollTop = el.scrollHeight;

  // Update phase badge
  if (msg.extensions && msg.extensions['agentroom/phase']) {
    document.getElementById('phase-badge').textContent = msg.extensions['agentroom/phase'].current;
  }
}

function updateRoomUI(room) {
  document.getElementById('room-info').textContent = `Room ${room.id} — ${room.goal}`;
  document.getElementById('phase-badge').textContent = room.phase;
  const list = document.getElementById('agents-list');
  list.innerHTML = room.agents.map(a => {
    const c = COLORS[a] || 'text-gray-300';
    return `<div class="flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-green-500"></span><span class="${c} text-sm font-mono">${a}</span></div>`;
  }).join('');
}

// Send user message
document.getElementById('msg-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const input = document.getElementById('msg-input');
  const content = input.value.trim();
  if (!content || !ws) return;
  ws.send(JSON.stringify({ type: 'message', content }));
  input.value = '';
});

async function runRound() {
  if (!currentRoomId) return;
  await fetch(`/api/rooms/${currentRoomId}/round`, { method: 'POST' });
}

async function runTurn() {
  if (!currentRoomId) return;
  await fetch(`/api/rooms/${currentRoomId}/turn`, { method: 'POST' });
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function formatContent(s) {
  // Basic markdown: bold, code, code blocks
  const escaped = escapeHtml(s);
  const withCodeBlocks = escaped.replace(/```([^]*?)```/g, '<pre class="bg-gray-800 rounded p-3 my-2 overflow-x-auto text-xs"><code>$1</code></pre>');
  const withInlineCode = withCodeBlocks.replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1 rounded text-xs">$1</code>');
  const withBold = withInlineCode.replace(/[*][*](.+?)[*][*]/g, '<strong>$1</strong>');
  return withBold.replace(/\\n/g, '<br>');
}

// Check if rooms already exist
(async () => {
  const resp = await fetch('/api/rooms');
  const rooms = await resp.json();
  if (rooms.length > 0) {
    const room = rooms[0];
    currentRoomId = room.id;
    document.getElementById('create-modal').classList.add('hidden');
    connectWs(room.id);
    updateRoomUI(room);
  }
})();
</script>
</body>
</html>
"""
