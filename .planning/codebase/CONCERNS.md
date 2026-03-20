# Codebase Concerns

**Analysis Date:** 2025-03-20

## Tech Debt

**WebSocket State Management Fragility:**
- Files: `src/python/api_main.py`, `src/frontend-react/src/hooks/useWebSocket.ts`
- Issue: Global `clients` dict in `api_main.py` (line 523) is mutated directly without transaction semantics. Race conditions possible during simultaneous disconnect/broadcast cycles (lines 552-557).
- Impact: Memory leaks from failed clients not properly cleaned up; silent drops of critical state updates during high load.
- Fix approach: Replace with asyncio-safe queue or use a lock-protected dict with transaction rollback on broadcast failure. Implement client lifecycle hooks.

**Simulation Engine Size & Complexity:**
- Files: `src/python/sim_engine.py` (1553 lines)
- Issue: Single 1553-line file violates 800-line file size guideline. Mixed concerns: physics simulation, state machine logic, UAV/target behavior, zone management, autonomy transitions all in one module.
- Impact: Difficult to test individual systems; coupling increases risk of cascading failures when physics changes.
- Fix approach: Split into: `sim_core.py` (physics/update loop), `uav_behaviors.py`, `target_behaviors.py`, `autonomy_state_machine.py`. Establish clear boundaries.

**API Main Complexity:**
- Files: `src/python/api_main.py` (1113 lines)
- Issue: Large monolithic file mixing WebSocket handlers, simulation loop, demo autopilot, broadcast logic, HITL processing, and HTTP endpoints. Multiple global variables (`sim`, `hitl`, `assistant`, `clients`) with circular dependencies.
- Impact: Difficult to extend; testing requires full system spin-up; changes to one endpoint risk destabilizing all others.
- Fix approach: Extract: `websocket_handlers.py`, `demo_autopilot.py`, `simulation_loop.py`, `http_endpoints.py`. Use dependency injection instead of globals.

**Broad Exception Catching:**
- Files: `src/python/api_main.py` (lines 207-209, 647-648), `src/python/llm_adapter.py` (lines 107, 336, 392, 432)
- Issue: Bare `except Exception as exc` or silent `pass` statements swallow errors without re-raising or logging actionable context. Line 647: `except Exception: logger.exception("battlespace_assessment_error")` has no recovery path.
- Impact: Hard to debug failures; silent graceful degradation masks bugs; assessment errors silently drop data.
- Fix approach: Catch specific exceptions, preserve traceback context, implement retry logic for transient failures, log error boundaries clearly.

**LLM Adapter Fallback Chain Risk:**
- Files: `src/python/llm_adapter.py`
- Issue: Provider detection runs once at init; Gemini/Anthropic/Ollama failures are cached permanently. No runtime re-probing if network recovers.
- Impact: If LLM provider becomes available mid-run (docker restart, network recovery), system never detects it.
- Fix approach: Implement per-call provider health checks with exponential backoff; cache results with TTL (5min).

**Hard-Coded Port & Hostname in Frontend:**
- Files: `src/frontend-react/src/hooks/useWebSocket.ts` (line 21)
- Issue: WebSocket URL hardcoded to `ws://${window.location.hostname}:8000/ws`. Works locally but breaks in containerized/prod environments where backend port may differ.
- Impact: Multi-node deployments, reverse proxies, Docker swarms will fail silently on connection refused.
- Fix approach: Read from environment variable `VITE_BACKEND_WS_URL` or discover via service discovery.

## Known Bugs

**Demo Autopilot Race Condition:**
- Files: `src/python/api_main.py` (lines 335-346)
- Symptoms: Strike board entry approval succeeds in demo mode but COA proposal silently fails due to entry status change between approval and COA proposal.
- Trigger: Entry status transitions between `PENDING → APPROVED` while COA proposal is in-flight; another task changes status to `REJECTED` before line 403 executes.
- Workaround: Restart demo mode; currently race window is small (APPROVAL_DELAY=5s) so rare in practice.
- Root cause: Entry fetch at line 337 is non-atomic; entry_id lookup at line 403 doesn't re-verify status.

**Target State Regression Threshold Mismatch:**
- Files: `src/python/sim_engine.py` (line 170), `src/python/verification_engine.py` (lines 83-90)
- Symptoms: Targets in CLASSIFIED state regress to DETECTED even with continuous sensor contact if `regression_timeout_sec` expires before promotion to VERIFIED.
- Trigger: Target needs 2 sensor types but only has 1; `regression_timeout_sec=8-15s` < `verify_sustained_sec=10-15s`. Timing race causes regression before promotion.
- Workaround: Fusion must reach verify_confidence threshold simultaneously with sustained time.
- Fix approach: Change regression logic to reset timer on any sensor update (not just regress); separate "loss timeout" from "promotion minimum".

