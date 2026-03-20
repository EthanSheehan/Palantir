# Architecture

**Analysis Date:** 2025-03-20

## Pattern Overview

**Overall:** Multi-layer event-driven C2 system with three primary subsystems:

1. **FastAPI WebSocket backend** running a 10Hz simulation loop
2. **Physics simulation engine** managing UAV dynamics, target movement, zone imbalance
3. **React/Cesium geospatial frontend** with real-time map visualization and tactical controls

The system implements an asynchronous F2T2EA kill chain (Find-Fix-Track-Target-Engage-Assess) with LangGraph-based multi-agent orchestration, human-in-the-loop approval gates, and complementary multi-sensor fusion.

**Key Characteristics:**
- **Event-driven**: WebSocket broadcasts full state each tick (10Hz)
- **Immutable data models**: Frozen dataclasses and Pydantic models prevent mutation
- **Pure functions**: Verification engine, sensor fusion, and state transitions are deterministic (no side effects)
- **Dual-client model**: Dashboard clients (frontend) and Simulator clients (drone video feed) share one WebSocket namespace
- **LangGraph orchestration**: Nine agents communicate through a shared Pydantic ontology

## Layers

**WebSocket & Network Layer:**
- Purpose: Real-time bidirectional communication between backend and frontend
- Location: `src/python/websocket_manager.py`, `src/python/api_main.py` (endpoint `/ws`)
- Contains: `ConnectionManager` (connection state), message routing (state broadcasts, video frames, COAs)
- Depends on: FastAPI, asyncio
- Used by: Frontend hooks (`useWebSocket`), simulator clients, dashboard clients
- Frame-dropping safety: Tracks busy connections to prevent message accumulation; non-blocking with timeouts

**Simulation Engine Layer:**
- Purpose: Physics-based tactical simulation managing UAV modes, target movement, sensor emissions
- Location: `src/python/sim_engine.py`
- Contains: `SimulationModel` class managing UAV positions, modes (IDLE/SEARCH/FOLLOW/PAINT/INTERCEPT/REPOSITIONING/RTB), target movement per unit type, zone-based imbalance tracking
- Depends on: `theater_loader.py` (loads theater configs), `sensor_model.py` (evaluates detections), `swarm_coordinator.py` (autonomous transitions)
- Used by: Main simulation loop in `api_main.py`, autonomous drone dispatching

**Verification & Fusion Layer:**
- Purpose: Advance targets through kill-chain states (DETECTED→CLASSIFIED→VERIFIED→NOMINATED) using multi-sensor fusion
- Location: `src/python/verification_engine.py`, `src/python/sensor_fusion.py`
- Contains:
  - `VerificationThreshold` frozen dataclass with per-target-type confidence/time/sensor requirements
  - `evaluate_target_state()` pure function (no state mutation) advancing target states based on evidence
  - `fuse_detections()` complementary fusion using 1 - ∏(1-ci) formula with max-within-type deduplication
  - `SensorContribution` and `FusedDetection` frozen dataclasses
- Depends on: Target classification data, sensor confidence scores
- Used by: ISR pipeline, tactical assistant, UI target cards

**Multi-Agent Orchestration Layer (LangGraph):**
- Purpose: AI-driven recommendation generation across the F2T2EA chain
- Location: `src/python/agents/` (9 agents total)
- Contains:
  - **ISR Pipeline (4 core agents):**
    - `isr_observer.py` — Sensor fusion, track correlation
    - `strategy_analyst.py` — ROE evaluation, priority scoring, nomination decision
    - `tactical_planner.py` — Course of Action (COA) generation
    - `effectors_agent.py` — Engagement execution and battle damage assessment
  - **Support Agents (5):**
    - `pattern_analyzer.py` — Activity pattern analysis across targets
    - `ai_tasking_manager.py` — Sensor retasking optimization
    - `battlespace_manager.py` — Map layer management, threat ring visualization
    - `synthesis_query_agent.py` — SITREP generation, natural language queries
    - `performance_auditor.py` — System performance monitoring
- Depends on: `llm_adapter.py` (LLM calls), `core/ontology.py` (shared data contract)
- Used by: Pipeline orchestrator, tactical assistant widget, autonomous decision-making

**Strike Board & HITL Layer:**
- Purpose: Target nomination and COA approval with immutable status tracking
- Location: `src/python/hitl_manager.py`
- Contains: `StrikeBoardEntry` (immutable target nomination), `CourseOfAction` (immutable COA option)
- Depends on: Strategy analyst outputs, tactical planner outputs
- Used by: Frontend strike board UI, demo autopilot mode, engagement authorization

**Core Data Contract:**
- Location: `src/python/core/ontology.py`, `src/python/schemas/ontology.json`
- Contains: Pydantic models for `Detection`, `Location`, `IdentityClassification`, `SensorType`, `ROEAction`, `TargetClassification`, `Track`, `ActionableTarget`, etc.
- Ensures: All agents communicate with consistent field names, types, confidence ranges

