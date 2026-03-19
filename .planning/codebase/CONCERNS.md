# Codebase Concerns

**Analysis Date:** 2025-03-19

## Tech Debt

**Global state mutation in API server:**
- Issue: `sim` and `hitl` are module-level globals in `src/python/api_main.py` (lines 433-434). Theater switching (line 545) reassigns global `sim` directly, creating hidden state dependencies and potential race conditions in concurrent WebSocket handlers.
- Files: `src/python/api_main.py`
- Impact: Theater switches can affect all connected clients unexpectedly; WebSocket handlers may operate on stale simulation state if not carefully synchronized.
- Fix approach: Refactor to use dependency injection — create a `SimulationContext` class per request/session and inject into handlers. Store per-client state in `clients` dict metadata.

**Bare exception catch with silent pass:**
- Issue: Multiple locations catch broad exceptions and pass silently without logging:
  - `src/python/api_main.py:78` — catches WebSocketDisconnect/ConnectionError/OSError and passes
  - `src/python/api_main.py:151` — catches asyncio task cancellation and passes
  - `src/python/vision/video_simulator.py:122, 151` — bare passes in exception handlers
- Files: `src/python/api_main.py`, `src/python/vision/video_simulator.py`
- Impact: Silent failures hide bugs; critical errors go unnoticed, making production debugging impossible.
- Fix approach: Replace all `except X: pass` with proper logging at WARN or ERROR level with context. Use `logger.warning()` before passing or only pass when exception is truly expected and benign.

**Event logger global queue not validated at import:**
- Issue: `src/python/event_logger.py:22` asserts `_queue is not None`, but this happens only when `start_logger()` is called. Code importing the module before startup will fail with a cryptic assertion error.
- Files: `src/python/event_logger.py`
- Impact: Initialization order bugs are hard to debug; unclear which code requires `start_logger()` to have been called first.
- Fix approach: Make `log_event()` check if queue is initialized and return early with warning, or raise a clear `RuntimeError` stating "Event logger not started — call start_logger() first".

## Known Bugs

**Demo autopilot hardcoded delays may not align with actual tick rate:**
- Symptoms: Demo mode has fixed delays (APPROVAL_DELAY=5.0, FOLLOW_DELAY=4.0) while simulation runs at `settings.simulation_hz` (default 10 Hz = 0.1s per tick). Timing drifts from user expectations.
- Files: `src/python/api_main.py:259-273`
- Trigger: Run demo mode with non-default `simulation_hz` value.
- Workaround: Keep simulation_hz at 10 Hz; adjust demo delays proportionally if changing Hz.

**Strike board entry field access without validation:**
- Symptoms: `api_main.py:347` accesses `entry.get("target_location", [0.0, 0.0])` and then indexing `target_loc[0]` and `target_loc[1]` without bounds checking. Empty lists will cause IndexError.
- Files: `src/python/api_main.py:347-351`
- Trigger: Malformed HITL entry with empty `target_location` tuple.
- Workaround: Validate entry structure before demo autopilot attempts to use it.

**Sensor contribution filtering by confidence cutoff is hardcoded:**
- Symptoms: `sim_engine.py:837` filters contributions with `if c.confidence > 0.05` hardcoded. Changes to sensor model confidence scale are not reflected in UI output.
- Files: `src/python/sim_engine.py:837`
- Trigger: Tune sensor model confidence outputs outside [0.05, 1.0] range.
- Workaround: This is primarily a display filter; underlying state includes all contributions.

## Security Considerations

**WebSocket input validation is incomplete:**
- Risk: `_validate_payload()` checks field types but not ranges or semantic validity. COA ID validation (`api_main.py:132`) relies on list search without permission checks; any client can forge a COA ID string.
- Files: `src/python/api_main.py:55-67, 124-134`
- Current mitigation: CORS limits to `localhost:3000` only (line 427).
- Recommendations:
  - Add range validation for numeric fields (e.g., drone IDs, lat/lon within bounds)
  - Validate COA IDs are actually from the strike board entry client requested
  - Add optional authentication layer (JWT or session tokens) if deploying to multi-user environment
  - Rate limit per-client payload size to prevent large payload attacks