**WebSocket JSON Parse Failure Cascade:**
- Files: `src/python/api_main.py` (lines 791-798)
- Symptoms: Malformed JSON from one client causes WebSocket to hang silently; no recovery logged.
- Trigger: Send invalid JSON from browser console: `ws.send("{invalid json}")`.
- Workaround: Client reconnection resets handler; server remains unaffected.
- Root cause: JSONDecodeError caught at line 793, error sent at line 795, but malformed JSON may leave parser in bad state.

## Security Considerations

**No Rate Limiting on WebSocket Bulk Actions:**
- Files: `src/python/api_main.py` (lines 86-96, 784-789)
- Risk: Rate limit is per-message count (30/sec), not per-action. Attacker can flood `approve_nomination` actions within rate limit.
- Files: `src/python/api_main.py` (lines 811-891 websocket action dispatch)
- Current mitigation: None explicit; HITL manager re-validates on each action but doesn't throttle repeated actions on same target.
- Recommendations: Add action-specific rate limits (e.g., 1 approval per target per 5s); implement circuit breaker if same user approves 10+ nominations in 1 minute.

**Unsafe Deserialization in Broadcast:**
- Files: `src/python/api_main.py` (lines 525-557)
- Risk: Broadcast assumes all `websocket` keys in `clients` dict are still valid WebSocket instances. If a concurrent task closes a socket, the dict entry may point to a closed handle, causing broadcast to emit to dead connections.
- Impact: Broadcast failures not retried; some clients miss state updates.
- Recommendations: Use `asyncio.Lock` on clients dict mutations; implement connection validity check in `_send()`.

**No Input Validation on REST Endpoints:**
- Files: `src/python/api_main.py` (lines 687-750)
- Risk: `/api/sitrep`, `/api/environment`, `/api/theater` accept arbitrary JSON without schema validation. Example: `time_of_day` accepts any float, no bounds check (line 729).
- Impact: Out-of-range values could cause sensor model failures or visualization crashes.
- Recommendations: Use Pydantic models for all REST request bodies; validate bounds in schema.

**LLM Injection Risk in Agent Prompts:**
- Files: `src/python/agents/isr_observer.py` (lines 99-100)
- Risk: User-provided detection data (if ever enabled) serialized directly into LLM prompt without escaping. Example: detection type could be `"); // DROP TABLE;` if malicious.
- Impact: Prompt injection could jailbreak agent to perform unintended reasoning.
- Recommendations: Validate detection types against whitelist; use structured prompts with templating engine (Jinja2), not string format.

**CORS Origins Hardcoded:**
- Files: `src/python/api_main.py` (lines 512-518)
- Risk: CORS `allow_origins=["http://localhost:3000"]` only allows local development. Zero CORS protection in prod.
- Impact: Frontend deployments to different hostname will fail with CORS error.
- Recommendations: Load allowed origins from env var; use `allow_origin_regex` for dynamic validation.

## Performance Bottlenecks

**O(n²) State Broadcast at Every Tick:**
- Files: `src/python/api_main.py` (lines 668-678)
- Problem: Full simulation state serialized to JSON + broadcast to all clients every tick (10Hz). State object includes all targets, UAVs, zones, assessment, ISR queue.
- Measured impact: At 20 UAVs + 50 targets = ~80KB per state JSON * 10 ticks/sec = 800KB/sec baseline.
- Scaling risk: 100 clients = 80MB/sec egress; 1000 clients = 800MB/sec.
- Improvement path:
  1. Delta encoding: only send changed fields
  2. Selective broadcast: send full state only to newly connected clients, deltas to others
  3. Compression: use msgpack or protobuf instead of JSON
  4. Sampling: broadcast at 2Hz instead of 10Hz; clients interpolate between frames

**Assessment Serialization Blocks Simulation:**
- Files: `src/python/api_main.py` (lines 606-646)
- Problem: `assessor.assess()` runs on main event loop with 5-second recalc interval. If assessment takes >100ms, simulation tick stalls.
- Current: Uses `asyncio.to_thread()` to avoid blocking (line 623), but assessment result is not cached across ticks; every consumer fetches fresh.
- Scaling risk: As target count grows, assessment complexity increases; cached result could be stale by 5s.
- Improvement path: Pre-compute and cache assessment result; publish via event rather than poll.

