# AgentRoom — Brainstorm

> A collaborative, open-source, multi-agent platform where AI agents from different providers work together in real time to research, reason, build, and review — just like a human team in a room.

---

## Core Idea

Most AI tools today are a single model answering a single user.  
AgentRoom flips this: **you post a problem to a room full of agents**. They debate, agree, build, and critique — collaboratively — while you watch or participate.

Each collaborative session is called a **Room**.

---

## Principles

- **Open source, for humanity** — no vendor lock-in, self-hostable, MIT licensed
- **Provider-agnostic** — works with Claude, GPT-4o, Gemini, Grok, and any future LLM
- **Leverage existing tools** — built on MCP, A2A, standard protocols; no reinvented wheels
- **Environment-agnostic** — runnable as a web console, CLI, or daemon; same core protocol
- **Auditable** — every message, vote, file change, and decision is logged and reversible
- **Human-in-the-loop optional** — humans can join the room as participants too

---

## The Room

A **Room** is a named, persistent collaborative session.

```
Room: "Build a real-time trading signal engine"
│
├── Participants
│   ├── @claude     (Anthropic Claude)       role: researcher + reviewer
│   ├── @gpt4o      (OpenAI GPT-4o)          role: coordinator + implementer
│   ├── @gemini     (Google Gemini)           role: researcher
│   ├── @grok       (xAI Grok)               role: devil's advocate + reviewer
│   └── @krishna    (Human)                  role: director
│
├── Shared Workspace
│   ├── /files      (read/write for all agents)
│   ├── /memory     (vector store — persistent context)
│   └── /history    (full audit log of all messages + decisions)
│
└── State Machine
    OPEN → RESEARCHING → CONSENSUS → IMPLEMENTING → REVIEWING → DONE
```

---

## Room Lifecycle

### 1. Problem Posting
- Director (human or agent) posts a problem to the room
- Coordinator agent summarizes and frames it for all participants

### 2. Research Phase
- All agents broadcast their independent research/proposals simultaneously (or in round-robin)
- Each agent has tool access: web search, code execution, file read/write, memory recall
- Responses stream in real time to the UI

### 3. Consensus Phase
- Coordinator synthesizes differences between proposals
- Agents vote on the best approach: `+1 agree` / `~0 neutral` / `-1 block` with rationale
- If supermajority (>60%): proceed with winning proposal
- If split: coordinator synthesizes a hybrid → re-vote (max 3 rounds)
- Final decision is pinned to room memory

### 4. Implementation Phase
- One agent **volunteers** (or is assigned by coordinator) as **Implementer**
- Others become **Reviewers** and **Observers**
- Implementer has exclusive write access to `/files` (others read-only during this phase)
- Implementer streams progress updates to the room

### 5. Review Loop
- Each reviewer posts structured feedback: `comment`, `suggestion`, `blocking issue`
- Implementer addresses blocking issues, ACKs suggestions
- Loop continues until all reviewers post `LGTM` or max iterations reached
- Director can override at any time

### 6. Completion
- Final output committed to workspace
- Room summary generated (what was built, key decisions, who contributed what)
- Room can be archived or continued

---

## Inter-Agent Communication Protocol (A2A)

> **Design decision:** Instead of inventing a custom wire protocol, AgentRoom adopts the **Agent-to-Agent (A2A) Protocol v1.0** (Linux Foundation, Apache 2.0) as its inter-agent communication layer. A2A overlaps ~80% with what a custom `AgentMessage` schema would need — standardized message format, task lifecycle, streaming, agent discovery — while also giving us interoperability with the broader A2A ecosystem for free.

### Why A2A?

| Need | Custom schema | A2A v1.0 |
|---|---|---|
| Structured messages (text, code, files) | Would build | `Message` with `Part` (TextPart, DataPart, FilePart) |
| Task lifecycle (phases) | Would build | Task states: SUBMITTED → WORKING → COMPLETED/FAILED/CANCELED/INPUT_REQUIRED |
| Agent discovery | Would build | `AgentCard` at `/.well-known/agent-card.json` |
| Streaming | Would build | SSE via `sendStreamingMessage` |
| Multi-turn conversations | Would build | `contextId` for session continuity |
| Typed artifacts (output files, code) | Would build | `Artifact` with MIME types |
| Authentication | Would build | OAuth2, API Key, mTLS, OpenID Connect |
| Extensibility | Would build | Extensions system for custom metadata |

The only things A2A **doesn't** cover that we need are Room-specific: voting, phase management, role assignment, and consensus. These are implemented as **A2A Extensions** — custom metadata attached to standard A2A messages.

### A2A Tech Stack

A2A is a protocol specification, not a framework. Its tech stack:

| Layer | Technology |
|---|---|
| **Normative data model** | Protocol Buffers (canonical type definitions) |
| **Wire formats** | JSON-RPC 2.0, gRPC, HTTP+JSON/REST (three bindings, all first-class) |
| **Streaming** | Server-Sent Events (SSE) for real-time token streaming |
| **Push notifications** | Webhooks (server-to-server callbacks for async task updates) |
| **Agent discovery** | AgentCard JSON at `/.well-known/agent-card.json` |
| **Card signing** | JWS (JSON Web Signature) + JCS (JSON Canonicalization Scheme) |
| **Authentication** | OAuth 2.0, API Key, HTTP Bearer, mTLS, OpenID Connect |
| **Versioning** | `A2A-Version` header (currently `0.3.0`) |
| **Python SDK** | `a2a-python` — official Python SDK, FastAPI integration, supports all 3 bindings |

### How AgentRoom Maps to A2A

| AgentRoom concept | A2A equivalent | Notes |
|---|---|---|
| Room | A2A Context (`contextId`) | One contextId per room session |
| Agent participant | A2A Agent with `AgentCard` | Each agent exposes a card describing its capabilities |
| Room message | A2A `Message` with `TextPart` | Messages contain typed `Part` objects |
| Code output | A2A `Message` with `DataPart` or `Artifact` | Artifacts are typed outputs with MIME types |
| File attachment | A2A `FilePart` (inline or URI) | |
| Agent identity | A2A `AgentCard` | Name, description, URL, capabilities, auth schemes |
| Streaming response | A2A `sendStreamingMessage` (SSE) | Token-by-token streaming via SSE |
| Phase transition | A2A Extension: `agentroom/phase` | Custom extension on Message metadata |
| Vote | A2A Extension: `agentroom/vote` | Extension carries vote value + rationale |
| Proposal | A2A Extension: `agentroom/proposal` | Extension marks message as a structured proposal |
| Review comment | A2A Extension: `agentroom/review` | Extension carries severity (comment/suggestion/blocking) |
| LGTM | A2A Extension: `agentroom/lgtm` | Approval signal |
| Handoff | A2A Extension: `agentroom/handoff` | Role transfer between agents |
| Thought (internal reasoning) | A2A Extension: `agentroom/thought` | Opt-in: agents subscribe explicitly (not broadcast by default) |
| Confidence | A2A Extension: `agentroom/confidence` | 0–1 float on message metadata |

### AgentRoom Extensions (on top of A2A)

```python
# Room-specific extensions attached to A2A Messages
# These are standard A2A extension objects in the message's extensions map

from enum import StrEnum
from pydantic import BaseModel, Field

class RoomPhase(StrEnum):
    OPEN = "open"
    RESEARCHING = "researching"
    CONSENSUS = "consensus"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    DONE = "done"

class AgentRole(StrEnum):
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    OBSERVER = "observer"
    DIRECTOR = "director"

class PhaseTransition(BaseModel):
    from_phase: RoomPhase = Field(alias="from")
    to_phase: RoomPhase = Field(alias="to")

class PhaseExtension(BaseModel):
    current: RoomPhase
    transition: PhaseTransition | None = None

class VoteExtension(BaseModel):
    value: int  # +1 agree / 0 neutral / -1 block
    rationale: str
    target_message_id: str  # the proposal being voted on

class ProposalExtension(BaseModel):
    title: str
    summary: str

class ReviewSeverity(StrEnum):
    COMMENT = "comment"
    SUGGESTION = "suggestion"
    BLOCKING = "blocking"

class ReviewExtension(BaseModel):
    severity: ReviewSeverity
    file: str | None = None
    line: int | None = None

class LgtmExtension(BaseModel):
    approved_at: float

class HandoffExtension(BaseModel):
    from_role: AgentRole
    to_role: AgentRole
    to_agent: str

class ThoughtExtension(BaseModel):
    visible: bool

class ConfidenceExtension(BaseModel):
    value: float  # 0–1

class CostExtension(BaseModel):
    tokens_used: int
    estimated_cost: float  # USD
    tools_used: list[str]
```

### Agent Discovery via AgentCard

Each agent in a room publishes an A2A `AgentCard` — a JSON document describing what the agent can do. In AgentRoom, the server generates these cards for each configured agent:

```json
{
  "name": "Claude",
  "description": "Anthropic Claude — research, analysis, code review",
  "url": "http://localhost:4000/agents/claude",
  "provider": { "organization": "Anthropic" },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "extensions": [
      "agentroom/phase",
      "agentroom/vote",
      "agentroom/proposal",
      "agentroom/review"
    ]
  },
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["text/plain", "text/markdown", "application/json"],
  "skills": [
    { "id": "research", "name": "Research & Analysis" },
    { "id": "code-review", "name": "Code Review" },
    { "id": "implementation", "name": "Implementation" }
  ]
}
```

### Using the A2A Python SDK (`a2a-python`)

The SDK provides the server and client infrastructure. AgentRoom uses it to:

1. **Expose each agent as an A2A endpoint** — The server implements `AgentExecutor` for each agent adapter, handling incoming messages and returning responses via A2A protocol bindings
2. **Route messages between agents** — The A2A client sends messages between agent endpoints through the SQLite queue
3. **Stream responses** — SSE streaming returns async iterables for real-time token streaming
4. **Handle task lifecycle** — SQLite-backed store tracks task state transitions

```python
from a2a.server.agent_execution import AgentExecutor
from a2a.server.events import EventQueue
from a2a.types import Message

# Each agent adapter implements AgentExecutor
class ClaudeAgentExecutor(AgentExecutor):
    async def execute(self, context, event_queue: EventQueue) -> None:
        # Route incoming A2A message to Anthropic API
        # Stream response back via event_queue
        async for chunk in self.call_anthropic(context.message):
            await event_queue.enqueue_event(chunk)
```