**LLM API keys stored in environment variables without validation:**
- Risk: Config loads OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY from environment without checking if they're actually valid. Invalid keys are silently passed to LLM providers, causing runtime failures.
- Files: `src/python/config.py:16-30`, `src/python/llm_adapter.py:72-95`
- Current mitigation: None — keys are used as-is; providers return errors.
- Recommendations:
  - On startup, validate at least one LLM provider key actually works with a lightweight probe call (e.g., token count API)
  - Log clearly which providers are available/unavailable at startup
  - Never log actual API key values; only log provider availability status

**Vision simulator stores drone video as base64 in WebSocket frames without size limit:**
- Risk: `video_simulator.py:630` sends MJPEG frames as base64 JSON without checking payload size. Large frames can exceed WebSocket buffer limits or create memory bloat.
- Files: `src/python/vision/video_simulator.py:630`
- Current mitigation: Timeout on send (0.1s), but no size enforcement.
- Recommendations:
  - Add max_frame_size config; reject frames exceeding limit
  - Compress video frames (JPEG quality reduction) if size grows too large
  - Consider alternative transport (separate TCP stream, HTTP chunked) for video

## Performance Bottlenecks

**Sensor fusion loops all-against-all for every target every tick:**
- Problem: `sim_engine.py:594-633` iterates over all UAVs for every target every tick to compute contributions. With 20 UAVs and 17 targets, this is 340 distance/aspect calculations per tick, 3400 per second at 10 Hz.
- Files: `src/python/sim_engine.py:594-633`
- Cause: No spatial partitioning; O(n_uav * n_target) naive approach.
- Improvement path:
  - Implement grid-based spatial partitioning (quadtree or simple lat/lon buckets)
  - Only compute contributions for UAVs within detection range; skip others
  - Cache UAV positions at tick start to avoid repeated `hypot()` calls

**WebSocket broadcast to all clients runs serially despite claim of "parallel":**
- Problem: `api_main.py:461` claims `asyncio.gather(*[_send(t) for t in targets])` runs in parallel, but if one client has high latency, all others wait for the timeout (0.1s per client). With 20 clients, this becomes 2 seconds of blocking.
- Files: `src/python/api_main.py:453-466`
- Cause: Timeouts are sequential, not truly parallel.
- Improvement path:
  - Keep timeout-per-client but increase to 0.5s to accommodate slower networks
  - Implement an async queue for slow clients so broadcasts don't block the main loop
  - Log slow-client warnings to identify network bottlenecks

**Theater configuration loads entire file into memory without streaming:**
- Problem: `theater_loader.py:243` loads and parses YAML theater files entirely into memory. Large theater configs (e.g., 1000+ unit definitions) create spike in GC pressure during theater switch.
- Files: `src/python/theater_loader.py`
- Cause: No lazy loading; all units hydrated at once.
- Improvement path:
  - For now, acceptable (theaters are small); if units scale to 1000+, implement lazy unit loading
  - Cache parsed theater objects in memory after first load

## Fragile Areas

**Aspect angle calculation assumes WGS-84 flat-earth approximation:**
- Files: `src/python/sim_engine.py:605-610`
- Why fragile: Code applies flat-earth projection only in one place (line 607), but similar calculations appear elsewhere. If projection constants change, inconsistency creeps in.
- Safe modification: Extract aspect-angle calculation to a utility function in `src/python/utils/geo_utils.py` and call it everywhere. This centralizes the approximation.
- Test coverage: `test_sim_integration.py` covers basic simulation but not aspect-angle edge cases (near poles, across date line).