**UAV Target Search O(n²):**
- Files: `src/python/sim_engine.py` (line 278: `_find_nearest_available_uav`)
- Problem: Demo autopilot finds nearest UAV by iterating all UAVs, computing distance to each. Per-entry operation in loop.
- Impact: With 20 UAVs and 50 concurrent PENDING entries, = 1000 distance calculations per demo cycle.
- Improvement path: Index UAVs by zone; search only nearby zones; use KD-tree for spatial queries.

**Sensor Model Re-evaluation Per Target Per Tick:**
- Files: `src/python/sensor_model.py` (called from `sim_engine.py` tick loop)
- Problem: `evaluate_detection()` runs for every UAV-target pair every tick. With 20 UAVs × 50 targets = 1000 evaluations per tick @ 10Hz.
- Impact: CPU-bound operation with exponential sensor contributions list growth.
- Improvement path: Cache detection results with 1-tick TTL; invalidate only on UAV mode/position change >0.001deg.

## Fragile Areas

**Autonomy State Machine Transitions:**
- Files: `src/python/sim_engine.py` (lines 545-548, 546-548 autonomy_level and pending_transitions)
- Why fragile: Autonomous mode transitions span multiple ticks (FOLLOW → PAINT → BDA). If a transition is rejected or timeout expires, there's no fallback path. UAV stuck in PENDING state until manually released.
- Safe modification: Always exit pending transitions with explicit timeout; log all rejections; test all rejection paths before deploying autonomy changes.
- Test coverage: Minimal — no test for transition rejection + timeout scenario.

**Target State Transitions via Verification Engine:**
- Files: `src/python/verification_engine.py` (lines 50-105), consumed by `src/python/sim_engine.py` (tick loop)
- Why fragile: Pure function returns new state but caller (sim_engine) must update target.state. If caller crashes between evaluation and update, state is lost. No idempotency.
- Safe modification: Wrap state update in transaction; log state change reason; test with state machine fuzzing.
- Test coverage: Good — `test_verification.py` covers promotion and regression paths.

**Demo Autopilot Entry Locking Logic:**
- Files: `src/python/api_main.py` (lines 298-442)
- Why fragile: `in_flight` set tracks entries being processed, but if demo_autopilot task crashes mid-process, entry stays in `in_flight` forever → never gets re-attempted. No external watchdog.
- Safe modification: Add entry expiry in demo loop; implement external circuit breaker that clears stale `in_flight` entries.
- Test coverage: No test for demo autopilot failure recovery.

**WebSocket Client Cleanup on Network Jitter:**
- Files: `src/python/api_main.py` (lines 753-809)
- Why fragile: Client cleanup happens in broadcast error handler (lines 556-557). If broadcast succeeds but later task sends to same client, race condition. Multiple paths to cleanup = multiple mutation points.
- Safe modification: Use single cleanup function; centralize all client removal; implement client lifecycle hooks (onConnect, onDisconnect).
- Test coverage: No test for concurrent connect/disconnect scenarios.

**Theater Configuration Loading with Missing Units:**
- Files: `src/python/theater_loader.py`, `src/python/sim_engine.py` (lines 517-522, 557-565)
- Why fragile: If theater YAML missing `red_force.units` section, fallback uses hardcoded list. Map lookups at lines 557-565 won't find unit types → targets spawn without type-specific attributes (speed, range). Manifests as silent attribute mismatches.
- Safe modification: Validate theater schema early in `load_theater()`; raise with clear error if required sections missing.
- Test coverage: `test_theater_loader.py` doesn't test partial/malformed configs.

## Scaling Limits

**In-Memory Target/UAV State Without Persistence:**
- Files: `src/python/sim_engine.py` (lines 573-574)
- Current capacity: Stores full history for 50-100 targets + 20 UAVs in memory. Position history (line 173) limited to 60 entries per target = ~30KB per target = 1.5MB total.
- Limit: Beyond 500 targets, memory grows linearly; no cleanup. Process restarts lose all state.
- Scaling path: Implement target lifecycle with archival (old targets → SQLite after ESCAPED/DESTROYED); stream new targets from file/API instead of spawning at init.

**WebSocket Connection Limit Hard Cap:**
- Files: `src/python/api_main.py` (lines 48, 756-760)
- Current capacity: MAX_WS_CONNECTIONS = 20 hardcoded.
- Limit: Exactly 20 simultaneous clients. Connection 21 rejected with 1013 (service unavailable).
- Scaling path: Use connection pooling with load balancing; implement WebSocket gateway upstream; increase MAX_WS_CONNECTIONS if memory permits (each connection ≈ 100KB state cache).

**Battlespace Assessment Recalculation Interval:**
- Files: `src/python/api_main.py` (line 606: 5-second interval)
- Current capacity: Assessment runs every 5s. At high target count (100+), assessment becomes I/O bound.
- Limit: If assessment takes >1s to complete, next assessment queued while previous still running → assessment lag.
- Scaling path: Implement incremental assessment; cache clustered results; process assessment in separate thread pool.