---

## Message Queue & Transport

### Core Model: Async FIFO Pub/Sub over SQLite

All inter-agent communication is routed through a **durable async message queue** backed by SQLite. There is no Redis, no external broker, no runtime dependency. The queue is the single source of truth for every message in a room.

```
Every agent PUBLISHES to the queue.
Every agent SUBSCRIBES to the queue.
All messages are visible to all agents (full mesh pub/sub).
FIFO order is guaranteed by the SQLite sequence number.
```

### Queue Schema

```sql
CREATE TABLE messages (
  seq       INTEGER PRIMARY KEY AUTOINCREMENT,  -- FIFO ordering
  id        TEXT NOT NULL UNIQUE,               -- UUID
  room_id TEXT NOT NULL,
  topic     TEXT NOT NULL,                      -- routing key (see below)
  from_agent TEXT NOT NULL,
  type      TEXT NOT NULL,
  payload   TEXT NOT NULL,                      -- JSON: A2A Message
  created_at INTEGER NOT NULL                   -- Unix ms
);

CREATE TABLE agent_cursors (
  agent_id    TEXT NOT NULL,
  room_id TEXT NOT NULL,
  last_seq    INTEGER NOT NULL DEFAULT 0,        -- last message read
  PRIMARY KEY (agent_id, room_id)
);
```

### Topics (Pub/Sub Routing)

| Topic | Who subscribes | Purpose |
|---|---|---|
| `room/<roomId>` | All agents | Main broadcast channel — all room messages |
| `agent/<agentId>` | That agent only | Direct messages, coordinator directives |
| `phase/<phase>` | All agents | Phase transition signals |
| `system` | All agents | Heartbeat, connect/disconnect events |

Agents **always** subscribe to `room/<roomId>` and their own `agent/<agentId>` topic. This means any agent can read everything said in the room — there are no hidden conversations (except direct coordinator-to-agent directives, which are still logged).

### FIFO Delivery

Agents poll the queue for messages with `seq > last_seq` where `last_seq` is their stored cursor.

```
Agent wakes up → SELECT * FROM messages WHERE seq > :cursor AND topic IN (:subscriptions)
              → process each in seq order
              → UPDATE agent_cursors SET last_seq = :new_seq
              → go back to sleep for poll interval (default: 200ms)
```

This is **not** a busy loop — poll interval is configurable and agents sleep between polls. WebSocket push is layered on top for the web UI (server pushes to browser when the queue has new rows), but agents themselves always use the pull model internally.

### Why SQLite?

- **Zero install** — `sqlite3` is built into the Python standard library, no external dependency needed
- **FIFO guaranteed** — `AUTOINCREMENT` sequence is monotonic and durable
- **WAL mode** — multiple concurrent readers, one writer, no contention
- **Crash-safe** — messages written to disk before agents process them; on restart, agents resume from their cursor
- **Full history** — the queue doubles as the immutable audit log; never truncated, only compacted into summaries
- **Upgrade path** — for distributed deployments across multiple machines, swap SQLite for libSQL (Turso) or PostgreSQL — same schema, same queries, different driver

### Delivery Guarantee

- **At-least-once delivery** — cursors are updated only after successful processing
- If an agent crashes mid-message, it re-reads from the last committed cursor on restart
- Out-of-order delivery is impossible — `seq` is the strict ordering key

### Client Transports (for UI / external processes)

The queue is the internal backbone. External clients connect via:

| Transport | Use Case |
|---|---|
| **WebSocket** | Web console — server pushes queue events to browser in real time |
| **HTTP SSE** | Lightweight read-only observers (dashboards, monitoring) |
| **STDIO** | CLI agent processes communicating with the local server |
| **Named Pipe / UNIX socket** | Local IPC — Windows uses Named Pipes, POSIX uses UNIX sockets (abstracted) |

---

## Three-Protocol Architecture: A2A + MCP + SQLite Queue

AgentRoom uses three complementary protocols, each for what it does best:

| Protocol | Role | Analogy |
|---|---|---|
| **A2A** (Agent-to-Agent) | Wire format for inter-agent messages | "How agents talk" — the language |
| **MCP** (Model Context Protocol) | Tool access for agents | "What agents can do" — the hands |
| **SQLite Queue** | Durable message broker + audit log | "Where messages live" — the memory |

### Why Three?

**A2A** is the message **format** — it defines the structure of messages (Parts, Artifacts), task lifecycle states, agent discovery (AgentCard), streaming (SSE), and authentication. It's the standard envelope that every message is wrapped in.

**MCP** is for **tools** — it gives agents access to files, web search, code execution, memory. MCP is a standard that lets an LLM connect to external tools and data sources via JSON-RPC. Every major AI provider supports it.

**SQLite Queue** is the **broker** — it stores, orders, and delivers A2A messages between agents. A2A defines the message format but not the routing/persistence layer. Our SQLite FIFO queue provides durable at-least-once delivery, crash recovery, and a full audit log.

```
A2A = "what agents say" (message format + protocol)
MCP = "what agents can do" (tool access)
SQLite Queue = "message delivery + persistence" (broker + audit log)
```

