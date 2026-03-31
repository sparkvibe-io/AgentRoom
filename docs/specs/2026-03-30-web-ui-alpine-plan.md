# Web UI Alpine.js Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the embedded HTML string in app.py with a static Alpine.js + Tailwind web UI that supports agent configuration, room creation, and real-time chat.

**Architecture:** Three static files (index.html, app.js, styles.css) served by FastAPI's StaticFiles. Alpine.js manages SPA state (two views: Agents and Room). Tailwind CDN for styling. WebSocket for real-time messages. All existing API endpoints consumed as-is.

**Tech Stack:** Alpine.js 3 (CDN), Tailwind CSS (CDN), vanilla JS, FastAPI StaticFiles

---

### Task 1: Create static directory and index.html shell

**Files:**
- Create: `src/agentroom/server/static/index.html`

- [ ] **Step 1: Create the static directory**

Run: `mkdir -p src/agentroom/server/static`

- [ ] **Step 2: Create index.html**

Create `src/agentroom/server/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentRoom</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            surface: { DEFAULT: '#1c1c1c', card: '#262626', nav: '#2a2a2a', hover: '#333333' },
            accent: { DEFAULT: '#7c83ff', hover: '#6b72e8' },
          }
        }
      }
    }
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
  <link rel="stylesheet" href="/styles.css">
</head>
<body class="bg-surface text-gray-100 min-h-screen" x-data x-init="$store.app.init()">

  <!-- Top Navigation -->
  <nav class="flex justify-center py-3 border-b border-gray-800">
    <div class="flex bg-surface-nav rounded-lg p-1 gap-1">
      <button
        @click="$store.app.view = 'agents'"
        :class="$store.app.view === 'agents' ? 'bg-surface-hover text-white' : 'text-gray-500 hover:text-gray-300'"
        class="px-5 py-1.5 rounded-md text-sm font-medium transition">
        Agents
      </button>
      <button
        x-show="$store.app.activeRoom"
        @click="$store.app.view = 'room'"
        :class="$store.app.view === 'room' ? 'bg-surface-hover text-white' : 'text-gray-500 hover:text-gray-300'"
        class="px-5 py-1.5 rounded-md text-sm font-medium transition">
        Room
      </button>
    </div>
  </nav>

  <!-- Agents View -->
  <main x-show="$store.app.view === 'agents'" class="max-w-2xl mx-auto px-5 py-8">

    <!-- Header -->
    <div class="text-center mb-8">
      <h1 class="text-2xl font-semibold text-gray-100">Your Agent Team</h1>
      <p class="text-gray-500 text-sm mt-1">Configure agents, then create a room to start collaborating</p>
    </div>

    <!-- Agent Cards -->
    <div class="flex flex-col gap-3 mb-6">
      <template x-for="agent in $store.app.agents" :key="agent.id">
        <div class="bg-surface-card rounded-xl p-4 flex items-center gap-4 border border-gray-800">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0"
               :class="$store.app.agentColor(agent.name).bg">
            <span :class="$store.app.agentColor(agent.name).text" x-text="agent.name[0] === '@' ? agent.name[1].toUpperCase() : agent.name[0].toUpperCase()"></span>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-semibold text-sm" :class="$store.app.agentColor(agent.name).text" x-text="agent.name"></span>
              <span class="text-xs px-2 py-0.5 rounded-full"
                    :class="$store.app.agentColor(agent.name).badge"
                    x-text="agent.provider.toUpperCase()"></span>
            </div>
            <div class="text-gray-500 text-xs mt-0.5">
              <span x-text="agent.model"></span>
              <span x-show="agent.command"> · <span x-text="agent.command"></span></span>
              <span x-show="agent.base_url"> · <span x-text="agent.base_url"></span></span>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <!-- Test button -->
            <button @click="$store.app.testAgent(agent.id)"
                    class="text-gray-500 text-xs px-3 py-1 border border-gray-700 rounded-md hover:border-gray-500 transition"
                    :disabled="agent._testing">
              <span x-show="!agent._testing && agent._testResult === undefined">Test</span>
              <span x-show="agent._testing">...</span>
              <span x-show="agent._testResult === true" class="text-green-400">OK</span>
              <span x-show="agent._testResult === false" class="text-red-400">Fail</span>
            </button>
            <!-- Delete button -->
            <button @click="$store.app.deleteAgent(agent.id)"
                    class="text-gray-600 hover:text-red-400 text-sm px-1 transition">
              ✕
            </button>
          </div>
        </div>
      </template>

      <!-- Add Agent Button / Inline Form -->
      <div x-show="!$store.app.showAddForm"
           @click="$store.app.showAddForm = true"
           class="bg-surface-card rounded-xl p-4 flex items-center justify-center gap-2 border border-dashed border-gray-700 cursor-pointer hover:border-gray-500 transition text-gray-500">
        <span class="text-lg">+</span>
        <span class="text-sm">Add Agent</span>
      </div>

      <!-- Inline Add Form -->
      <div x-show="$store.app.showAddForm" x-transition
           class="bg-surface-card rounded-xl p-5 border border-gray-700">
        <div class="flex items-center justify-between mb-4">
          <span class="text-sm font-medium">New Agent</span>
          <button @click="$store.app.showAddForm = false; $store.app.resetAddForm()"
                  class="text-gray-500 hover:text-gray-300 text-sm">Cancel</button>
        </div>

        <!-- Provider Select -->
        <div class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">Provider</label>
          <select x-model="$store.app.addForm.provider"
                  class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
            <option value="cli">CLI (claude, gemini, codex)</option>
            <option value="ollama">Ollama</option>
            <option value="lmstudio">LM Studio</option>
            <option value="anthropic">Anthropic (API key)</option>
            <option value="openai">OpenAI (API key)</option>
          </select>
        </div>

        <!-- Name -->
        <div class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">Name</label>
          <input x-model="$store.app.addForm.name" type="text" placeholder="@claude"
                 class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
        </div>

        <!-- Model -->
        <div class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">Model</label>
          <input x-model="$store.app.addForm.model" type="text" placeholder="sonnet-4"
                 class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
        </div>

        <!-- CLI fields -->
        <div x-show="$store.app.addForm.provider === 'cli'" class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">Command</label>
          <input x-model="$store.app.addForm.command" type="text" placeholder="claude"
                 class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
        </div>

        <!-- Local LLM fields -->
        <div x-show="['ollama', 'lmstudio'].includes($store.app.addForm.provider)" class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">Base URL (optional)</label>
          <input x-model="$store.app.addForm.base_url" type="text"
                 :placeholder="$store.app.addForm.provider === 'ollama' ? 'http://localhost:11434/v1' : 'http://localhost:1234/v1'"
                 class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
        </div>

        <!-- API key fields -->
        <div x-show="['anthropic', 'openai'].includes($store.app.addForm.provider)" class="mb-3">
          <label class="block text-xs text-gray-500 mb-1">API Key</label>
          <input x-model="$store.app.addForm.api_key" type="password" placeholder="sk-..."
                 class="w-full bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent">
        </div>

        <!-- Save -->
        <button @click="$store.app.saveAgent()"
                class="w-full bg-accent hover:bg-accent-hover text-white py-2 rounded-lg text-sm font-medium transition">
          Save Agent
        </button>
      </div>
    </div>

    <!-- Create Room -->
    <div class="bg-surface-card rounded-xl p-5 border border-gray-800">
      <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Create Room</div>
      <input x-model="$store.app.roomGoal" type="text"
             placeholder="What should the agents work on?"
             class="w-full bg-surface border border-gray-700 rounded-lg px-4 py-2.5 text-sm mb-3 focus:outline-none focus:border-accent">
      <div class="flex justify-between items-center">
        <div class="flex flex-wrap gap-1.5">
          <template x-for="agent in $store.app.agents" :key="agent.id">
            <button @click="$store.app.toggleAgentSelection(agent.id)"
                    class="text-xs px-2.5 py-1 rounded-full border transition"
                    :class="$store.app.selectedAgents.includes(agent.id)
                      ? $store.app.agentColor(agent.name).badge + ' border-transparent'
                      : 'border-gray-700 text-gray-500 hover:border-gray-500'">
              <span x-text="agent.name"></span>
            </button>
          </template>
        </div>
        <button @click="$store.app.createRoom()"
                :disabled="!$store.app.roomGoal || $store.app.selectedAgents.length < 1"
                class="bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg text-sm font-medium transition flex-shrink-0">
          Start Room
        </button>
      </div>
    </div>
  </main>

  <!-- Room View -->
  <main x-show="$store.app.view === 'room'" class="flex flex-col" style="height: calc(100vh - 49px);">

    <!-- Room Header -->
    <div class="max-w-2xl mx-auto w-full px-5 py-3 border-b border-gray-800 flex justify-between items-center">
      <div>
        <div class="text-sm font-medium text-gray-100" x-text="$store.app.activeRoom?.goal || ''"></div>
        <div class="flex gap-1.5 mt-1">
          <template x-for="name in ($store.app.activeRoom?.agents || [])" :key="name">
            <span class="text-xs px-2 py-0.5 rounded-full"
                  :class="$store.app.agentColor(name).badge"
                  x-text="name"></span>
          </template>
          <span class="text-xs px-2 py-0.5 rounded-full bg-purple-900/50 text-purple-300"
                x-text="$store.app.activeRoom?.phase || ''"></span>
        </div>
      </div>
      <div class="flex gap-2">
        <button @click="$store.app.runTurn()"
                class="text-gray-400 text-xs px-3 py-1.5 border border-gray-700 rounded-md hover:border-gray-500 transition">
          Next Turn
        </button>
        <button @click="$store.app.runRound()"
                class="bg-accent hover:bg-accent-hover text-white text-xs px-3 py-1.5 rounded-md transition">
          Run Round
        </button>
      </div>
    </div>

    <!-- Messages -->
    <div class="flex-1 overflow-y-auto" x-ref="messageList">
      <div class="max-w-2xl mx-auto px-5 py-4 space-y-4">
        <template x-for="msg in $store.app.messages" :key="msg.id">
          <div>
            <!-- System/Phase messages -->
            <template x-if="msg.type === 'system' || msg.type === 'phase'">
              <p class="text-xs text-gray-600 italic" x-text="msg.content"></p>
            </template>
            <!-- Agent messages -->
            <template x-if="msg.type !== 'system' && msg.type !== 'phase'">
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-xs font-semibold" :class="$store.app.agentColor(msg.from_agent).text" x-text="msg.from_agent"></span>
                  <span class="text-xs text-gray-600" x-text="$store.app.timeAgo(msg.created_at)"></span>
                </div>
                <div class="text-sm text-gray-200 leading-relaxed prose-content" x-html="$store.app.renderMarkdown(msg.content)"></div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <!-- Input -->
    <div class="border-t border-gray-800">
      <div class="max-w-2xl mx-auto px-5 py-3">
        <form @submit.prevent="$store.app.sendMessage()" class="flex gap-2">
          <input x-model="$store.app.messageInput" type="text"
                 placeholder="Send a message to the room..."
                 class="flex-1 bg-surface-card border border-gray-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent">
          <button type="submit"
                  class="bg-accent hover:bg-accent-hover text-white px-4 py-2.5 rounded-lg text-sm font-medium transition">
            Send
          </button>
        </form>
      </div>
    </div>
  </main>

  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add src/agentroom/server/static/index.html
git commit -m "feat: add index.html shell for Alpine.js web UI"
```

