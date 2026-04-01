# Leader-Driven Coordinator Design

**Status:** IN PROGRESS — design decisions captured, detail sections pending
**Date:** 2026-03-31
**Replaces:** Free-for-all coordination (previously described as next priority)

## Overview

AgentRoom's coordinator is being redesigned around a **leader-driven hub-and-spoke** model. A user selects a leader agent and one or more advisor agents. The leader orchestrates research, consolidates feedback, and is the sole implementer. Advisors provide analysis and review only.

## Core Workflow

```
User sends prompt
  → Leader receives prompt, reframes per advisor with focus directives
  → All agents (leader + advisors) research in parallel
  → Leader reads responses, optionally asks clarification questions (up to N rounds)
  → Leader consolidates into a single merged answer
  → User reviews: new prompt (loop) | "implement it" | "done"
```

## Design Decisions

### DD-7: Leader reframes with hybrid approach
The leader forwards the user's original prompt to all advisors AND adds a brief per-advisor directive based on their strengths/role (e.g., "Focus your analysis on security aspects"). Advisors see the raw request plus leader guidance.

### DD-8: Bounded clarification rounds (default 3)
The leader can go back and forth with advisors up to N rounds (configurable, default 3). The leader signals completion with a `[SATISFIED]` sentinel in its response. If max rounds reached, the system forces consolidation.

### DD-9: Hybrid filesystem context
At room start, a file tree + key file summaries (README, entry points) are generated and injected into all agent prompts. Full file contents are injected on-demand when agents reference specific files. CLI agents (claude, gemini) also have native filesystem access via subprocess.

### DD-10: Leader-only implementation
When the user says "implement it," the leader acts alone. Advisors are idle. No automatic review cycle (future enhancement).

### DD-11: Leader-first rewrite (drop round-robin)
The Room class is rewritten to only support the leader-driven workflow. Round-robin is removed entirely. YAGNI — the leader model is the product.

## Room Phases (Simplified)

```
IDLE → RESEARCHING → CLARIFYING → CONSOLIDATING → USER_REVIEW → IMPLEMENTING → DONE
       └──────────────────────────────────────────┘
                    (loops on new user prompt)
```

- **IDLE**: Room created, agents connected, waiting for user prompt
- **RESEARCHING**: Leader + all advisors working in parallel (`asyncio.gather`)
- **CLARIFYING**: Leader asks follow-up questions to advisors (up to N rounds)
- **CONSOLIDATING**: Leader merges all inputs into a single answer
- **USER_REVIEW**: User reads consolidated answer, decides next step
- **IMPLEMENTING**: Leader executes approved plan (advisors idle)
- **DONE**: Room complete

## Room Class Shape

```python
class Room:
    leader: AgentAdapter
    advisors: dict[str, AgentAdapter]
    broker: MessageBroker
    context: FolderContext          # NEW — filesystem access
    phase: RoomPhase
    max_clarify_rounds: int        # Default 3

    async def run_cycle(prompt: str) -> None
    async def implement(instruction: str) -> None
    async def user_message(content: str) -> None
```

**Removed:** `run_turn()`, `run_round()`, `_next_agent()`, turn counter, round-robin logic.
**Kept:** broker, on_message() callbacks, _notify(), start()/stop() lifecycle.

## Prompt Builder

Leader and advisors get different system prompts:

**Leader prompt:**
- Role as leader and consolidator
- Room goal + all advisor names/descriptions
- Filesystem context (folder tree + summaries)
- Phase-specific instructions (research, clarify with `[SATISFIED]` signal, consolidate, implement)

**Advisor prompt:**
- Role as advisor (read-only, no actions)
- Room goal + leader's focus directive for this advisor
- Filesystem context (same tree + summaries)
- Simple instruction: provide analysis, leader will consolidate

## Filesystem Context (FolderContext)

New component that provides agents with codebase awareness:

- **Upfront**: File tree + summaries of key files (README, entry points, config)
- **On-demand**: Full file contents when referenced
- **CLI agents**: Get native access via subprocess (FolderContext is supplementary)
- **API agents**: Depend entirely on FolderContext for file access

## Open Questions (To Resolve Next Session)

### Privacy-Aware Mode
A key concern was raised: commercial models (Claude, GPT-4, Gemini) have no privacy guarantees. Can a team of local LLMs match a commercial model?

**Current thinking:**
- Fully local teams are weaker today for complex reasoning
- **Hybrid model is the sweet spot**: local LLMs as advisors (code never leaves machine), commercial model as leader (sees only advisor summaries, not raw source code)
- The system should support a **privacy mode** where the leader only receives advisor summaries, never raw file contents
- This maps naturally to the leader-advisor architecture

**To decide:**
- Should privacy-mode be part of the initial design or a future layer?
- How to handle the trust boundary (what the leader sees vs. what advisors see)
- UI for selecting privacy level per room

### Remaining Design Sections (Not Yet Discussed)
- Server/API changes (endpoints for the new cycle)
- WebSocket protocol changes (streaming parallel research, clarification rounds)
- Web UI redesign (room creation with leader selection, cycle visualization)
- Message broker changes (if any — likely minimal)
- Testing strategy
- Migration path from current codebase

## Infrastructure Reuse Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| SQLite broker | ✅ Keep as-is | Message history, audit trail |
| Agent adapters (all 4) | ✅ Keep as-is | Core abstraction unchanged |
| FastAPI + WebSocket | ✅ Keep, update endpoints | New cycle-based API |
| Web UI (Alpine.js) | ✅ Keep stack, redesign views | Leader selection, cycle viz |
| Agent config persistence | ✅ Keep as-is | User still picks from library |
| Room coordinator | 🔄 Rewrite | Leader-driven cycle replaces round-robin |
| Prompt builder | 🔄 Rewrite | Leader vs advisor prompts |
| Phase state machine | 🔄 Simplify | New phase set |
| Vote/Review extensions | ❌ Remove for now | Not needed in leader model |
| Round-robin logic | ❌ Remove | Replaced by fan-out/fan-in |