| What | Handled by |
|---|---|
| Giving an agent access to tools (file read, web search, code run) | **MCP** |
| Structuring a message with text, code, and files | **A2A** |
| Streaming a response token-by-token | **A2A** (SSE) |
| Storing and ordering messages durably | **SQLite Queue** |
| Agent discovery (what agents exist, what they can do) | **A2A** (AgentCard) |
| Voting, consensus, phase transitions | **A2A Extensions** (agentroom/*) |
| Third-party tool plugins (GitHub, Postgres, Slack) | **MCP** |
| Crash recovery (resume from cursor) | **SQLite Queue** |

These are separate, non-competing concerns. An agent uses **MCP** to read a file, wraps its findings in an **A2A** message, and publishes it to the **SQLite Queue** for delivery to all other agents.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HUMAN INTERFACES                            │
│                                                                     │
│   ┌────────────────────┐          ┌──────────────────────────┐      │
│   │   Web Console      │          │   CLI / Daemon           │      │
│   │  (React + WS)      │          │  agentroom join <id>     │      │
│   └─────────┬──────────┘          └────────────┬─────────────┘      │
└─────────────┼───────────────────────────────────┼───────────────────┘
              │ WebSocket                          │ STDIO / Named Pipe
              ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AGENTROOM SERVER                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 Room State Machine                        │  │
│  │   OPEN → RESEARCHING → CONSENSUS → IMPLEMENTING → REVIEWING  │  │
│  │          (lead agent drives phase transitions)                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              A2A Protocol Layer (a2a-python)                   │  │
│  │                                                               │  │
│  │  · AgentCard registry (/.well-known/agent-card.json)         │  │
│  │  · A2A message format (Message → Part → Artifact)            │  │
│  │  · Streaming via SSE (sendStreamingMessage)                  │  │
│  │  · AgentRoom extensions (vote, phase, review, handoff)       │  │
│  │  · Task lifecycle (SUBMITTED → WORKING → COMPLETED)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │         Async FIFO Message Queue (SQLite — Broker)            │  │
│  │                                                               │  │
│  │  topics:  room/<id>  ·  agent/<id>  ·  phase/<p>  ·  system  │  │
│  │  publish ──────────────────────────────────────── subscribe  │  │
│  │  A2A messages serialized to queue, delivered via cursors      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Context Manager                             │  │
│  │  · assembles context packets per-agent                       │  │
│  │  · monitors token usage vs 50% threshold                     │  │
│  │  · triggers /compact via lead agent                          │  │
│  │  · maintains pinned messages table                           │  │
│  │  · tracks cost per-agent per-room                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
              │                                   │
              │   A2A Message (context packet)     │
              ▼                                   ▼
┌─────────────────────────────┐  ┌───────────────────────────────────┐
│       AGENT ADAPTERS        │  │         AGENT ADAPTERS            │
│                             │  │                                   │
│  ┌──────────┐ ┌──────────┐  │  │  ┌──────────┐  ┌──────────┐     │
│  │ @claude  │ │ @gpt4o   │  │  │  │ @gemini  │  │  @grok   │     │
│  │Anthropic │ │ OpenAI   │  │  │  │  Google  │  │   xAI    │     │
│  │  SDK     │ │  SDK     │  │  │  │   SDK    │  │(OAI-compat│    │
│  │  or CLI  │ │  or CLI  │  │  │  │  or CLI  │  │    API)  │     │
│  └────┬─────┘ └────┬─────┘  │  │  └────┬─────┘  └────┬─────┘     │
└───────┼────────────┼─────────┘  └───────┼─────────────┼───────────┘
        │            │                    │             │
        │            └────────────────────┘             │
        │                      │                        │
        │            (all adapters connect to           │
        │             the same MCP server)              │
        └───────────────────────┬────────────────────── ┘
                                │
                                │  MCP (JSON-RPC 2.0 over STDIO or HTTP+SSE)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AgentRoom MCP SERVER                            │
│                    (shared tools for all agents)                    │
│                                                                     │
│  workspace/          memory/           execution/    room/      │
│  ┌──────────────┐   ┌──────────────┐  ┌──────────┐  ┌──────────┐  │
│  │ read(path)   │   │ store(k,v)   │  │ run(lang │  │broadcast │  │
│  │ write(path)* │   │ search(q)    │  │  code)†  │  │  vote()  │  │
│  │ diff(path)   │   │ recall(k)    │  └──────────┘  │ phase()  │  │
│  │ commit(msg)  │   └──────────────┘                └──────────┘  │
│  └──────────────┘                                                   │
│   * write enforces phase-based role lock                            │
│   † sandboxed: Docker / Deno / e2b — disabled by default            │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌────────────┐ ┌───────────────┐
       │  SQLite DB │ │  Git Repo  │ │  sqlite-vec   │
       │ (queue,    │ │ /workspace │ │ (vector memory│
       │  state,    │ │  /files    │ │  for semantic │
       │  history,  │ │            │ │  search)      │
       │  pinned)   │ └────────────┘ └───────────────┘
       └────────────┘
```

### How a Single Agent Turn Flows

```
1. Server assembles context packet for @claude:
      [system prompt] + [pinned decisions] + [compact summary] + [recent A2A msgs]

2. Server sends A2A Message to @claude's adapter via AgentExecutor

3. @claude adapter calls Anthropic API (or CLI) with the context packet

4. @claude decides it needs to read a file → calls MCP tool: workspace.read("src/main.ts")
      MCP server reads the file, returns contents to @claude

5. @claude formulates its response

6. @claude adapter wraps response as A2A Message (with Parts + Extensions)
   → publishes to SQLite queue topic: room/<roomId>

7. Queue fans out to all subscriber cursors (all other agents + UI)

8. Each other agent picks up the A2A message on their next poll cycle

9. UI immediately receives it via WebSocket push
```

### Why Three Separate Protocols (A2A + MCP + SQLite Queue)?

```
A2A              =  "how agents talk"                    (message format + wire protocol)
SQLite Queue     =  "where messages are stored/routed"   (broker + persistence)
MCP              =  "what agents can do in the world"   (tool use)
```

Keeping them separate means:
- A2A gives us instant compatibility with any A2A-compliant agent ecosystem
- Any MCP-compatible tool (GitHub, Postgres, Slack, web browser) can be plugged in without touching the messaging layer
- The SQLite queue can be swapped for a distributed broker (libSQL/Turso, PostgreSQL) without changing the A2A message format
- External A2A agents can join a room without needing our SQLite queue — they communicate via standard A2A HTTP endpoints

---

## Tool Access (via MCP)

All agents connect to the shared AgentRoom MCP server. Tools are grouped into namespaces:

| Tool | Description |
|---|---|
| `workspace.read(path)` | Read a file from shared workspace |
| `workspace.write(path, content)` | Write a file (enforces phase-based role lock) |
| `workspace.diff(path)` | Get git diff for a file |
| `workspace.commit(msg)` | Commit current workspace state |
| `memory.store(key, value)` | Store to vector memory |
| `memory.search(query)` | Semantic search over room memory |
| `memory.recall(key)` | Exact key lookup |
| `search.web(query)` | Web search (via pluggable search provider) |
| `code.run(lang, code)` | Execute code in sandbox (disabled by default) |
| `room.broadcast(msg)` | Publish a message to the room queue |
| `room.vote(msgId, vote)` | Cast a vote (+1 / 0 / -1) |
| `room.phase()` | Get current room phase (read-only) |

Third-party MCP servers (GitHub, Linear, Postgres, browser, etc.) can be chained in via the standard MCP proxy pattern — agents see them as additional tool namespaces with no changes to the core.

---

## Lead Agent (Coordinator)

The lead agent is a **full peer participant who also has coordination responsibilities**. It contributes its own research, opinions, and votes exactly like every other agent — coordination is an additional hat, not a replacement for participation.

> The lead agent is not a passive moderator. It has opinions and it shares them. It just also has the responsibility to ensure the room functions fairly and reaches decisions.

### Selection

**User-selected is the preferred and recommended mode.** The room author explicitly names the lead agent:
```yaml
room:
  lead: "@claude"   # preferred — chosen by the author
```

This is preferred because:
- The author knows which model is best-suited for coordination in their use case
- A stable lead provides consistency across the full room lifecycle
- Agents and humans can build trust with a known lead

**Auto-select fallback** (if `lead` is omitted): The server picks the most capable available agent based on declared model tier. This is the fallback, not the default recommendation.

**Mid-room replacement:** Any participant (human or agent) can call a re-vote on the lead if it is perceived as biased. Requires a majority. The current lead may also voluntarily step down.

### The Lead Is a Full Contributor

During every phase, the lead agent does two things:

**1. Contributes as a peer** (same as all other agents):
- Posts its own research and proposals in the research phase
- Casts its own vote during consensus (equal weight to all others)
- Provides its own code review comments

**2. Coordinates** (additional responsibilities):
- **Queue management** — decides turn order within each phase, manages speaking windows so no agent dominates
- **Polling** — opens and closes votes, tallies results transparently
- **Conflict resolution** — when a vote is split after max rounds, the lead casts the deciding vote with a required written rationale (logged permanently)
- **Consolidation** — synthesizes the room's outputs into structured summaries at phase boundaries
- **Context compaction** — triggers `/compact` signals when any agent is approaching context limits (see Context Management)
- **Phase transitions** — declares phase changes, announces the implementer, opens review rounds
- **Room summary** — generates the final summary at completion

### Fairness Rules

- The lead's **vote carries equal weight** to all other agents — coordination does not grant extra voting power
- The deciding vote (deadlock resolution) is the **only exception**, and it is always logged with rationale
- The lead must publish its own research/proposals **before** it reads others' (prevents anchoring bias)
- All coordination actions are written to the queue as `system` messages — nothing the lead does is private
- If the lead is also the implementer, another agent is temporarily assigned polling/phase duties for that review cycle

---

## Interfaces

### Web Console
- One panel per agent (like a group chat, but structured)
- Real-time streaming, markdown + code rendering
- Phase banner showing current room state
- Vote tally visible to all
- File tree panel for shared workspace
- Director controls: pause, redirect, override, end

### CLI Mode
- Multiple terminal windows, one per agent
- Shared session via STDIO or local socket
- Color-coded agent output
- `agentroom join <room-id>` to attach

### Daemon Mode
- Agents run as persistent background processes
- Room server coordinates them
- Human can drop in and out via CLI or web

---

## Why This Is Different

| Feature | AutoGen | CrewAI | MetaGPT | AgentRoom |
|---|---|---|---|---|
| Multi-provider (GPT + Claude + Gemini + Grok) | No | No | No | **Yes** |
| Standard wire protocol (A2A) | No | No | No | **Yes** |
| Real-time broadcast + streaming | Partial | No | No | **Yes** (SSE via A2A) |
| Consensus voting | No | No | No | **Yes** |
| Shared file workspace (git-backed) | No | No | Partial | **Yes** |
| Human as peer participant | No | Partial | No | **Yes** |
| Open protocol (not framework-specific) | No | No | No | **Yes** (A2A + MCP) |
| CLI + Web + Daemon | No | No | No | **Yes** |
| Single binary, zero-install | No | No | No | **Yes** |
| Cost tracking | No | No | No | **Yes** |

---

## Design Issues & Mitigations

These are real problems in the current design that must be resolved before implementation begins.

---

### Issue 1 — UNIX Sockets Don't Work on Windows
**Problem:** The transport layer lists "STDIO / UNIX socket" as a mode. UNIX domain sockets are not available on Windows (without WSL). Named Pipes are the Windows equivalent but have a different API.
**Mitigation:** Abstract the local IPC transport behind a `LocalTransport` interface. On POSIX: UNIX socket. On Windows: Named Pipe (`\\.\pipe\agentroom-<id>`). Node.js `net` module handles both if written correctly. Contributors should never call sockets directly — always via the transport abstraction.

---

### Issue 2 — Consensus Threshold Breaks With Small Agent Counts
**Problem:** A 60% supermajority with 4 agents requires 2.4 → effectively 3 votes. With only 2 agents, a 60% threshold is mathematically impossible to reach in a split (you'd need 1.2 agents). The fixed percentage doesn't scale.
**Mitigation:** Make the threshold dynamic:
```
required_votes = ceil(n_agents * 0.6)   // minimum 2, maximum n_agents - 1
```
With 2 agents: requires 2 (both must agree — unanimous for small rooms). With 4: requires 3. With 10: requires 6. Also: after max re-vote rounds, coordinator casts the deciding vote (logged and rationale required).

---

### Issue 3 — Concurrent Streaming Creates a Noisy UI
**Problem:** During research phase, all agents stream simultaneously. The web console will show interleaved tokens from multiple models at once — unreadable. But full sequential responses feel slow and kills the "live room" feeling.
**Mitigation:** Two modes, user-configurable:
- **Waterfall mode (default):** Agents respond one at a time in turn order. Each streams fully before the next starts. Smooth, readable.
- **Parallel mode:** All agents buffer internally and publish complete messages together. No interleaving in the UI, but agents work in parallel (faster for large rooms).
The broker handles buffering; the UI never sees partial overlap.

---

### Issue 4 — Shared File Write Locks Are Unenforced
**Problem:** "Implementer has exclusive write access to /files" — but the MCP server as designed has no locking mechanism. Two agents could write the same file simultaneously via separate MCP connections. OS-level file locks don't work across processes reliably on all platforms.
**Mitigation:** The MCP workspace server maintains an in-memory write lock table per room. `workspace.write()` checks the lock: if the calling agent doesn't hold the implementer role for this phase, the call is rejected with a `PERMISSION_DENIED` error. Lock is granted at phase transition, released at handoff.

---

### Issue 5 — Context Window Will Overflow on Long Rooms
**Problem:** As a room progresses through research → consensus → implementation → review cycles, the accumulated message history could easily exceed 200K tokens. Agents receiving the full history will hit context limits or become very expensive.
**Mitigation:** The coordinator runs a **rolling context summarizer** at each phase transition:
- Full verbose log stored in `/history` (never truncated)
- Agents receive a **context packet** instead of raw history: phase summary + last N messages + pinned decisions + relevant memory search results
- Context packet is assembled by the broker per-agent per-message

---

### Issue 6 — Code Execution Has No Sandbox
**Problem:** `code.run(lang, code)` is listed as an MCP tool but sandbox design is deferred to "open questions". This is a critical security gap — agents executing arbitrary code on the host machine is dangerous by default.
**Mitigation:** Code execution must be sandboxed from day one:
- **Default:** Disabled. Must be explicitly enabled per room with `capabilities: [code_exec]`
- **Sandbox options:** Docker container (if available), Deno subprocess with `--allow` flags, or e2b.dev cloud sandbox
- **No sandbox available:** Tool call returns an error, not silent execution
- Resource limits enforced: max 30s execution, 512MB memory, no network by default

---

### Issue 7 — CLI STDIO Mode Is Fragile
**Problem:** The `claude`, `gemini`, and `openai` CLIs are designed for interactive human use, not programmatic STDIO piping. Their output formats can change between versions, they may prompt for confirmation, and reusing a long-lived process may have undefined behavior.
**Mitigation:**
- CLI mode is explicitly a **best-effort, community-maintained** adapter — not the primary path
- Each CLI adapter must specify the exact version range it supports and pin `--output-format` flags
- CLI adapters include a `verify()` method that runs a test prompt and validates the output can be parsed
- API mode is always preferred; CLI mode is a fallback for users without API keys
- A warning is shown at startup when using CLI mode adapters

---

### Issue 8 — Heavy Default Dependencies ✓ Resolved by Architecture
**Problem:** The design previously referenced Redis (pub/sub) and ChromaDB (vector store) as core infrastructure. Redis requires a running server. ChromaDB is Python-based.
**Resolution:** The message queue architecture is now SQLite-native. Redis is no longer in the default stack.
- **Default (local):** SQLite in WAL mode for the queue, state, history, and pinned messages. `sqlite-vec` extension for vector search in memory. Zero external services.
- **Distributed upgrade:** Replace SQLite with libSQL (Turso) or PostgreSQL — same schema and queries, different driver. Enabled via `DATABASE_URL` env variable. No code changes required in the application layer.

---

### Issue 9 — No Crash Recovery / Room Checkpointing
**Problem:** If the room server crashes mid-implementation, all in-progress state is lost. Agents would need to start over. This is especially bad for long-running rooms.
**Mitigation:** State machine is persisted to SQLite after every transition. On server restart, rooms in non-terminal states are automatically resumed. Agents re-join with their last known role and context packet. The `/history` directory is the source of truth.

---

### Issue 10 — No Clear Agent Failure Handling
**Problem:** What happens if an agent stops responding mid-room? (API timeout, rate limit, CLI crash.) Currently unspecified. Could stall the whole room.
**Mitigation:**
- Each agent has a configurable `timeout` per turn (default: 120s)
- On timeout: agent is marked `UNRESPONSIVE`, their turn is skipped, coordinator is notified
- After 3 consecutive timeouts: agent is marked `OFFLINE`, removed from rotation
- Coordinator automatically redistributes that agent's role to the next available participant
- Human director receives an alert
- **For lead agent failure specifically, see the Lead Failure Protocol below**

---

### Issue 11 — Lead Agent Failure Protocol

**Problem:** The lead agent is the single point of coordination inside a room. If it crashes, lags, or drifts, the entire room stalls. General agent failure handling (Issue 10) isn't sufficient — the lead requires a dedicated succession protocol because it holds coordination state (current phase, pending actions, vote tallies).

**Three failure modes:**

| Failure | Symptom | Severity |
|---|---|---|
| **Crash** | Lead's adapter stops responding entirely (API down, process killed, OOM) | Critical — room is headless |
| **Lag** | Lead is responding but extremely slowly (rate limited, overloaded, long thinking) | Medium — room stalls but isn't broken |
| **Drift** | Lead responds but makes bad coordination decisions (hallucinating phases, unfair turns) | Subtle — room continues but poorly |

#### Detection: Passive-First, Active-Last (4-Tier Health Check)

> **Core principle:** The cheapest health check is no health check — just observe what's already happening. Burning tokens on heartbeat pings is wasteful. Check the free things first, escalate only when necessary.

**Tier 0 — Implicit Heartbeat (Free, Always On)**

Don't ping at all. Just observe normal activity. The lead sends messages during normal operation — responses, phase transitions, vote tallies, consolidation summaries. Every one of these is proof of life.

```
last_activity[lead] = timestamp of lead's last published message to the queue

If now() - last_activity[lead] < inactivity_threshold (default: 5 min)
  → Lead is alive. Do nothing.
```

During active phases (research, consensus, review), the lead is constantly talking. This covers 90% of operating time with zero cost.

**Tier 1 — Process Ping (Free, On Demand)**

If the lead has been silent past the inactivity threshold, check if the adapter process is alive via local IPC:

```
Server → IPC ping to lead's adapter process (Unix socket / Named Pipe)
       → "Are you there?" (raw bytes, not an LLM call)
       → Adapter responds with { status: "idle", uptime: 3600 }
```

Zero tokens, zero network. The adapter process responds to a health check without touching the LLM API:

```python
def handle_health_check(self) -> HealthStatus:
    return HealthStatus(
        status="idle",                    # idle | busy | error
        last_api_call=self.last_api_call_at,  # when we last called the provider
        last_api_result="success",        # success | rate_limited | error | timeout
        provider_latency=self.avg_latency,  # rolling average
        uptime=time.monotonic() - self.start_time,
    )
```

If process responds → lead is alive, just idle. No further check.
If process doesn't respond → process crashed. Skip to failover.

**Tier 2 — Provider Health Check (Nearly Free, Rare)**

If the process is alive but its last API call failed, check if the provider is reachable using lightweight model-listing endpoints (NO tokens consumed):

```
Anthropic:  GET https://api.anthropic.com/v1/models          → 200 OK
OpenAI:     GET https://api.openai.com/v1/models              → 200 OK
Google:     GET https://generativelanguage.googleapis.com/v1/models → 200 OK
xAI:        GET https://api.x.ai/v1/models                    → 200 OK
Ollama:     GET http://localhost:11434/api/tags                → 200 OK
```

| Result | Meaning | Action |
|---|---|---|
| 200 OK | Provider is up, API key valid | Lead is fine, just slow or idle |
| 401/403 | API key expired/revoked | Alert human |
| 429 | Rate limited | Not a failure — wait for `Retry-After`, inform room |
| 5xx | Provider outage | Not the lead's fault — wait or failover to different provider |
| Timeout | Network issue | Retry with backoff, then escalate |

**Tier 3 — Active Probe (Costs Tokens, Last Resort, Very Rare)**

Only if all above are inconclusive. Server sends a minimal A2A message:

```
"Please acknowledge: respond with 'ACK' and your current status."
~20 input tokens + ~10 output tokens = ~$0.0001 per probe.
```

Fires extremely rarely — maybe once per hour in a long idle room.

**Frequency summary:**

| Tier | Trigger | Frequency | Cost |
|---|---|---|---|
| 0 (implicit) | Every lead message | Continuous | $0 |
| 1 (process ping) | Lead silent > 5 min | Few times per long room | $0 |
| 2 (provider check) | Process alive + last call failed | Rare | $0 (HTTP GET) |
| 3 (active probe) | Everything else inconclusive | Very rare | $0.0001 |

#### Succession Protocol

```
Phase 1: SUSPECTED (Tier 1 or 2 failed)
  │
  │  Server sends direct ping via agent/<leadId> topic
  │  Wait 30s for response.
  │
  ├── Lead responds → false alarm, resume
  │
  └── No response → requires 2 consecutive failures (no single-failure failover)
      │
Phase 2: CONFIRMED DOWN
      │
      Server publishes: "[SYSTEM] Lead @claude is unresponsive. Initiating failover."
      Room enters FAILOVER sub-state. Current phase is PAUSED.
      │
Phase 3: SUCCESSION
      │
      ├── Option A: Pre-configured fallback (preferred)
      │   room.yaml: lead: "@claude", fallback: ["@gpt4o", "@gemini"]
      │   Server activates next in fallback list
      │
      └── Option B: No fallback configured
          Server picks agent with: (1) lowest failure count, (2) highest remaining
          context budget, (3) longest uptime
      │
Phase 4: HANDOVER
      │
      Server assembles a handover packet for new lead:
      │
      │   {
      │     room: { id, goal, currentPhase },
      │     previousLead: { agentId, failureReason, lastActiveAt },
      │     state: {
      │       pinnedDecisions: Message[],      // all pinned messages
      │       recentMessages: Message[],       // last 20 for context
      │       activeVotes?: { proposalId, tallySoFar, roundNumber },
      │       agentRoster: [{ agentId, role, status }],
      │       pendingActions: string[]         // e.g., "transition to implementing"
      │     }
      │   }
      │
      New lead receives packet as agentroom/handover extension message
      New lead acknowledges within 30s
      │
      ├── ACK → new lead active, room resumes
      └── No ACK → try next fallback, or PAUSE for human
      │
Phase 5: RESUMED
      │
      New lead posts: "Taking over as coordinator. State: [phase]. Continuing."
      Room exits FAILOVER.
```

#### Handling Lag (Not Crash)

```
Lead response exceeds lag_threshold (90s) for 2+ consecutive turns
  │
  ├── If non-blocking phase (research) → warn, continue
  └── If blocking (mid-consensus, phase transition) → failover
  │
  Human director can override: keep lagging lead or force failover
```

#### Handling Drift (Bad Coordination)

```
Any agent or human can call: /vote-no-confidence @claude
  │
  Special vote: all non-lead agents vote keep/replace
  Majority (>50%) → graceful handover (lead is alive, transfers state directly)
  Lead cannot vote on its own removal
  Vote is logged permanently
```

#### Old Lead Recovers

- If room already has a new lead → old lead re-joins as regular participant (never auto-reclaims)
- If room is still in FAILOVER (no successor found) → old lead resumes as lead

#### Safeguards Against False Positives

1. **Never failover on a single missed check** — require 2 consecutive failures
2. **Distinguish provider-down from lead-down** — if `GET /v1/models` returns 5xx, the provider is down, not the lead. Failover to a different provider, not the same one
3. **Grace period** — no flip-flopping. Once failover completes, it's final
4. **Exponential backoff** — `5s → 15s → 45s → declare unresponsive`. Don't hammer the provider
5. **Always inform** — every escalation publishes a system message. No surprise failovers

#### Configuration

```yaml
room:
  lead: "@claude"
  failover:
    fallback: ["@gpt4o", "@gemini"]

    # Tier 0: implicit heartbeat
    inactivity_threshold: 300         # seconds (5 min) before checking

    # Tier 1: process-level ping
    process_ping_timeout: 5           # seconds for IPC response

    # Tier 2: provider health check
    provider_check_retries: 2
    provider_check_backoff: [5, 15, 45]  # seconds between retries

    # Tier 3: active probe
    probe_timeout: 60                 # seconds to wait for ACK

    # General
    consecutive_failures: 2           # require 2 failures before failover
    auto_failover: true               # false = always wait for human
```

---

## Additional Features (from Design Review)

These features were identified during the design review as critical additions not covered by the original brainstorm.

---

### Feature 1 — Cost Tracking & Budgeting

Every API call costs money. With 4–6 agents in a long-running room, costs compound fast.

**Design:**
- Each adapter reports token usage via the `agentroom/cost` extension on every A2A message
- The Context Manager maintains a running cost ledger per-agent per-room in SQLite
- Room config supports hard and soft budgets:

```yaml
room:
  budget:
    soft_limit: 5.00        # USD — warn the director
    hard_limit: 20.00       # USD — pause the room, require human approval to continue
    per_agent_limit: 5.00   # USD — individual agent cap
```

```sql
CREATE TABLE cost_ledger (
  room_id   TEXT NOT NULL,
  agent_id      TEXT NOT NULL,
  message_seq   INTEGER NOT NULL,
  tokens_input  INTEGER NOT NULL,
  tokens_output INTEGER NOT NULL,
  estimated_usd REAL NOT NULL,
  created_at    INTEGER NOT NULL
);
```

- Cost-per-token rates are maintained per-provider and auto-updated
- The web UI shows a running cost meter in the room header
- When soft limit is hit: director gets a notification, room continues
- When hard limit is hit: room pauses, enters `INPUT_REQUIRED` state (A2A task state)

---

### Feature 2 — Rate Limit Handling

Different providers have different rate limits. Hitting a 429 mid-room shouldn't crash the system.

**Design:**
- Each adapter implements a `RateLimitStrategy` with exponential backoff
- On 429: adapter enters a cooldown state, publishes a system message to the room ("@claude is rate-limited, retrying in 30s")
- Coordinator is aware and can skip the rate-limited agent's turn, continuing with others
- Provider-specific retry headers (`Retry-After`, `x-ratelimit-reset`) are respected
- Configurable max retries (default: 5) before marking agent as UNRESPONSIVE

---

### Feature 3 — Agent System Prompts (RoomPromptBuilder)

How does each agent know its role, the room goal, and how to behave? The raw A2A message doesn't carry this — it needs to be assembled per-agent as a system prompt.

**Design:**
```python
class RoomPromptBuilder:
    def build(self, agent: AgentAdapter, room: Room) -> str:
        lines = [
            f'You are {agent.card.name}, participating in a room: "{room.goal}"',
            f'Your role: {room.get_role_for(agent)}',
            f'Current phase: {room.phase}',
            f'Other participants: {", ".join(a.card.name for a in room.agents)}',
            'Rules:',
            '- Respond in markdown. Be concise.',
            '- When voting, use the format: +1/0/-1 with rationale',
            f'- You have access to tools via MCP: {", ".join(agent.capabilities)}',
        ]
        if room.phase == RoomPhase.REVIEWING:
            lines.append('- Post structured review: comment/suggestion/blocking')
        return "\n".join(lines)
```

The system prompt is assembled fresh for every agent turn and injected as the first element of the context packet. It is NOT stored in the queue — it's ephemeral and changes as the room progresses.

---

### Feature 4 — Sub-Task Decomposition

Complex problems benefit from being broken into parallel sub-tasks. Currently the design only supports a single linear flow.

**Design:**
- The lead agent can decompose a problem into sub-tasks during the research or implementation phase
- Each sub-task becomes a **child A2A Task** (A2A supports task hierarchies via `contextId`)
- Sub-tasks can be assigned to different agents working in parallel
- Results are collected and merged by the lead agent before proceeding

```
Room Task: "Build a trading signal engine"
├── Sub-task 1: "Research technical indicators" → @gemini (parallel)
├── Sub-task 2: "Design the API schema" → @claude (parallel)
├── Sub-task 3: "Survey existing implementations" → @grok (parallel)
└── Merge: Lead agent consolidates results → proceed to consensus
```

This is opt-in. Simple rooms use the default linear flow. The lead agent decides whether decomposition is beneficial.

---

### Feature 5 — Replay / Debug Mode

When a room produces unexpected results, you need to understand what happened. Replaying the message history step-by-step is essential for debugging.

**Design:**
- `/replay <room-id>` — replays all messages in the room in chronological order, showing agent-by-agent responses
- `/replay <room-id> --from <seq> --to <seq>` — replay a specific range
- `/replay <room-id> --agent @claude` — show only one agent's messages
- The SQLite queue is the immutable audit log — replay reads directly from it
- Web UI supports a "timeline scrubber" that lets you step through the room visually
- Export to JSON/Markdown for sharing and analysis

---

### Feature 6 — Thought Messages Are Opt-In

The original design had `thought` messages broadcast to all agents. With 4+ agents, this creates massive noise — every agent's internal reasoning floods every other agent's context.

**Design:**
- Thought messages use the `agentroom/thought` extension and are **not broadcast by default**
- Agents must explicitly subscribe to thoughts: `subscribe: ["room/<id>", "thoughts/<id>"]`
- The lead agent always receives thoughts (for coordination purposes)
- The web UI shows thoughts in a collapsible "thinking" panel — visible but not intrusive
- Thoughts are still stored in the SQLite queue for replay/audit purposes

---

## Open Questions (To Brainstorm)

1. **Consensus algorithm** — after mitigating the threshold math, should we also support confidence-weighted voting (e.g., an agent with 0.9 confidence counts for more than one with 0.4)?
2. **Trust model** — should agents be able to reject tasks on ethical grounds? Who arbitrates?
3. ~~**Cost management** — multi-provider means multiple API bills. Token budgets per agent per room?~~ **→ Resolved: See Feature 1 (Cost Tracking & Budgeting)**
4. **Persistent agent memory** — should agents remember past rooms? Cross-room learning creates compounding value but also compounding bias.
5. **Plugin system** — how do third parties add new agent providers or new tools without forking the repo? (A2A AgentCard + MCP tool registration may be sufficient)
6. **Room templates** — pre-configured rooms for common use cases (SDLC, research, trading analysis)?
7. **Agent personas** — should agents maintain consistent personas across rooms for predictability?
8. **Observability** — structured logs, traces, metrics for production deployments?
9. **A2A ecosystem interop** — should AgentRoom rooms be discoverable by external A2A clients? (i.e., expose the room itself as an A2A agent)
10. **Multi-tenant / auth** — should AgentRoom support multiple users with separate rooms? OAuth for the web UI?

---

## Potential Use Cases

- **Software development** — full SDLC from spec to deployed code
- **Research synthesis** — aggregate and debate papers, produce literature review
- **Trading & analysis** — multiple models analyzing signals, debating risk
- **Creative writing** — collaborative worldbuilding, plot critique
- **Security audits** — red team / blue team agent roles
- **Legal/contract review** — specialized agents with domain knowledge
- **Education** — students watch agents reason through a problem in real time

---

## Agent Adapters

Every agent in a room is backed by an **adapter** — a thin wrapper that translates the AgentRoom protocol into whatever that provider actually speaks. The same adapter interface is used regardless of whether the agent is accessed via API key or a locally installed CLI tool.

### The Adapter Interface

The adapter interface wraps provider-specific SDKs behind a unified A2A-compatible interface. Each adapter implements `AgentExecutor` from the `a2a-python` SDK and adds AgentRoom-specific context management.

```python
from abc import ABC, abstractmethod
from a2a.server.agent_execution import AgentExecutor
from a2a.server.events import EventQueue
from a2a.types import Message, AgentCard
from pydantic import BaseModel

class ContextBudget(BaseModel):
    max_tokens: int           # hard context window limit for this model
    warning_threshold: float  # when to trigger compaction (default: 0.50 = 50% full)
    reserved_for_response: int  # tokens to keep free for the response

class CompactedContext(BaseModel):
    summary: str              # compressed representation of the history
    pinned_messages: list[Message]  # A2A messages that must never be dropped
    dropped_count: int        # how many messages were summarized away
    token_estimate: int       # estimated tokens in the resulting context

class AgentAdapter(AgentExecutor, ABC):
    card: AgentCard           # A2A AgentCard for this agent

    # Lifecycle
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_available(self) -> bool: ...  # health-check before joining room

    # Core: A2A AgentExecutor — receives A2A messages, streams responses
    @abstractmethod
    async def execute(self, context, event_queue: EventQueue) -> None: ...

    # Context management — each adapter handles compaction for its own model
    @abstractmethod
    async def compact(self, history: list[Message], budget_tokens: int) -> CompactedContext: ...

    @abstractmethod
    def context_budget(self) -> ContextBudget: ...
```

Every provider implements this interface. The room server doesn't know or care whether the underlying agent is an API call or a child process.

**The `compact()` method is provider-specific by design.** Each model has different context window sizes, different strengths at summarization, and different token counting methods. Claude's adapter compresses differently than GPT-4o's — each knows its own model best.

---

### Two Access Modes

#### Mode 1 — API Key (Cloud)
The adapter calls the provider's HTTP API directly using their official SDK.
Best for: production, reliable latency, access to latest models.

```
AgentRoom → Anthropic SDK  → api.anthropic.com
AgentRoom → OpenAI SDK     → api.openai.com
AgentRoom → Google AI SDK  → generativelanguage.googleapis.com
AgentRoom → xAI HTTP API   → api.x.ai
AgentRoom → OpenAI-compat  → any OpenRouter / Together / Groq endpoint
```

Config (per agent in `room.yaml`):
```yaml
agents:
  - name: "@claude"
    provider: anthropic
    model: claude-opus-4
    access:
      mode: api
      apiKey: ${ANTHROPIC_API_KEY}   # from env, never hardcoded
```

#### Mode 2 — Local CLI (Process)
The adapter spawns the provider's official CLI as a child process and communicates over **STDIO**. No API key needed if the CLI is already authenticated.

```
AgentRoom → spawn("claude")  → STDIO ↔ Claude CLI process
AgentRoom → spawn("gemini")  → STDIO ↔ Gemini CLI process
AgentRoom → spawn("chatgpt") → STDIO ↔ OpenAI CLI process
AgentRoom → spawn("ollama")  → STDIO ↔ Ollama (fully local)
```

Config:
```yaml
agents:
  - name: "@claude"
    provider: anthropic
    model: claude-opus-4
    access:
      mode: cli
      bin: claude          # PATH lookup, or absolute path
      args: ["--output-format", "stream-json"]
```

#### Mode 3 — Local Model (Ollama / llama.cpp)
Special case of CLI/API mode — fully offline, no external calls. Ollama exposes an OpenAI-compatible API on `localhost:11434`, so the OpenAI adapter handles it with a custom `baseURL`.

```yaml
agents:
  - name: "@local-llama"
    provider: ollama
    model: llama3.3
    access:
      mode: api
      baseURL: http://localhost:11434/v1
      apiKey: ollama        # placeholder, Ollama doesn't require a real key
```

---

### Auto-Detection (Priority Order)

If `access.mode` is not specified, the adapter auto-detects in this order:

```
1. API key present in env?          → use API mode
2. CLI binary found in PATH?        → use CLI mode
3. Ollama running on localhost?     → use Ollama mode
4. None of the above?               → agent marked unavailable, skipped in room
```

This means a contributor can clone the repo, run `agentroom start`, and whatever agents they have configured (even just one) will participate. No configuration required beyond what they already have.

---

### Provider Support Matrix

| Provider | API Mode | CLI Mode | Local/Offline | Notes |
|---|---|---|---|---|
| **Anthropic (Claude)** | `@anthropic-ai/sdk` | `claude` CLI | No | CLI ships with `--output-format stream-json` |
| **OpenAI (GPT-4o)** | `openai` SDK | `openai` CLI | No | |
| **Google (Gemini)** | `@google/generative-ai` | `gemini` CLI | No | |
| **xAI (Grok)** | HTTP (OpenAI-compat) | No official CLI | No | Uses OpenAI SDK with custom baseURL |
| **Ollama** | OpenAI-compat REST | `ollama run` | **Yes** | Best for fully offline rooms |
| **LM Studio** | OpenAI-compat REST | No | **Yes** | GUI + local server |
| **Groq / Together** | OpenAI-compat REST | No | No | Fast inference, drop-in |
| **Custom** | OpenAI-compat REST | Any binary | Optional | Plugin interface |

---

### CLI Mode: How STDIO Works

When in CLI mode, the adapter:

1. Spawns the binary as a child process with `stdin` / `stdout` / `stderr` piped
2. Writes the prompt (formatted as the provider's CLI expects) to `stdin`
3. Reads streaming response chunks from `stdout`
4. Parses provider-specific output format into `AgentMessage` chunks
5. On disconnect, sends EOF to `stdin` and waits for the process to exit cleanly

The adapter handles **re-use**: for CLI mode, a single long-running process is preferred over spawning per-message (where the CLI supports it), to avoid cold-start latency.

---

---

## Context Management & Compaction

Context window overflow is one of the most likely failure modes for long-running rooms. Every model has a hard limit. Once the accumulated history approaches it, the model either errors or starts losing coherence. Compaction is not optional — it is a first-class feature.

### How It Works

```
1. Each agent's adapter tracks its own token usage against contextBudget()
2. When usage crosses warningThreshold (default: 50%), the adapter emits a
   CONTEXT_WARNING event to the room server
3. The lead agent receives the warning and schedules a /compact cycle
4. /compact is an ordered operation — no new messages are processed during compaction
5. Each adapter runs its own compact() method independently
6. The compacted summary + pinned messages replace the raw history in that agent's context
7. The raw history is never deleted from SQLite — only the agent's working context shrinks
8. A COMPACT_DONE event is published to the room so all agents know the context was reset
```

### Pinned Messages (Never Compacted)

Certain messages are pinned and must survive every compaction cycle:
- Phase transition decisions
- Consensus votes and outcomes
- Assigned roles (who is implementing what)
- Director overrides
- LGTM approvals

Pinned messages are stored in a separate SQLite table and re-injected at the top of every context packet:

```sql
CREATE TABLE pinned_messages (
  seq         INTEGER NOT NULL,  -- references messages.seq
  room_id TEXT NOT NULL,
  reason      TEXT NOT NULL      -- why it was pinned
);
```

### Per-Provider Compaction Strategy

Each adapter implements compaction differently:

| Provider | Strategy |
|---|---|
| **Claude** | Asks the model to summarize its own previous turns into a structured briefing |
| **GPT-4o** | Uses the `system` message slot for a rolling summary; older turns dropped |
| **Gemini** | Leverages the long context window; compacts only the earliest 30% of history |
| **Grok** | Similar to GPT-4o — rolling system summary |
| **Ollama (local)** | Aggressive compaction — small models have tight limits (4K–32K tokens) |

### `/compact` as a Manual Command

The human director (or any agent) can also trigger compaction manually:
```
/compact              → compact all agents' contexts now
/compact @claude      → compact only @claude's context
/compact --pin <id>   → pin a specific message before compacting
```

### Context Packet (What Agents Actually Receive)

Agents never receive the raw SQLite queue dump. They receive a **context packet** assembled by the server:

```
┌─────────────────────────────────────────────┐
│ 1. System prompt (room goal, their role)│
│ 2. Pinned decisions (always present)        │
│ 3. Compact summary (if compaction has run)  │
│ 4. Recent messages (last N, up to 50% of budget) │
│ 5. The new incoming message                 │
└─────────────────────────────────────────────┘
```

The server assembles this packet per-agent per-message using the agent's `contextBudget()` to stay within limits.

---

### Adding a Custom Adapter

Any agent that speaks an OpenAI-compatible API can be added in config with zero code:

```yaml
agents:
  - name: "@my-model"
    provider: openai-compat
    model: my-model-name
    access:
      mode: api
      baseURL: https://my-inference-server.internal/v1
      apiKey: ${MY_API_KEY}
```

For non-standard providers, the SDK exports a base class:

```python
# src/agentroom/agents/base.py
from abc import abstractmethod
from a2a.server.agent_execution import AgentExecutor
from a2a.server.events import EventQueue

class BaseAgentAdapter(AgentAdapter):
    @abstractmethod
    async def execute(self, context, event_queue: EventQueue) -> None: ...
    # connect/disconnect/is_available have sensible defaults
    # context_budget() returns conservative defaults (128K tokens, 50% threshold)
```

Contributors implement `execute()` and register the adapter by provider name.

---

## UI, Installation & Cross-Platform Strategy

### Design Principle

> The same `agentroom` binary should provide a complete experience out of the box on any platform — no separate installs, no Docker required, no "web app" to deploy separately.

### Three Interface Modes

AgentRoom runs as a **Python server** (`agentroom start`) in three modes:

#### 1. Web Console (Primary UI)

A React + TailwindCSS web application served as static files by **FastAPI's StaticFiles middleware**. When you run `agentroom start`, the web console is available at `http://localhost:4000`.

```
┌──────────────────────────────────────────────────────────────┐
│  AgentRoom — Room: "Build a trading signal engine"       │
├──────────┬───────────────────────────────────────────────────┤
│          │  ┌─────────────────────────────────────────────┐  │
│ Agents   │  │ @claude (researching...)                    │  │
│          │  │ Based on my analysis of the Binance API     │  │
│ @claude  │  │ and common TA indicators, I propose we...   │  │
│ @gpt4o   │  ├─────────────────────────────────────────────┤  │
│ @gemini  │  │ @gpt4o (researching...)                     │  │
│ @grok    │  │ I've surveyed 3 approaches to real-time     │  │
│          │  │ signal engines: event-driven, polling...     │  │
│──────────│  ├─────────────────────────────────────────────┤  │
│ Phase    │  │ @gemini (thinking...)                        │  │
│ ████░░░░ │  │ ▌                                           │  │
│RESEARCH  │  └─────────────────────────────────────────────┘  │
│──────────│                                                   │
│ Files    │  ┌─────────────────────────────────────────────┐  │
│ src/     │  │ Director controls: [Pause] [Skip] [End]     │  │
│ docs/    │  │ Cost: $0.42 / $20.00     Tokens: 18,204    │  │
│          │  └─────────────────────────────────────────────┘  │
└──────────┴───────────────────────────────────────────────────┘
```

**UI features:**
- Real-time streaming via WebSocket (server pushes A2A messages to browser)
- Agent panel per participant — color-coded, with streaming indicators
- Phase banner with progress visualization
- Vote tally — live counts during consensus
- File tree panel for the shared workspace (read-only, with diff viewer)
- Cost meter — running total per-agent and per-room
- Thought messages in a collapsible "thinking" drawer
- Director controls: pause, redirect, override, skip, end room
- Timeline scrubber for replay mode
- Responsive — works on tablet/mobile for monitoring

**Tech stack for web UI:**
- **React 19** — component model, hooks, server state
- **TailwindCSS v4** — utility-first styling, zero CSS files to manage
- **Vite** — dev server + production build (outputs static files)
- **Tanstack Query** — server state management (room data, agent status)
- WebSocket client for real-time message streaming
- Static files served by FastAPI's `StaticFiles` middleware — bundled in the Python package

#### 2. CLI Mode (Terminal Interface)

For users who prefer the terminal, or for running rooms in headless environments (CI, servers, SSH sessions).

```bash
$ agentroom room create --goal "Build a trading signal engine"
Room created: ws_abc123

$ agentroom join ws_abc123
Joined room ws_abc123 as @krishna (director)
Phase: RESEARCHING

@claude: Based on my analysis of the Binance API...
@gpt4o: I've surveyed 3 approaches...
@gemini: [thinking...]

> /vote +1 "I agree with @claude's approach"
Vote recorded.

> /phase consensus
Phase transition: RESEARCHING → CONSENSUS
```

**CLI features:**
- Color-coded agent output (each agent gets a consistent color)
- Streaming output — tokens appear as they arrive
- Slash commands: `/vote`, `/phase`, `/compact`, `/replay`, `/cost`
- Pipe-friendly — `agentroom replay ws_abc123 --format json | jq`
- Works over SSH — no browser required

#### 3. Daemon Mode (Background Process)

For long-running rooms or production deployments:

```bash
$ agentroom daemon start
AgentRoom daemon started (PID: 12345)
Web console: http://localhost:4000
API: http://localhost:4000/api

$ agentroom room create --goal "Monitor trading signals" --auto-start
$ agentroom daemon status
Running rooms: 2
Active agents: 8
Uptime: 3h 22m
```

### Installation

Goal: **zero-friction install on any platform.** Multiple distribution channels, all delivering the same Python package.

#### Method 1 — pip / uv (Primary)

```bash
# Using pip (Python already installed)
pip install agentroom

# Using uv (recommended — faster, manages Python itself)
uv tool install agentroom

# One-shot via uvx (no install)
uvx agentroom start
```

#### Method 2 — Package Managers

```bash
# macOS
brew install agentroom

# Linux (Debian/Ubuntu)
sudo apt install agentroom

# Linux (Arch)
yay -S agentroom

# Windows
scoop install agentroom
winget install agentroom
```

#### Method 3 — Direct Download (Script)

```bash
# macOS / Linux
curl -fsSL https://agentroom.dev/install.sh | sh

# Windows (PowerShell)
irm https://agentroom.dev/install.ps1 | iex
```

These scripts install `uv` if needed, then install AgentRoom via `uv tool install`.

#### Method 4 — GitHub Releases

Source distributions and wheels on every GitHub release. Users can install directly:
```bash
pip install https://github.com/agentroom/agentroom/releases/download/v1.0.0/agentroom-1.0.0.tar.gz
```

#### Method 5 — Docker (for server deployments)

```bash
docker run -p 4000:4000 -v ./room:/data agentroom/agentroom
```

Docker is NOT required for normal use — it's for users who prefer containerized deployments.

### Why Not a Desktop App (Tauri/Electron)?

We evaluated **Tauri** (Rust + web frontend) and **Electron** for a native desktop experience. Decision: **not for v1.**

| Factor | Web-in-server (chosen) | Tauri | Electron |
|---|---|---|---|
| Install size | ~10MB (Python package) | ~10-15MB | ~150MB+ |
| Cross-platform | Anywhere Python runs | 5 targets via Rust | 3 targets |
| Native OS integration | None (runs in browser) | Full (menus, tray, file dialogs) | Full |
| Auto-update | `pip install --upgrade` / `uv` | Built-in updater | Built-in updater |
| Build complexity | Simple (`uv build`) | Moderate (Rust + JS toolchain) | Simple (but huge) |
| Contributor barrier | Low (just Python) | High (need Rust knowledge) | Low (Chromium + Node) |
| Server/headless mode | Yes (same package) | No (GUI app) | No (GUI app) |
| Mobile support | N/A (web works in mobile browser) | iOS + Android (Tauri 2) | No |

**Key reasons:**
1. AgentRoom is fundamentally a **server** with a web UI, not a GUI app. The agents, queue, and MCP server all run as a backend process. A desktop wrapper adds complexity without core value.
2. The single binary approach means the **same binary** runs as a CLI, daemon, or web server. Tauri would require a separate desktop app build alongside the CLI/daemon build.
3. **Headless mode is essential.** Many users will run AgentRoom on servers, in CI, or over SSH. A desktop app can't serve this use case.
4. **Future consideration:** If desktop integration (tray icon, notifications, native menus) proves valuable, Tauri v2 can wrap the existing web UI later. The web UI is already React — it's Tauri-ready.

### Cross-Platform Tech Stack Summary

| Component | Technology | Role |
|---|---|---|
| **Runtime** | Python 3.12+ | All business logic |
| **Web framework** | FastAPI + uvicorn | HTTP server, WebSocket, SSE, static files |
| **Agent protocol** | A2A (`a2a-python`) | Inter-agent message format + wire protocol |
| **Tool protocol** | MCP | Agent access to tools (files, search, code exec) |
| **Message broker** | SQLite (WAL mode, `sqlite3` stdlib) | Durable FIFO queue + audit log |
| **Vector memory** | sqlite-vec | Semantic search over room memory |
| **Data validation** | Pydantic | Schema validation, settings, serialization |
| **Web UI** | React 19 + TailwindCSS v4 + Vite | Embedded web console |
| **Real-time** | WebSocket | UI ↔ server push |
| **Streaming** | SSE (`sse-starlette`) | Agent-to-agent streaming (A2A standard) |
| **File versioning** | Git | Workspace change tracking |
| **Linting** | Ruff | Format + lint (replaces flake8 + black + isort) |
| **Type checking** | Pyright | Static type analysis (strict mode) |
| **Testing** | pytest + pytest-asyncio | Unit + integration tests |
| **Package manager** | uv (by Astral) | Dependencies, virtualenvs, Python installation |
| **CI/CD** | GitHub Actions | Build, test, publish to PyPI |
| **Provider SDKs** | anthropic, openai, google-genai | Official AI provider SDKs (Python) |

---

## Language & Runtime

### The Cross-Platform Requirement

Must run natively (not via WSL or a compatibility layer) on:
- **Windows** 10/11 x64 + ARM64
- **macOS** x64 + Apple Silicon (ARM64)
- **Linux** x64 + ARM64 (Debian/Ubuntu/Fedora/Arch)

### Candidates Evaluated

| Language | Distribution | AI SDK Support | Contributor Accessibility | Async/Streaming | Verdict |
|---|---|---|---|---|---|
| **Python** | **pip/uv** — ubiquitous, `uv` can install Python itself | **Best** — all providers, most examples, A2A ecosystem dominant | **Best** — ML/AI community default, largest AI contributor pool | Excellent (asyncio + FastAPI) | **✓ Chosen** |
| **TypeScript (Bun)** | Yes — `bun build --compile` single binary | Best — all providers ship official Node SDKs | Best — largest web/backend pool | Excellent | Strong, but wrong ecosystem for A2A |
| **TypeScript (Node)** | No (needs runtime) | Same as Bun | Same as Bun | Excellent | Needs bundling |
| **Go** | Yes — `GOOS=windows go build` | Community SDKs only, lag behind API changes | Medium | Good (goroutines) | Good for CLI wrapper |
| **Rust** | Yes | Immature AI SDKs | Low — high barrier to contributors | Excellent (tokio) | Too risky for open source |

### Decision: Python + FastAPI

**Python 3.12+** for all business logic. **FastAPI + uvicorn** as the server. **uv** for package management.

**Why Python?**

1. **A2A ecosystem is Python-first.** The `a2a-python` SDK has 1,787 stars (3.5× the JS SDK). Most A2A examples, tutorials, and community contributions are in Python. Upstream spec contributions happen in Python repos.
2. **Every AI provider ships official Python SDKs** — Anthropic, OpenAI, Google, xAI. Updated same-day when APIs change. Python is the primary language for AI development.
3. **Target users already have Python.** Anyone running AI tools — LangChain, CrewAI, AutoGen, LlamaIndex — has Python installed. Zero new runtime to install.
4. **`sqlite3` is in the standard library.** Our message broker has literally zero external dependencies. No install step, no native compilation, no binary compatibility issues.
5. **`uv` solved the distribution story.** `uv tool install agentroom` or `uvx agentroom start` — one command, cross-platform, fast. `uv` can even install Python itself if the user doesn't have it.
6. **FastAPI is the de facto Python web framework** for async APIs — native async/await, WebSocket, SSE via `sse-starlette`, Pydantic validation, OpenAPI docs auto-generated.

**Why not TypeScript + Bun (original choice)?**
Bun's single-binary distribution (`bun build --compile`) was the original reason to choose TypeScript. However: (a) the A2A ecosystem is overwhelmingly Python — swimming against that current hurts contributor accessibility and upstream contributions, (b) `uv` now provides a comparable "zero-friction install" story for Python, and (c) AI provider SDKs are equally well-maintained in Python (often better — some providers ship Python SDKs first).

**Why not Go?**
Go produces excellent cross-platform binaries, but every major AI provider's Go SDK is community-maintained with significant lag. For a project that lives or dies by keeping up with fast-moving AI APIs, using the official SDKs is not optional.

**Why not Rust?**
Immature AI SDKs and a high contributor barrier. Open source projects need contributors — Rust's learning curve is a dealbreaker.

### Distribution

```bash
# Primary — pip / uv (works everywhere Python runs)
pip install agentroom
uv tool install agentroom
uvx agentroom start          # one-shot, no install

# Package managers
brew install agentroom       # macOS
apt install agentroom        # Debian/Ubuntu
scoop install agentroom      # Windows
```

Python runs on every target platform. The same `pyproject.toml` and source code works everywhere — no platform-specific compilation. Platform differences (Named Pipes vs UNIX sockets, path separators) are handled inside narrow adapter modules using Python's cross-platform stdlib (`pathlib`, `asyncio`, `subprocess`).

### Package Manager & Tooling

- **uv** (by Astral) for dependency management — fast, manages virtualenvs and Python versions
- **Ruff** (by Astral) for linting + formatting — single tool replacing flake8, black, isort
- **Pyright** for static type checking — strict mode, VS Code integrated
- **pytest + pytest-asyncio** for testing
- **Pydantic** for data validation and settings management

### Web UI

React 19 + TailwindCSS v4, built with Vite, served as static files by FastAPI's `StaticFiles` middleware. The web console is accessible at `http://localhost:4000` when the server starts — no separate web server or CDN needed. The built web assets are bundled into the Python package (`agentroom/static/`). See the "UI, Installation & Cross-Platform Strategy" section above for full details.

### Platform-Specific Notes

- **Windows STDIO:** Python's `asyncio.create_subprocess_exec()` handles Windows correctly. Child processes (CLI adapters) use UTF-8 explicitly.
- **Windows IPC:** Named Pipes instead of UNIX sockets (abstracted behind `LocalTransport`). Python's `asyncio` supports both.
- **File paths:** `pathlib.Path` handles cross-platform paths natively.
- **Code execution sandbox:** On Windows, Docker Desktop is the recommended sandbox. Deno subprocess sandbox is cross-platform fallback.

---

## Project Structure (Proposed)

```
AgentRoom/
├── src/
│   └── agentroom/
│       ├── __init__.py
│       ├── __main__.py        # CLI entry point (agentroom start, room create, etc.)
│       ├── protocol/          # A2A types, AgentRoom extensions, Pydantic models
│       ├── broker/            # SQLite message queue + A2A message serialization
│       ├── agents/            # Provider adapters (Anthropic, OpenAI, Google, xAI, local)
│       ├── coordinator/       # Room lifecycle, consensus, role management, prompt builder
│       ├── mcp_server/        # Shared workspace MCP server (tools for agents)
│       ├── context/           # Context manager, compaction, cost tracking
│       ├── server/            # FastAPI app, WebSocket, SSE, static file serving
│       └── static/            # Built React web console (output of Vite build)
├── web/                       # React web console source (Vite + TailwindCSS)
├── tests/
│   ├── unit/
│   └── integration/
├── examples/
│   ├── sdlc-room/             # Example: build a feature end-to-end
│   ├── research-room/         # Example: synthesize a research topic
│   └── trading-room/          # Example: analyze a trade setup
├── docs/
│   ├── protocol.md            # A2A integration + AgentRoom extensions spec
│   ├── architecture.md        # System architecture and data flow
│   └── adapters.md            # How to build a custom agent adapter
├── pyproject.toml             # Project config, dependencies, build settings
├── BRAINSTORM.md              # This file
└── README.md
```

---

## A2A Ecosystem & Language Landscape

The A2A protocol was donated to the Linux Foundation by Google. Understanding where the community lives helps us make informed decisions about contributor accessibility.

### Official SDKs (by community adoption)

| SDK | Language | Stars | Notes |
|---|---|---|---|
| **a2a-python** | Python | 1,787 | Most popular by 3.5x. Default for AI/ML community — **what we use** |
| **a2a-samples** | Jupyter/Python | 1,458 | Tutorials and example agents |
| **a2a-js** | TypeScript | 506 | Official JS SDK |
| **a2a-inspector** | TypeScript | 383 | Validation tools for A2A agents |
| **a2a-java** | Java | 376 | Enterprise adoption |
| **a2a-go** | Go | 316 | Infrastructure/DevOps |
| **a2a-dotnet** | C# | 215 | Enterprise/.NET |
| **a2a-tck** | Python | 32 | Technology Compatibility Kit |

**Python dominates the A2A ecosystem** — most contributors, most examples, most community activity. TypeScript is a solid second with a well-maintained official SDK.

### What This Means for AgentRoom

Our choice of **Python + FastAPI** aligns with where the A2A ecosystem lives. This gives us:
- Direct use of `a2a-python` — the most actively maintained and documented A2A SDK
- Ability to contribute upstream to A2A spec extensions and SDK patches in the same language
- Maximum contributor accessibility — the AI/ML community defaults to Python
- TypeScript developers who want to build A2A agents that talk to AgentRoom rooms can use A2A's standard HTTP protocol — they don't need our Python SDK
- The A2A wire protocol is language-agnostic (Protocol Buffers, JSON-RPC, HTTP) — interop works regardless of implementation language

---

## Design Decisions & Q&A Log

Key design discussions and their outcomes, documented for future reference. Each entry captures the question, the reasoning, and the decision.

---

### DD-1: ESB vs A2A — Why a Hybrid Architecture?

**Question:** A2A is a peer-to-peer protocol where agents talk directly via HTTP. ESB (Enterprise Service Bus) is a hub-and-spoke model with a central broker. Why did we pick one over the other?

**Answer:** We didn't — we use both, at different zoom levels.

**Inside a room:** Our SQLite queue acts as a lightweight ESB. Every agent publishes to the queue and subscribes from it. Agents don't call each other's HTTP endpoints directly. This is deliberate — an ordered conversation (turns, votes, consensus) requires:
- Strict FIFO ordering (`seq` in SQLite)
- Central audit log (every message in one place)
- Crash recovery (agents resume from their cursor)
- Voting tallies (coordinator reads the queue)

Pure peer-to-peer A2A can't provide any of those without building a central broker anyway.

**Between rooms:** Pure A2A peer-to-peer. Rooms are independent agents that communicate via standard A2A HTTP endpoints. No central bus, no single point of failure, no coupling.

```
Inside a room:                      Between rooms:

  @claude ──┐                       Room A ←── A2A HTTP ──→ Room B
  @gpt4o  ──┤── SQLite Queue            │                      │
  @gemini ──┤   (hub-and-spoke)     Room C ←── A2A HTTP ──→ Room D
  @grok   ──┘                       (peer-to-peer, no central broker)
```

**What we took from A2A:** The message format (Message, Part, Artifact, AgentCard, Extensions, task lifecycle). This gives us a battle-tested schema and interoperability with the broader A2A ecosystem.

**What we kept from ESB:** The delivery model (central broker, FIFO, cursors, audit log). This gives us ordering, crash recovery, and a single source of truth.

**Decision:** A2A's vocabulary + ESB's delivery model. Best of both.

---

### DD-2: Inter-Room Communication (Swarm Model)

**Question:** What if multiple rooms need to communicate? Does the ESB model break down?

**Answer:** No — this is where pure A2A peer-to-peer shines. Each room IS an A2A agent from the outside:

- It has an **AgentCard** describing what it can do
- It has an **HTTP endpoint** accepting A2A messages
- It supports **streaming** (SSE)
- It can be **discovered** at `/.well-known/agent-card.json`

A swarm of rooms is just a network of A2A agents talking to each other. No new protocol needed.

**Use cases for inter-room communication:**

| Pattern | Example |
|---|---|
| **Delegation** | A room researching "build a trading engine" spawns a child room for "research TA indicators" |
| **Pipeline** | Research room → Implementation room → Review room (output feeds input) |
| **Parallel exploration** | 3 rooms explore different approaches, coordinator room collects and compares |
| **Knowledge base** | A long-running "library" room that other rooms query like a senior colleague |

**Who handles incoming messages?** The lead agent. External A2A messages enter the SQLite queue like any internal message. The lead agent triages: answer solo, broadcast to room, or route to a specific participant. The server is a dumb broker — the lead has context to make judgment calls.

**Single-agent rooms work identically.** A room with one agent still has the queue (for audit), still has an AgentCard, still accepts A2A messages. Just simpler.

**Decision:** ESB inside the room (conversations need order), A2A between rooms (swarms need independence).

---

### DD-3: Naming Decision — "Room"

**Question:** What do we call the core collaborative session? Candidates: Workshop, Room, Deck, Lab, Table, Pod.

**Evaluation:**

| Term | Strengths | Weaknesses |
|---|---|---|
| Workshop | Implies structured work, clear phases | 8 chars, "workshopping" is awkward, slightly formal |
| **Room** | Simple, universal, short. Immediate metaphor | Could feel "just a chat" without context |
| Deck | Unique, punchy, memorable | Ambiguous (cards? slides? ship?), requires explanation |
| Lab | Implies experimentation, discovery | Too research-focused, odd for "build me a CRUD app" |
| Table | "Round table" — peers debating as equals | Less common in tech, could confuse with DB tables |
| Pod | Modern, short, Kubernetes precedent | Overloaded with K8s meaning |

**Decision: Room.**

Reasons:
1. **It's what it actually is** — agents are in a room, talking. Zero explanation needed.
2. **Shortest CLI** — `agentroom room create`, `agentroom room join`
3. **Natural language** — "I have 3 rooms running" / "The room reached consensus" / "Join my room"
4. **Scales to swarm** — "Rooms can talk to other rooms" is immediately understood
5. **Pairs with roles** — "The room's coordinator" / "Everyone in the room voted"
6. **Precedent** — Matrix protocol uses "rooms" for structured collaboration spaces

The structured phases, voting, and lifecycle make it clear this isn't a casual chatroom.

---

### DD-4: Lead Agent Failure & Heartbeat Design

**Question:** What happens when the lead agent crashes, lags, or makes bad decisions? How do we detect it without wasting tokens on constant pinging?

**Key insight:** Pinging the lead via an LLM API call every 30 seconds burns money for zero value. Most of the time, normal message activity already proves the lead is alive.

**Decision: Passive-first, 4-tier escalation.**

| Tier | What | Cost | When |
|---|---|---|---|
| 0 | Observe normal message activity | $0 | Always (covers 90% of time) |
| 1 | IPC ping to adapter process | $0 | Lead silent > 5 min |
| 2 | HTTP GET to provider's `/v1/models` endpoint | $0 | Process alive but last API call failed |
| 3 | Minimal LLM probe ("respond with ACK") | $0.0001 | Everything else inconclusive (very rare) |

**Effective cost of the entire health-check system: essentially zero.**

On confirmed failure: server initiates succession — pre-configured fallback list, handover packet with current state (phase, pinned decisions, vote tallies, pending actions), new lead acknowledges and resumes. Old lead rejoins as a regular participant if it recovers.

See **Issue 11 — Lead Agent Failure Protocol** above for the full specification.

---

### DD-5: A2A Ecosystem Language Choice (Superseded by DD-6)

**Question:** A2A was originally written by Google. The ecosystem is heavily Python (1,787 stars) vs TypeScript (506 stars). Should we follow what A2A contributors are familiar with?

**Original Answer:** No — we chose TypeScript + Bun for distribution reasons.

**Update:** This decision was revisited and reversed. See DD-6 below.

---

### DD-6: Language Switch — TypeScript + Bun → Python + FastAPI

**Question:** After evaluating the A2A ecosystem, MCP ecosystem, and target user base more carefully, should we switch from TypeScript + Bun to Python?

**Answer:** Yes.

| Factor | TypeScript + Bun (original) | Python + FastAPI (new) |
|---|---|---|
| A2A SDK | `a2a-js` (506 stars) | `a2a-python` (1,787 stars, 3.5×) |
| A2A community | Second largest | **Dominant** — most contributions, examples, tutorials |
| AI provider SDKs | Official (all providers) | Official (all providers) — often shipped first |
| Distribution | Single binary (`bun build --compile`) | `pip install` / `uv tool install` / `uvx` |
| Target users | Need Bun installed (new runtime) | **Already have Python** (AI tools require it) |
| SQLite | Embedded in Bun | **stdlib** (`sqlite3`) — zero dependency |
| MCP ecosystem | MCP servers exist in both | Many more Python MCP servers and examples |
| Async/streaming | Excellent | Excellent (asyncio + FastAPI + SSE) |

**Key insight that changed the decision:** The original argument for TypeScript was "distribution via single binary." But our target users — people who run AI agents — already have Python installed. `uv` (by Astral) now provides a comparable zero-friction install story: `uvx agentroom start` is one command, cross-platform, and fast. The distribution advantage of Bun evaporated when we identified our actual user base.

**Decision:** Python + FastAPI. Same architecture, better ecosystem alignment.

---

## Immediate Next Steps

- [ ] Set up project (`pyproject.toml`, uv, Ruff, Pyright strict)
- [ ] Integrate `a2a-python` — define AgentRoom extensions as Pydantic models
- [ ] Build minimal SQLite broker (two agents sending A2A messages)
- [ ] Build first two provider adapters (Claude + GPT-4o) implementing `AgentExecutor`
- [ ] Build RoomPromptBuilder (system prompt assembly)
- [ ] Build coordinator prototype (phase management, turn order, voting)
- [ ] Wire up basic web UI (React + Vite + WebSocket) to watch agents talk
- [ ] Add cost tracking to context manager
- [ ] Add rate limit handling to adapters
- [ ] Package and publish to PyPI + test `uvx agentroom start` on macOS/Linux/Windows
- [ ] Write contributor guide and open source the repo

---

*Last updated: March 2026*
