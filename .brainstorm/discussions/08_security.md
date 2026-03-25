# 08 — Security Audit

## Risk Matrix

| # | Finding | Severity | Vector |
|---|---------|----------|--------|
| 2 | No authentication on any endpoint | CRITICAL | Network |
| 14a | HITL approval requires no auth — any client can approve | CRITICAL | WebSocket |
| 14c | HITL replay: status not checked before transition | HIGH | WebSocket |
| 3a | No WebSocket message size limit — memory bomb | HIGH | WebSocket |
| 13 | demo_autopilot auto-approves indefinitely, no dead-man switch | HIGH | Config |
| 1a | `set_coverage_mode` passes raw string to sim | MEDIUM | WebSocket |
| 1b | `lat/lon/confidence` accept NaN/Inf — propagates to physics | MEDIUM | WebSocket |
| 1c | Theater name not allowlisted before path construction | MEDIUM | REST |
| 4 | LLM prompts contain raw user-data — prompt injection | MEDIUM | WebSocket/LLM |
| 9 | NaN/Inf leaks internal error text to client | MEDIUM | WebSocket |
| 10 | SITREP query_text unconstrained length | MEDIUM | WebSocket |
| 11 | LangChain minimum versions dangerously low | MEDIUM | Supply chain |
| 3b | Rate limit per-connection not per-IP | LOW | WebSocket |
| 5 | Theater path traversal leaks attempted path in error | LOW | REST |
| 15 | Internal error text exposed to clients | LOW | WebSocket |

## Detailed Findings

### Authentication (CRITICAL — none exists)
- Zero auth on any endpoint
- Any host reaching port 8000 can connect
- Client self-declares as SIMULATOR — can inject false intelligence
- Server binds 0.0.0.0 by default

### HITL Bypass Vectors (CRITICAL)
1. **Self-declared client type** — any WebSocket client can approve nominations
2. **Demo mode enablement** — `DEMO_MODE=true` env var bypasses all HITL
3. **Replay attack** — `_transition_entry` doesn't check current status before transitioning; can go REJECTED to APPROVED

### WebSocket Security
**Hardened:** Connection limit (20), rate limiting (30/s), identification timeout (2s), broadcast timeout (0.1s)
**Gaps:** No message size limit, no origin checking, rate limit per-connection not per-IP

### Input Validation Gaps
- `set_coverage_mode` — raw string to sim, no allowlist
- `retask_sensors` — `float()` accepts NaN/Inf, no range validation on lat/lon/confidence
- `subscribe` — arbitrary feed names into subscription state
- `subscribe_sensor_feed` — no validation elements are integers
- `SITREP_QUERY` — no query length limit
- `POST /api/environment` — no range checks on time_of_day, cloud_cover, precipitation
- `POST /api/theater` — raw string, no allowlist check

### Autonomous Mode Safety (HIGH)
- Auto-approves ALL PENDING nominations after 5s delay
- No maximum strike count or rate limit
- No dead-man switch — continues if all DASHBOARD clients disconnect
- Nomination flood from malicious SIMULATOR would be auto-approved

### LLM Security (MEDIUM)
- Target data flows into LLM prompts without sanitization
- Prompt injection possible via target type or id fields
- SITREP query reflected back to client (XSS vector if rendered as HTML)
- API key handling is correct (env vars, not hardcoded)

### Clean Areas
- No hardcoded secrets found
- .env in .gitignore, .env.example has only placeholders
- No command injection (no shell exec, subprocess, eval, exec calls found)
- YAML uses safe_load
- JSON parsing is safe

## Top Recommendations

1. Token-based WebSocket auth (Bearer token in IDENTIFY message)
2. Message size guard before `json.loads()`
3. Fix HITL replay: check `old.status == "PENDING"` before transition
4. Separate SIMULATOR auth token from DASHBOARD
5. Validate theater_name against `list_theaters()` allowlist
6. Range validation: lat (-90,90), lon (-180,180), confidence (0,1)
7. Demo autopilot circuit breaker: max N auto-approvals, halt if no DASHBOARD connected
8. Pin all dependencies, add `pip-audit` to CI