---

### Task 2: Create app.js — Alpine.js store and logic

**Files:**
- Create: `src/agentroom/server/static/app.js`

- [ ] **Step 1: Create app.js**

Create `src/agentroom/server/static/app.js`:

```javascript
/* AgentRoom — Alpine.js application store */

const AGENT_COLORS = [
  { text: 'text-green-400', bg: 'bg-green-900/50', badge: 'bg-green-900/50 text-green-400' },
  { text: 'text-blue-400', bg: 'bg-blue-900/50', badge: 'bg-blue-900/50 text-blue-400' },
  { text: 'text-purple-400', bg: 'bg-purple-900/50', badge: 'bg-purple-900/50 text-purple-400' },
  { text: 'text-orange-400', bg: 'bg-orange-900/50', badge: 'bg-orange-900/50 text-orange-400' },
  { text: 'text-pink-400', bg: 'bg-pink-900/50', badge: 'bg-pink-900/50 text-pink-400' },
  { text: 'text-cyan-400', bg: 'bg-cyan-900/50', badge: 'bg-cyan-900/50 text-cyan-400' },
];

const USER_COLOR = { text: 'text-yellow-300', bg: 'bg-yellow-900/50', badge: 'bg-yellow-900/50 text-yellow-300' };
const SYSTEM_COLOR = { text: 'text-gray-500', bg: 'bg-gray-800', badge: 'bg-gray-800 text-gray-500' };

document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    // --- State ---
    view: 'agents',
    agents: [],
    activeRoom: null,
    messages: [],
    ws: null,
    showAddForm: false,
    addForm: { provider: 'cli', name: '', model: '', command: '', cli_args: '', base_url: '', api_key: '' },
    selectedAgents: [],
    roomGoal: '',
    messageInput: '',
    _colorMap: {},

    // --- Init ---
    async init() {
      await this.fetchAgents();
      const rooms = await this._api('GET', '/api/rooms');
      if (rooms && rooms.length > 0) {
        this.activeRoom = rooms[0];
        this.messages = await this._api('GET', `/api/rooms/${this.activeRoom.id}/messages?limit=200`) || [];
        this._connectWs(this.activeRoom.id);
        this.view = 'room';
      }
    },

    // --- Agent CRUD ---
    async fetchAgents() {
      const data = await this._api('GET', '/api/agents');
      this.agents = (data || []).map(a => ({ ...a, _testing: false, _testResult: undefined }));
    },

    async saveAgent() {
      const f = this.addForm;
      const body = {
        name: f.name,
        provider: f.provider,
        model: f.model,
      };
      if (f.provider === 'cli') body.command = f.command;
      if (f.cli_args) body.cli_args = f.cli_args.split(' ').filter(Boolean);
      if (f.base_url) body.base_url = f.base_url;
      if (f.api_key) body.api_key = f.api_key;

      await this._api('POST', '/api/agents', body);
      await this.fetchAgents();
      this.showAddForm = false;
      this.resetAddForm();
    },

    async deleteAgent(id) {
      await this._api('DELETE', `/api/agents/${id}`);
      this.selectedAgents = this.selectedAgents.filter(a => a !== id);
      await this.fetchAgents();
    },

    async testAgent(id) {
      const agent = this.agents.find(a => a.id === id);
      if (!agent) return;
      agent._testing = true;
      agent._testResult = undefined;
      const result = await this._api('POST', `/api/agents/${id}/test`);
      agent._testing = false;
      agent._testResult = result?.available === true;
      setTimeout(() => { agent._testResult = undefined; }, 5000);
    },

    resetAddForm() {
      this.addForm = { provider: 'cli', name: '', model: '', command: '', cli_args: '', base_url: '', api_key: '' };
    },

    // --- Room ---
    async createRoom() {
      const agentCards = this.agents
        .filter(a => this.selectedAgents.includes(a.id))
        .map(a => ({
          name: a.name,
          provider: a.provider,
          model: a.model,
          command: a.command || undefined,
          cli_args: a.cli_args?.length ? a.cli_args : undefined,
          base_url: a.base_url || undefined,
          api_key: a.api_key || undefined,
        }));

      const room = await this._api('POST', '/api/rooms', {
        goal: this.roomGoal,
        agents: agentCards,
      });

      if (room) {
        this.activeRoom = room;
        this.messages = await this._api('GET', `/api/rooms/${room.id}/messages?limit=200`) || [];
        this._connectWs(room.id);
        this.view = 'room';
        this.roomGoal = '';
        this.selectedAgents = [];
      }
    },

    async runTurn() {
      if (!this.activeRoom) return;
      await this._api('POST', `/api/rooms/${this.activeRoom.id}/turn`);
    },

    async runRound() {
      if (!this.activeRoom) return;
      await this._api('POST', `/api/rooms/${this.activeRoom.id}/round`);
    },

    sendMessage() {
      if (!this.ws || !this.messageInput.trim()) return;
      this.ws.send(JSON.stringify({ type: 'message', content: this.messageInput.trim() }));
      this.messageInput = '';
    },

    // --- Agent selection ---
    toggleAgentSelection(id) {
      const idx = this.selectedAgents.indexOf(id);
      if (idx >= 0) {
        this.selectedAgents.splice(idx, 1);
      } else {
        this.selectedAgents.push(id);
      }
    },

    // --- WebSocket ---
    _connectWs(roomId) {
      if (this.ws) { this.ws.close(); this.ws = null; }
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${location.host}/ws/${roomId}`);
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.error) return;
        // Avoid duplicates (WebSocket sends history on connect)
        if (!this.messages.find(m => m.id === msg.id)) {
          this.messages.push(msg);
        }
        // Update phase
        if (msg.extensions?.['agentroom/phase']) {
          this.activeRoom.phase = msg.extensions['agentroom/phase'].current;
        }
        // Auto-scroll
        this.$nextTick(() => {
          const el = document.querySelector('[x-ref="messageList"]');
          if (el) el.scrollTop = el.scrollHeight;
        });
      };
      ws.onclose = () => { this.ws = null; };
      this.ws = ws;
    },

    // --- Colors ---
    agentColor(name) {
      if (name === 'user') return USER_COLOR;
      if (name === 'system') return SYSTEM_COLOR;
      if (!this._colorMap[name]) {
        const idx = Object.keys(this._colorMap).length % AGENT_COLORS.length;
        this._colorMap[name] = AGENT_COLORS[idx];
      }
      return this._colorMap[name];
    },

    // --- Markdown ---
    renderMarkdown(text) {
      if (!text) return '';
      let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-800 rounded-lg p-3 my-2 overflow-x-auto text-xs"><code>$1</code></pre>')
        .replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1.5 py-0.5 rounded text-xs">$1</code>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
      return html;
    },

    // --- Time ---
    timeAgo(timestamp) {
      const seconds = Math.floor(Date.now() / 1000 - timestamp);
      if (seconds < 60) return 'just now';
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      return `${hours}h ago`;
    },

    // --- API helper ---
    async _api(method, url, body) {
      try {
        const opts = { method, headers: {} };
        if (body) {
          opts.headers['Content-Type'] = 'application/json';
          opts.body = JSON.stringify(body);
        }
        const resp = await fetch(url, opts);
        if (!resp.ok) return null;
        return await resp.json();
      } catch {
        return null;
      }
    },
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add src/agentroom/server/static/app.js
git commit -m "feat: add Alpine.js store with agent CRUD, room, and WebSocket logic"
```

---

### Task 3: Create styles.css

**Files:**
- Create: `src/agentroom/server/static/styles.css`

- [ ] **Step 1: Create styles.css**

Create `src/agentroom/server/static/styles.css`:

```css
/* AgentRoom — custom styles (Tailwind handles most via classes) */