**State Management (LangGraph):**
- Location: `src/python/core/state.py`
- Contains: `AnalystState` TypedDict with annotated reducers (`Annotated[list[T], add]`)
- Pattern: List fields use `add` reducer to accumulate (strike board, tasking requests, rejections)

**Frontend State Management:**
- Location: `src/frontend-react/src/store/SimulationStore.ts`
- Contains: Zustand store with full simulation state (UAVs, targets, zones, flows, strike board, assistant messages, intel/command feeds, assessment data, ISR queue, map modes)
- Depends on: WebSocket messages from backend
- Used by: React components throughout the app

## Data Flow

**Simulation Tick (10Hz main loop):**

1. **Backend tick** (`api_main.py` async loop):
   - Advance simulation 100ms: call `sim.step(0.1)` updating UAV positions, target movements, emissions
   - Fuse new sensor detections across all UAVs via `sensor_fusion.fuse_detections()`
   - Advance target states via `verify_engine.evaluate_target_state()` (pure function, no mutation)
   - Evaluate autonomy transitions via `swarm_coordinator` (autonomous mode only)
   - Broadcast full state JSON to all DASHBOARD clients: `broadcast({"type": "state", "data": {...}})`

2. **WebSocket reception** (frontend `useWebSocket` hook):
   - Parse JSON payload
   - Call `store.setSimData(payload.data)` updating Zustand store atomically

3. **React render** (components subscribe to store):
   - `CesiumContainer` reads store state, updates Cesium entities (drone markers, target labels, zones, flow lines)
   - `Sidebar` tabs (MISSION, ASSETS, ENEMIES, ASSESSMENT) read store and re-render on state changes
   - `DroneCamPIP` displays video feed from selected drone's camera

**Kill-Chain Pipeline (user-initiated or autonomous):**

1. **Nomination** (human or `TacticalAssistant`):
   - ISR-fused target reaches VERIFIED state
   - Strategy analyst evaluates against ROE
   - Creates `StrikeBoardEntry` with priority score, reasoning trace
   - Frontend displays in MISSION tab strike board

2. **HITL Gate 1** (target approval/rejection/retasking):
   - User clicks APPROVE/REJECT/RETASK button
   - `hitl_manager.approve_target()` returns new `StrikeBoardEntry` with status APPROVED/REJECTED/RETASKED
   - In demo mode: auto-approves all nominations

3. **COA Generation** (tactical planner agent):
   - Backend receives APPROVE action from frontend
   - `TacticalPlannerAgent.generate_coas()` produces 3 options (conservative, balanced, aggressive)
   - Calculates time-to-effect, PK estimate, risk score
   - Sends HITL_UPDATE with COA list to frontend

4. **HITL Gate 2** (COA selection):
   - User selects one COA from dropdown
   - `hitl_manager.authorize_coa()` creates new `CourseOfAction` with status AUTHORIZED
   - Broadcasts COA to backend

5. **Engagement** (effectors agent):
   - Backend calls `effectors_agent.execute_engagement(approved_coa, target_data)`
   - Simulates strike with probabilistic outcome
   - Records engagement result: target status → ENGAGED/DESTROYED/ESCAPED
   - Sends BDA assessment to frontend

**State Accumulation Pattern (LangGraph):**

- `strike_board: Annotated[list[ActionableTarget], add]` — each node appends targets, never overwrites
- `tasking_requests: Annotated[list[TaskingRequest], add]` — accumulates sensor retasking orders
- `rejected: Annotated[list[dict], add]` — tracks denied detections with reasons

## Key Abstractions

**Target State Machine:**
- States: UNDETECTED → DETECTED → CLASSIFIED → VERIFIED → NOMINATED → LOCKED → ENGAGED → DESTROYED
- Transitions: Driven by fused confidence, sensor count, time-in-state, regression timeouts
- Implementation: Pure function `evaluate_target_state()` in `verification_engine.py`
- Per-target-type thresholds stored in frozen `VerificationThreshold` dataclass

**Sensor Fusion:**
- Algorithm: Complementary fusion — 1 - ∏(1-c_i) per sensor type
- Deduplication: Max confidence within each sensor type before fusion
- Examples:
  - EO/IR confidence 0.8 + GMTI confidence 0.7 → fused ≈ 0.94
  - SAR confidence 0.6 + SAR confidence 0.65 → max 0.65 (deduplicated)
- Immutable: `SensorContribution` and `FusedDetection` frozen dataclasses prevent accidental modification

**UAV Mode Transitions:**
- Modes: IDLE, SEARCH (circular loiter), FOLLOW (loose 2km orbit), PAINT (tight 1km laser lock), INTERCEPT (direct approach), REPOSITIONING, RTB, SUPPORT, VERIFY, OVERWATCH, BDA
- User-commanded: SEARCH/FOLLOW/PAINT/INTERCEPT triggered by frontend buttons
- Autonomous (DEMO_MODE): Governed by `AUTONOMOUS_TRANSITIONS` table + zone imbalance detection
- Physics: Fixed-wing loiter via `_turn_toward()` function, MAX_TURN_RATE = 3°/sec

