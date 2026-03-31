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
    thinking: false,
    thinkingAgent: '',
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
      if (!this.activeRoom || this.thinking) return;
      this.thinking = true;
      this.thinkingAgent = 'Agent';
      this._scrollToBottom();
      await this._api('POST', `/api/rooms/${this.activeRoom.id}/turn`);
      this.thinking = false;
      this.thinkingAgent = '';
    },

    async runRound() {
      if (!this.activeRoom || this.thinking) return;
      this.thinking = true;
      this.thinkingAgent = 'Agents';
      this._scrollToBottom();
      await this._api('POST', `/api/rooms/${this.activeRoom.id}/round`);
      this.thinking = false;
      this.thinkingAgent = '';
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
        if (!this.messages.find(m => m.id === msg.id)) {
          this.messages.push(msg);
        }
        if (msg.extensions?.['agentroom/phase']) {
          this.activeRoom.phase = msg.extensions['agentroom/phase'].current;
        }
        this._scrollToBottom();
      };
      ws.onclose = () => { this.ws = null; };
      this.ws = ws;
    },

    _scrollToBottom() {
      setTimeout(() => {
        const el = document.querySelector('[x-ref="messageList"]');
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
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