**Target velocity randomization at init has no bounds:**
- Files: `src/python/sim_engine.py:100-103`
- Why fragile: `speed = random.uniform(0.0005, 0.0015)` is a magic constant. No comment explains why these bounds; if sensor detection ranges change, this may need adjustment too.
- Safe modification: Move bounds to module-level constants at top (like `FOLLOW_ORBIT_RADIUS_DEG`). Document rationale in a comment (e.g., "~2-5 km/hr in sim units").
- Test coverage: `test_sensor_spawn.py` verifies speeds post-theater-load but not initial randomization bounds.

**Demand spike trigger increases queue by fixed 120 units regardless of size:**
- Files: `src/python/sim_engine.py:754-757`
- Why fragile: Magic number 120 is unexplained. If zone queue capacity or demand rate change, 120 may become inappropriate.
- Safe modification: Make this configurable; add `demand_spike_increment: int = 120` to theater config or as method parameter.
- Test coverage: No test for `trigger_demand_spike()`; manual testing only.

**HITL strike board status transitions are not validated:**
- Files: `src/python/hitl_manager.py:192-215`
- Why fragile: `_transition_entry()` accepts any `new_status` string without validating it's a legal transition. Invalid states can be set.
- Safe modification: Add an Enum for valid statuses and check transitions against a state machine (e.g., PENDING → {APPROVED, REJECTED, RETASKED}, APPROVED → {REJECTED, AUTHORIZED}, etc.).
- Test coverage: `test_hitl_manager.py` covers happy path but not invalid state transitions.

**CesiumContainer unmounts and remounts on every theme change (potential memory leak):**
- Files: `src/frontend-react/src/cesium/CesiumContainer.tsx`
- Why fragile: Cesium viewer instance is created/destroyed on mount/unmount. If cleanup (disposing of entities, removing listeners) isn't perfect, detached DOM nodes or WebGL contexts leak memory.
- Safe modification: Preserve viewer instance across theme changes; only update renderer properties.
- Test coverage: No test for memory leaks; manual E2E testing only.

## Scaling Limits

**HITL strike board stores all historical entries in memory:**
- Current capacity: 1000s of entries (limited by available RAM)
- Limit: Unbounded list growth; no pruning or archival.
- Scaling path:
  - Implement a max-size rolling buffer (e.g., keep last 10k entries, discard oldest)
  - Add persistence layer (SQLite or PostgreSQL) for audit trail
  - Add pagination API so frontend doesn't load all entries at once

**Simulation physics tick becomes O(n_uav * n_target) for detection:**
- Current capacity: ~20 UAVs × ~17 targets = manageable at 10 Hz
- Limit: Scales poorly beyond 50 UAVs or 100 targets; physics loop becomes bottleneck
- Scaling path:
  - Spatial partitioning (see Performance Bottlenecks above)
  - Reduce detection update frequency (e.g., update every 2 ticks, cache results)
  - Move detection to separate async worker thread/process

**WebSocket connection limit is hard-coded to 20:**
- Current capacity: 20 clients (line 43 of api_main.py)
- Limit: No justification for 20; bottleneck unknown
- Scaling path:
  - Remove artificial limit or make it configurable
  - Monitor memory per client; implement adaptive limits based on available RAM
  - Consider message queue (e.g., Redis pub/sub) for true multi-server deployment

## Dependencies at Risk

**Cesium JS library is large (unminified overhead):**
- Risk: Bundle size for 3D visualization; slow initial load on poor networks
- Impact: Blocks user interaction until viewer is ready
- Migration plan:
  - Use code-splitting to lazy-load Cesium after app boots
  - Consider lightweight 2D alternative (Leaflet) as fallback for slow clients

**FastAPI/uvicorn may bottleneck under sustained load:**
- Risk: Single-threaded async event loop; CPU-intensive operations (sensor fusion) block WebSocket writes
- Impact: Slow broadcast, delayed client updates under load
- Migration plan:
  - Profile hotspots; move heavy computation (sensor fusion) to thread pool
  - Consider Gunicorn + multiple uvicorn workers for multi-core usage
  - Monitor event loop lag with `asyncio.get_running_loop()` instrumentation