**Immutability Pattern (CRITICAL):**
- Strike board entries: `StrikeBoardEntry` frozen dataclass, status changes create new instance via `dataclasses.replace()`
- COA options: `CourseOfAction` frozen dataclass, never modified in-place
- Sensor fusion results: `FusedDetection` frozen dataclass prevents downstream mutation
- Verification results: `evaluate_target_state()` returns new state string, never mutates target object

**Multi-Sensor Confidence Accumulation:**
- Initial detection: Single sensor contributes confidence (e.g., EO/IR 0.6)
- Additional sensors confirm: GMTI adds 0.7 → fused jumps to ~0.88
- Sustained detection: Time-in-state threshold (10-15s depending on unit type)
- Regression: If no sensors report for 8-15s, target regresses one state (VERIFIED → CLASSIFIED)

## Entry Points

**WebSocket Endpoint:**
- Location: `src/python/api_main.py` — `@app.websocket("/ws")`
- Triggers: Client connection (DASHBOARD or SIMULATOR client_type)
- Responsibilities:
  - Accept/parse actions (scan_area, follow_target, paint_target, intercept_target, approve_nomination, authorize_coa, etc.)
  - Validate payloads via `_validate_payload()` with type schema
  - Rate-limit clients (30 msgs/sec per client)
  - Route to appropriate handler function
  - Broadcast state after each tick
  - Stream video frames for drone camera PIP

**FastAPI Server:**
- Location: `src/python/api_main.py` — `uvicorn.run()`
- Runs on: `:8000` (default)
- Launches: 10Hz simulation loop via `asyncio` background task
- Broadcasts: Full state JSON each tick to all connected clients

**React Frontend:**
- Location: `src/frontend-react/src/App.tsx`
- Renders: Sidebar (MISSION/ASSETS/ENEMIES/ASSESSMENT tabs), CesiumContainer, DemoBanner, DroneCamPIP overlay
- Initiates: WebSocket connection in `useWebSocket` hook, subscribes to INTEL_FEED and COMMAND_FEED

**Cesium Globe:**
- Location: `src/frontend-react/src/cesium/CesiumContainer.tsx`
- Renders: 3D globe with drone markers (color-coded by mode), target labels, zones, threat rings, flow lines
- Listens: Custom events from Cesium (waypoint placement, detail map zoom)
- Sends: User actions back to backend via custom events (`palantir:send`, `palantir:placeWaypoint`, `palantir:openDetailMap`)

**Demo Autopilot Mode:**
- Location: `src/python/api_main.py` — `demo_autopilot()` async function (when `DEMO_MODE=true`)
- Runs: Parallel to main simulation loop
- Executes: Full F2T2EA chain autonomously (auto-nominates targets, auto-generates COAs, auto-authorizes, simulates engagement)
- Interval: Driven by target verification timing (every 15-30s a target reaches NOMINATED state)

## Error Handling

**Strategy:** Explicit error handling at all system boundaries with client-safe messages

**Patterns:**

**WebSocket:**
- Invalid JSON → `ERROR` response: `{"type": "ERROR", "message": "...", "action": "..."}`
- Missing required field → `ERROR` with field name
- Type mismatch (e.g., string instead of float) → `ERROR` with type hint
- Rate limit exceeded → `ERROR` "Rate limit exceeded"
- Connection errors caught in `send_error()` helper, no bubbling to client

**Simulation:**
- Theater config missing → fallback to default (Romania grid)
- Target movement invalid → clamp to theater bounds
- Sensor detection failure → skip detection, log, continue

**LLM Calls:**
- Timeout → retry with exponential backoff
- JSON parse error → log full response, use fallback recommendation
- Token limit exceeded → truncate input gracefully

**Frontend:**
- WebSocket disconnect → show "Disconnected" status, auto-reconnect after 1s
- Cesium rendering error → silent fallback to map view
- Missing store data → default empty arrays

## Cross-Cutting Concerns

**Logging:**
- Tool: `structlog` (structured logging)
- Config: `logging_config.py` (JSON format, level defaults to INFO)
- Where to log:
  - Simulation ticks: once per 10 ticks to avoid noise
  - Target state transitions: always (DETECTED→CLASSIFIED, etc.)
  - Agent decisions: when high-confidence (>0.8) or anomalous
  - WebSocket actions: before and after HITL gates
  - Errors: always with full context

**Validation:**
- WebSocket payloads: `_validate_payload()` with field-level type checking
- Pydantic models: Built-in validation via `Field(..., ge=0.0, le=1.0)` constraints
- Agent outputs: JSON schema validation against `schemas/ontology.json`
- Spatial data: Lat/lon clamped to ±180/±90, altitude >= 0

**Authentication:**
- Not yet implemented (assumes trusted internal network)
- Client type distinction (DASHBOARD vs SIMULATOR) via `client_type` field at connection

**Authorization:**
- HITL gates enforce ROE (Rules of Engagement) in `StrategyAnalystAgent`
- Demo mode: Disables HITL, auto-approves all gates
- Supervisor override: Frontend can REJECT any nomination/COA

---

*Architecture analysis: 2025-03-20*