/* Smooth transitions for Alpine.js x-show */
[x-cloak] { display: none !important; }

/* Message content prose */
.prose-content pre {
  background: #1f2937;
  border-radius: 0.5rem;
  padding: 0.75rem;
  margin: 0.5rem 0;
  overflow-x: auto;
  font-size: 0.75rem;
}

.prose-content code {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
  font-size: 0.8em;
}

.prose-content pre code {
  background: none;
  padding: 0;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Message fade-in animation */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.space-y-4 > div {
  animation: fadeIn 0.2s ease-out;
}

/* Select dropdown styling */
select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.5rem center;
  background-repeat: no-repeat;
  background-size: 1.5em 1.5em;
  padding-right: 2.5rem;
}

/* Focus ring for inputs */
input:focus, select:focus {
  outline: none;
  border-color: #7c83ff;
  box-shadow: 0 0 0 1px #7c83ff33;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/agentroom/server/static/styles.css
git commit -m "feat: add custom styles for AgentRoom web UI"
```

---

### Task 4: Update app.py — remove embedded HTML, mount static files

**Files:**
- Modify: `src/agentroom/server/app.py:13, 130-132, 369, 383-598`

- [ ] **Step 1: Update imports**

In `src/agentroom/server/app.py`, replace the `HTMLResponse` import with `StaticFiles` and `Path`:

Replace line 13:
```python
from fastapi.responses import HTMLResponse
```

With:
```python
from pathlib import Path
from starlette.staticfiles import StaticFiles
```

- [ ] **Step 2: Remove the index route**

Remove lines 130-132 (the `index()` route):

```python
    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse(_INDEX_HTML)
```

- [ ] **Step 3: Add static file mount before `return app`**

Before `return app` (line 369), add:

```python
    # --- Static files (web UI) ---
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

- [ ] **Step 4: Remove the entire `_INDEX_HTML` string**

Delete lines 383-598 (the `# --- Embedded index page` comment and the entire `_INDEX_HTML` string).

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS. The `test_index_returns_html` test should still pass because StaticFiles serves index.html with text/html content type.

- [ ] **Step 6: Run linter and type checker**

Run: `uv run ruff check src/agentroom/server/app.py && uv run python -m pyright src/agentroom/server/app.py`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add src/agentroom/server/app.py
git commit -m "refactor: replace embedded HTML with static file mount for Alpine.js UI"
```

---

### Task 5: Manual verification — full UI test

**Files:** None — manual testing only.

- [ ] **Step 1: Stop the running server if active**

Run: `lsof -ti:4000 | xargs kill 2>/dev/null; sleep 1`

- [ ] **Step 2: Start the server**

Run: `uv run agentroom start --port 4000`

- [ ] **Step 3: Open http://127.0.0.1:4000 in browser**

Expected: See the "Your Agent Team" page with the Agents view. Dark theme, centered layout, no agents yet.

- [ ] **Step 4: Add a CLI agent**

Click "+ Add Agent". Fill in:
- Provider: CLI
- Name: @claude
- Model: sonnet
- Command: claude

Click "Save Agent". Expected: Agent card appears with green text, CLI badge.

- [ ] **Step 5: Test the agent**

Click "Test" on the @claude card. Expected: Shows "OK" in green after a moment.

- [ ] **Step 6: Add a second agent**

Add @gemini (CLI, gemini-2.5-pro, command: gemini).

- [ ] **Step 7: Create a room**

Select both agents (click their chips). Enter goal: "Compare Python vs Rust for CLI tools". Click "Start Room".

Expected: Switches to Room view. System message and phase message visible. "Room" tab appears in nav.

- [ ] **Step 8: Run a round**

Click "Run Round". Wait for both agents to respond.

Expected: Both agent messages appear with colored names, timestamps, and formatted content.

- [ ] **Step 9: Send a user message**

Type "What about Go?" and press Enter.

Expected: Message appears in the room.

- [ ] **Step 10: Verify tab switching**

Click "Agents" tab, then "Room" tab. Expected: Views switch without losing state or messages.

- [ ] **Step 11: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 12: Run all checks**

Run: `uv run ruff check src/ tests/ && uv run python -m pyright src/ && uv run bandit -r src/`
Expected: Ruff 0 errors, Pyright 0 errors, Bandit low-only (existing assert guards)

- [ ] **Step 13: Commit any fixes found during manual testing**

If any issues were discovered and fixed during manual testing, commit them.