**OpenAI/Anthropic/Google LLM provider APIs are external dependencies:**
- Risk: Rate limits, API changes, service outages, cost escalation
- Impact: Agent pipeline fails if LLM unreachable; heuristic fallback keeps system running but degrades to rule-based logic
- Migration plan:
  - Current fallback to heuristic mode is good; keep it
  - Add circuit breaker to disable LLM calls after N consecutive timeouts
  - Cache LLM responses where deterministic (e.g., COA generation for same target type)

## Missing Critical Features

**No audit trail for strike board decisions:**
- Problem: Decision rationale is logged but not indexed; no way to query "who approved what and when" without parsing logs
- Blocks: Compliance/accountability for firing decisions; incident investigation
- Solution: Add audit table with (entry_id, user_id, decision, timestamp, rationale) and expose via API endpoint

**No persistence across server restarts:**
- Problem: Strike board, simulation state, and event log all disappear on crash
- Blocks: Multi-day operations; incident reconstruction
- Solution: Implement PostgreSQL backend for strike board; add checkpoint snapshots for sim state

**No simulation state export/replay:**
- Problem: Can't save a scenario to rerun later or share with analysts
- Blocks: Testing, scenario analysis, training reproducibility
- Solution: Add export endpoint to dump full sim state as JSON; add replay mode to load and step through scenarios

**No role-based access control (RBAC):**
- Problem: All WebSocket clients have equal permissions; any client can approve strikes
- Blocks: Multi-operator teams, delegation of responsibilities
- Solution: Add JWT tokens with role claims; check authorization in strike board handlers

## Test Coverage Gaps

**Untested: Theater configuration loading edge cases:**
- What's not tested: Malformed YAML, missing required fields, invalid unit types, out-of-bounds coordinates
- Files: `src/python/theater_loader.py`, test file `test_theater_loader.py`
- Risk: Theater switch crashes silently or loads garbage data; users don't know theater is broken
- Priority: High — theater switch is critical path

**Untested: WebSocket payload validation boundaries:**
- What's not tested: Extremely large coordinates, negative drone IDs, empty strings in action fields, duplicate field names
- Files: `src/python/api_main.py:55-107`
- Risk: Malformed payloads bypass validation and cause crashes downstream
- Priority: High — API is attack surface

**Untested: Sensor fusion under zero/saturation conditions:**
- What's not tested: All sensors lost simultaneously, detection confidence = 1.0 (saturation), single-sensor contributions
- Files: `src/python/sensor_fusion.py`, `test_sensor_fusion.py`
- Risk: Edge case logic bugs in fused_confidence calculation
- Priority: Medium — rare but critical when it happens

**Untested: Demo autopilot timing under load:**
- What's not tested: Demo mode with 50+ WebSocket clients connected, high-latency broadcast, Cesium viewer lag
- Files: `src/python/api_main.py:259-397`, e2e tests
- Risk: Demo autopilot hangs if broadcast times out; UX appears frozen
- Priority: Medium — demo is marketing/testing tool; visible failures hurt confidence

**Untested: HITL state machine invalid transitions:**
- What's not tested: Attempting to transition from REJECTED back to PENDING, APPROVED back to PENDING, etc.
- Files: `src/python/hitl_manager.py`, test file `test_hitl_manager.py`
- Risk: Invalid state machine transitions corrupt strike board state
- Priority: Medium — rare in practice due to UI constraints but possible via direct API calls

**Untested: React component memory leaks on unmount:**
- What's not tested: Cesium viewer cleanup, WebSocket message handler cleanup, DOM listeners on component destroy
- Files: `src/frontend-react/src/cesium/CesiumContainer.tsx`, `src/frontend-react/src/hooks/useWebSocket.ts`
- Risk: Long-running sessions accumulate detached DOM nodes, unresolved promises, listener functions
- Priority: High — production deployments may run 24/7; memory leaks are critical

---

*Concerns audit: 2025-03-19*
