# Security

## Current Status (v0.1)

AgentRoom v0.1 is a **development prototype**. It includes baseline security hardening but is **not yet production-ready** for untrusted networks.

## Implemented Protections

### Input Validation
- All Pydantic models enforce `max_length` on string fields and `max_length` on list fields
- `AgentCard.name` (100), `AgentCard.provider` (50), `AgentCard.model` (100)
- `Message.content` capped at 100KB, `RoomConfig.goal` at 5KB
- `CreateRoomRequest.agents` limited to 10 agents per room
- API `limit` query parameter capped at 1,000 (via `Query(ge=1, le=1000)`)

### SQL Injection Prevention
- All SQLite queries use parameterized statements (`?` placeholders) — verified clean by Bandit

### WebSocket Hardening
- Payload size limit: 32KB per message
- JSON parsing with error handling (malformed JSON returns error, no crash)
- Schema validation: requires dict with `type` field
- Content validation: `message` type requires string content ≤ 10KB
- Unknown message types return error instead of being silently ignored

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Error Sanitization
- HTTP error messages do not expose internal state (e.g., "Room not found" not "Room abc123 not found")
- Provider validation errors return generic "Invalid agent configuration"

### Operation Timeouts
- Single agent turn: 120s timeout
- Full round (all agents): 600s timeout
- Timeout returns HTTP 504

### Room ID Security
- Room IDs use `secrets.token_urlsafe(16)` — 128 bits of cryptographic randomness

## Known Limitations (To Address Before Production)

### No Authentication
- All API endpoints and WebSocket connections are unauthenticated
- Any client with network access can create rooms, read messages, and trigger agent turns
- **Mitigation**: Run only on trusted networks or behind an authenticating reverse proxy

### No Rate Limiting
- API endpoints have no request throttling
- An attacker could spam `/api/rooms/{id}/turn` to exhaust LLM API quotas
- **Planned**: Add rate limiting middleware (e.g., `slowapi`)

### No CORS Configuration
- Default FastAPI CORS policy (same-origin only) is in effect
- Explicit CORS middleware should be added when the React UI is deployed separately

### No Message Retention Policy
- Messages accumulate indefinitely in SQLite
- No TTL, max count, or cleanup mechanism
- **Planned**: Add message eviction and room lifecycle management

### API Key Handling
- API keys are read from environment variables or passed in code
- Provider SDKs may include keys in exception tracebacks if logged at DEBUG level
- **Mitigation**: Never run with DEBUG logging in production

## Reporting Vulnerabilities

Please report security issues privately via GitHub Security Advisories or email the maintainers directly. Do not open public issues for security vulnerabilities.
