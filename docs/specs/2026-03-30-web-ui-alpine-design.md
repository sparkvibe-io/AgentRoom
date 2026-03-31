# Web UI Redesign — Alpine.js + Static Files

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Replace embedded HTML string with static files served by FastAPI, using Alpine.js + Tailwind CDN

## Problem

The current UI is a ~210-line HTML string embedded in `app.py`. It has hardcoded agents (Claude + GPT-4o API), no agent configuration, and no awareness of the new CLI/Ollama adapters or agent config CRUD endpoints. Python developers installing AgentRoom need a zero-build-step UI that works out of the box.

## Design Principles

- Zero build step — no Node.js, no npm, no bundler. `pip install agentroom` and go.
- Alpine.js + Tailwind CDN loaded from `<script>` tags
- Static HTML/JS/CSS files served by FastAPI's `StaticFiles`
- Cowork-inspired dark theme: warm tones, centered content, pill-shaped tabs
- Single page, two views managed by Alpine.js state

## File Structure

```
src/agentroom/server/
├── app.py          # FastAPI app (remove _INDEX_HTML, add StaticFiles mount)
└── static/
    ├── index.html  # Single page — Alpine.js app, loads CDN deps
    ├── app.js      # Alpine.js store, components, API calls, WebSocket
    └── styles.css  # Custom styles (agent colors, animations)
```

## Views

### 1. Top Navigation

Centered pill-shaped tab switcher:
- **"Agents"** tab — always visible
- **"Room"** tab — appears after a room is created

Tabs switch views via `Alpine.store('app').view = 'agents'|'room'`. No routing library.

### 2. Agents View

Centered content (max-width ~700px), containing:

**Agent card list:**
- Each card shows: agent name (colored), provider badge (CLI/Ollama/Anthropic/etc.), model info, command or base_url
- Actions per card: Test (hits `POST /api/agents/{id}/test`, shows inline result), Delete (hits `DELETE /api/agents/{id}`)
- Data source: `GET /api/agents` on page load

**Inline add agent form:**
- Triggered by "+ Add Agent" dashed card at end of list
- Provider dropdown at top: CLI, Ollama, LM Studio, Anthropic, OpenAI
- Fields adapt based on provider:
  - CLI: name, command, model, cli_args (optional)
  - Ollama/LM Studio: name, model, base_url (optional, shows default)
  - Anthropic/OpenAI: name, model, api_key
- Save button hits `POST /api/agents`, Cancel collapses form

**Create Room section:**
- Fixed section below agent list
- Goal text input
- Agent selector: clickable agent chips/checkboxes to pick which agents join
- "Start Room" button hits `POST /api/rooms`, switches to Room view, opens WebSocket

### 3. Room View

Centered content (max-width ~700px), containing:

**Room header bar:**
- Goal text
- Participating agent badges (colored chips)
- Phase badge (researching, consensus, etc.)

**Controls:**
- "Next Turn" button — `POST /api/rooms/{id}/turn`
- "Run Round" button — `POST /api/rooms/{id}/round`

**Message list:**
- Scrollable, auto-scrolls to bottom on new messages
- Each message: agent name (colored), relative timestamp, content
- System/phase messages styled differently (italic, muted)
- Basic markdown rendering: bold, inline code, code blocks

**Message input:**
- Text input + Send button
- Sends via WebSocket: `{"type": "message", "content": "..."}`
- Enter key also sends

## Alpine.js State

```javascript
Alpine.store('app', {
  view: 'agents',           // 'agents' | 'room'
  agents: [],               // from GET /api/agents
  activeRoom: null,         // { id, goal, phase, turn, agents }
  messages: [],             // room messages from WebSocket
  ws: null,                 // WebSocket connection
  showAddForm: false,       // inline form toggle
  addForm: {                // new agent form
    provider: 'cli',
    name: '', model: '', command: '',
    cli_args: '', base_url: '', api_key: ''
  },
  selectedAgents: [],       // agent IDs selected for room creation
  roomGoal: '',             // goal input for room creation
})
```

**Data flow:**
- Page load: `GET /api/agents`, `GET /api/rooms` (check for existing rooms)
- Add agent: `POST /api/agents` → refresh list
- Test agent: `POST /api/agents/{id}/test` → show inline result on card
- Delete agent: `DELETE /api/agents/{id}` → remove from list
- Create room: `POST /api/rooms` with selected agents + goal → switch to Room view → open WebSocket at `ws://host/ws/{room_id}`
- WebSocket `onmessage`: parse JSON, append to messages array
- Run Turn / Round: `POST /api/rooms/{id}/turn` or `/round`
- Send message: WebSocket `send(JSON.stringify({type: "message", content: text}))`

## Theme

Cowork-inspired warm dark theme:
- Background: `#1c1c1c` (main), `#262626` (cards), `#2a2a2a` (tab bar)
- Text: `#f0f0f0` (primary), `#888` (secondary), `#666` (muted)
- Accent: `#7c83ff` (indigo — buttons, active states)
- Agent colors: green (#4ade80), blue (#60a5fa), purple (#c084fc), orange (#fb923c) — assigned per agent
- Provider badge colors: match agent but muted (dark backgrounds with colored text)

## Changes to app.py

- Remove `_INDEX_HTML` string (~210 lines)
- Remove `index()` route returning `HTMLResponse`
- Add import: `from starlette.staticfiles import StaticFiles` and `from pathlib import Path`
- Add at end of `create_app()`, after all API/WebSocket routes:
  ```python
  static_dir = Path(__file__).parent / "static"
  app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
  ```
- All API and WebSocket routes unchanged

## Dependencies

- No new Python dependencies (`starlette.staticfiles` ships with FastAPI)
- Alpine.js loaded from CDN: `<script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js">`
- Tailwind CSS loaded from CDN: `<script src="https://cdn.tailwindcss.com">`

## What's NOT in Scope

- Authentication / login
- Room persistence across server restarts
- Multiple simultaneous rooms in the UI
- Agent workspace / file access
- React migration