**Strike Board Entry Duplication Without Dedup:**
- Files: `src/python/api_main.py` (lines 180-192, 223-235)
- Current capacity: No deduplication of nominations. Same target re-nominated multiple times adds duplicate entries.
- Limit: Strike board could grow to 100+ entries all pointing to same 20 targets → UI rendering becomes O(n) slow.
- Scaling path: Add nominated tracking by (target_id, target_type) tuple; prevent duplicate nominations within 10s window.

## Dependencies at Risk

**LangChain/LangGraph Version Drift:**
- Risk: Agents import `langgraph` but pinned versions may have CVEs or API changes. Migration to new major version requires updating all 9 agents simultaneously.
- Impact: Security patches blocked if version incompatible.
- Migration plan: Decouple agents from LangGraph; use adapter pattern to wrap agent calls. Allows gradual migration.

**Cesium GL Version Lock:**
- Files: `src/frontend-react/package.json`
- Risk: Cesium GL major version changes (e.g., 1.x → 2.x) break entity hooks and shader APIs. No minor version flexibility (pinned to exact version).
- Impact: Security updates blocked; new features gated.
- Migration plan: Update package-lock.json to allow patch versions; test Cesium updates in isolated branch before merging.

**numpy/scipy Transitive Dependency Conflicts:**
- Files: `requirements.txt`
- Risk: FastAPI → starlette → potentially incompatible numpy versions if multiple packages specify ranges.
- Impact: Venv creation fails mysteriously; can't install on new systems.
- Migration plan: Use `pip-tools` to generate exact pinned versions; test install on clean venv monthly.

## Missing Critical Features

**No Deployment Rollback Strategy:**
- Problem: No versioning of simulation state. If new code breaks sim_engine.tick(), old state can't be reloaded.
- Blocks: Production hardening; multi-region failover.
- Implementation: Add state snapshots to `.planning/state_backups/`; implement state restore endpoint.

**No Audit Trail for HITL Decisions:**
- Problem: Strike board approvals/rejections logged to structlog but no queryable database of decisions.
- Blocks: After-action review; compliance reporting; learning from operator behavior.
- Implementation: Add SQLite table `hitl_decisions(entry_id, operator_id, action, timestamp, rationale)`; expose query endpoint.

**No Multi-User Session Management:**
- Problem: Single shared sim_engine instance. All operators see same state; no role-based access control.
- Blocks: Multi-operator scenarios; secret/restricted theater configs.
- Implementation: Add user sessions with role-based visibility filters; multi-instance sim backends with operator-specific views.

## Test Coverage Gaps

**Demo Autopilot Failure Paths:**
- What's not tested: Demo autopilot recovery when target disappears, UAV shot down, or HITL manager full.
- Files: `src/python/api_main.py` (lines 282-442)
- Risk: Silent failures leave entries stuck in `in_flight` set; no recovery.
- Priority: **High** — demo mode is primary user-facing path; failures degrade demo experience.

**WebSocket Concurrent Operations:**
- What's not tested: Simultaneous connect + broadcast + disconnect from different tasks.
- Files: `src/python/api_main.py` (lines 523-557)
- Risk: Race conditions on `clients` dict; potential double-close or use-after-free.
- Priority: **High** — concurrent operations at scale will trigger races.

**Verification Engine Terminal State Lock-In:**
- What's not tested: Transitions TO terminal states (NOMINATED, LOCKED, ENGAGED) and staying locked when regression would regress.
- Files: `src/python/verification_engine.py` (lines 47, 72-73)
- Risk: Logic assumes terminal states never regress, but if manual state change occurs, verification engine could corrupt state.
- Priority: **Medium** — edge case but silent corruption is dangerous.

**Theater Config Partial Load Failures:**
- What's not tested: Theater YAML with missing sections, wrong types, or empty unit lists.
- Files: `src/python/theater_loader.py`, `src/python/sim_engine.py` (initialization)
- Risk: Silent fallback to defaults; operator thinks custom config loaded but actually using hardcoded values.
- Priority: **Medium** — affects custom theater deployments; errors caught at runtime.

**Sensor Fusion Edge Cases:**
- What's not tested: Fusion with 0 contributions, NaN confidence values, duplicate sensor types, time-skew.
- Files: `src/python/sensor_fusion.py` (lines 35-64)
- Risk: Edge cases produce NaN/Inf fused_confidence that propagate to verification engine.
- Priority: **Low** — fusion is pure function, but edge cases could corrupt state downstream.

---

*Concerns audit: 2025-03-20*
