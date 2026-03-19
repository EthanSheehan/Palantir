# Architecture

**Analysis Date:** 2026-03-19

## Pattern Overview

**Overall:** Layered F2T2EA Kill-Chain Orchestrator with WebSocket-driven simulation loop

**Key Characteristics:**
- Three-tier architecture: WebSocket server (FastAPI) running 10Hz simulation loop, Python AI agents (LangGraph-based), and React/Cesium 3D frontend
- Event-driven kill-chain pipeline: ISR Observer → Strategy Analyst → Tactical Planner → HITL gate → Effectors Agent
- Dual-client model: `DASHBOARD` clients (frontend UI) and `SIMULATOR` clients (drone video feeds) on same WebSocket
- Immutable strike board entries and COA state (dataclass frozen objects)
- Heuristic-first with LLM fallback capability via `LLMAdapter` abstraction

## Layers

**WebSocket Server (FastAPI):**
- Purpose: Real-time broadcast of simulation state, command ingestion, user actions, and HITL approval gates
- Location: `src/python/api_main.py`
- Contains: WebSocket handler (`/ws` endpoint), action validation, rate limiting (30 msg/sec), connection manager
- Depends on: `SimulationModel`, `TacticalAssistant`, `HITLManager`, agent pipeline
- Used by: React frontend, drone simulator

**Simulation Engine:**
- Purpose: Physics-based UAV positioning, target movement behaviors, sensor detection calculations
- Location: `src/python/sim_engine.py`
- Contains: `SimulationModel` class managing UAVs (with 7 modes: IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, REPOSITIONING, RTB), Target objects with behavior trees (SAM, TEL, TRUCK, CP, MANPADS, RADAR, C2_NODE, LOGISTICS, ARTILLERY, APC)
- Depends on: `SensorModel`, `SensorFusion`, `TheaterLoader`, `RomaniaMacroGrid`
- Used by: WebSocket server for tick updates, Demo mode

**AI Agent Layer (LangGraph + LangChain):**
- Purpose: Multi-agent reasoning pipeline for Find-Fix-Track-Target-Engage-Assess (F2T2EA)
- Location: `src/python/agents/` and `src/python/pipeline.py`
- Contains:
  - `ISRObserverAgent`: Sensor fusion, track correlation, classification (uses `SensorFusion`, heuristic or LLM path)
  - `StrategyAnalystAgent`: ROE evaluation, priority scoring, nomination → strike board (heuristic or LLM)
  - `TacticalPlannerAgent`: COA generation (3 per nominated target), effect prediction
  - `EffectorsAgent`: Strike execution and Battle Damage Assessment (BDA)
  - `AITaskingManagerAgent`: Secondary sensor tasking coordination
  - `BattlespaceManagerAgent`: Battlespace assessment and situation analysis
  - `SynthesisQueryAgent`: Intelligence synthesis from fragmented data
- Depends on: `LLMAdapter`, ontology models in `schemas/ontology.py`
- Used by: `TacticalAssistant` (polling new detections), `F2T2EAPipeline` orchestrator

**Data Ontology & State:**
- Purpose: Shared Pydantic models ensuring consistent world-view across agents
- Location: `src/python/core/ontology.py` (base types) and `src/python/schemas/ontology.py` (pipeline types)
- Contains: `Detection`, `Track`, `ActionableTarget`, `CourseOfAction`, `EngagementDecision`, enums for `DetectionType`, `IdentityClassification`, `SensorType`, `ROEAction`
- Depends on: Pydantic, Python stdlib
- Used by: All agents, HITL manager, frontend via WebSocket JSON

**HITL Manager:**
- Purpose: Two-gate approval system: (1) target nomination approval/reject/retask, (2) COA authorization
- Location: `src/python/hitl_manager.py`
- Contains: `StrikeBoardEntry` (frozen dataclass), `CourseOfAction` (frozen dataclass), `HITLManager` singleton managing strike board transitions
- Depends on: Core ontology
- Used by: WebSocket handler, demo autopilot loop, `TacticalAssistant`

**React Frontend (Cesium 3D):**
- Purpose: Real-time geospatial visualization, mission control UI, tactical AIP Assistant widget
- Location: `src/frontend-react/src/`
- Contains: Zustand store (`SimulationStore`), hooks (Cesium integration, WebSocket), panels (Mission/Assets/Enemies tabs), entity managers
- Depends on: Cesium JS, React 18, Zustand, fastapi WebSocket
- Used by: End user for visualization and action dispatch

**Cesium Entity Managers:**
- Purpose: Incremental update of Cesium 3D entities (drones, targets, zones, flow lines, range rings, waypoints, lock indicators)
- Location: `src/frontend-react/src/cesium/useCesium*.ts` hooks
- Contains: Custom hooks managing Cesium entity collections, entity cache refs, reactive updates from store
- Depends on: `useCesiumViewer`, `SimulationStore`, `useWebSocket` context
- Used by: `CesiumContainer` component

## Data Flow

**Simulation Tick (10Hz):**

1. **Simulation Update** (`SimulationModel.tick()`)
   - Advance UAV positions based on mode (SEARCH loiter, FOLLOW orbit, PAINT tight orbit, etc.)
   - Update target positions based on behavior (patrol, stationary, shoot-and-scoot, ambush, flee)
   - Apply sensor models to detect targets based on range, aspect, environment
   - Fuse multi-sensor detections into tracks

2. **Tactical Assistant Processing** (`TacticalAssistant.update(sim_state)`)
   - Identify newly detected targets (state transitioned from UNDETECTED)
   - Fire ISR Observer → Strategy Analyst → HITL nomination pipeline per new detection
   - Populate message queue for next broadcast

3. **WebSocket Broadcast** (connection manager)
   - Send JSON state packet: UAVs, targets, zones, theater bounds, strike board, demo mode flag
   - Send queued assistant messages (INFO/WARNING/CRITICAL)
   - Send HITL updates when COAs generated or nominations advanced

4. **Demo Autopilot Loop** (optional, `demo_autopilot()`)
   - Monitor strike board for PENDING nominations
   - Auto-approve after delay, dispatch UAV to follow/paint target
   - Generate COAs for nominated targets
   - Auto-authorize best COA and dispatch engagement

**User Action Flow (WebSocket command):**

1. **Frontend → Backend** via `useSendMessage()` custom event dispatch
2. **Action validation** via `_validate_payload()` and schema lookup
3. **Rate limiting check** per client
4. **Action handler** dispatch (scan_area, follow_target, paint_target, intercept_target, approve_nomination, authorize_coa, etc.)
5. **Simulation state mutation** (e.g., set drone mode, update target)
6. **Next tick broadcasts updated state** to all clients

**Strike Board Workflow:**

1. **New Target Detected** → `_process_new_detection()` fires ISR→Strategy→HITL
2. **Strategy Analyst Nominates** → `HITLManager.nominate_target()` adds to strike board
3. **Strike Board Entry Status**: PENDING
4. **User Approves** → `hitl.approve_nomination()` → status APPROVED
5. **Tactical Planner Generates COAs** → `_generate_coas()` → `HITLManager.propose_coas()`
6. **User Authorizes COA** → `hitl.authorize_coa()` → status AUTHORIZED
7. **Effectors Execute** → mark as EXECUTING/COMPLETE

**State Management (Frontend):**

- **Zustand Store** (`SimulationStore`) holds global simulation state (UAVs, targets, zones, strikeBoard, theater, demoMode)
- **Cesium Entity Hooks** subscribe to store and maintain 1:1 mapping between store entities and Cesium Primitives
- **Assistant Messages** accumulated in store (max 50 messages, circular buffer)
- **Cached COAs** per strike board entry ID for efficient display

## Key Abstractions

**Track Correlation:**
- Purpose: Group multiple sensor detections of same physical target
- Location: `src/python/sim_engine.py` (`_correlate_detections()`) and `src/python/agents/isr_observer.py`
- Pattern: Euclidean distance threshold (~1km) for spatial grouping, optional LLM refinement for temporal/signature correlation

**Sensor Fusion:**
- Purpose: Combine multi-source sensor reports into confidence-weighted detection
- Location: `src/python/sensor_fusion.py`
- Pattern: `SensorContribution` namedtuple, weighted averaging of confidence scores per sensor type

**Behavior Trees (Unit Types):**
- Purpose: Deterministic movement patterns for targets based on type
- Location: `src/python/sim_engine.py` (`UNIT_BEHAVIOR` dict)
- Pattern: Type → behavior string (stationary, patrol, shoot_and_scoot, ambush)

**LLM Adapter (Abstraction):**
- Purpose: Graceful fallback from LLM-enhanced agent to heuristic path
- Location: `src/python/llm_adapter.py`
- Pattern: All agents try LLM path first; if LLMAdapter returns `None`, fall back to heuristic methods (priority scoring, distance calculations, rule-based logic)

**Immutable State (HITL):**
- Purpose: Prevent accidental corruption of strike board state
- Location: `src/python/hitl_manager.py`
- Pattern: Frozen dataclasses (`StrikeBoardEntry`, `CourseOfAction`) with `dataclasses.replace()` for updates (never mutation)

## Entry Points

**Backend:**
- Location: `src/python/api_main.py`
- Triggers: `uvicorn api_main:app --host 0.0.0.0 --port 8000`
- Responsibilities: FastAPI app creation, WebSocket server, 10Hz simulation loop startup, CORS middleware, settings loading

**Frontend:**
- Location: `src/frontend-react/src/main.tsx`
- Triggers: Vite dev server or built bundle serving via `serve.py`
- Responsibilities: React hydration, WebSocket connection, Zustand store initialization, Cesium viewer setup

**Simulation Entry (Physics Loop):**
- Location: `src/python/api_main.py` async function `_simulation_loop()`
- Triggers: On FastAPI startup
- Responsibilities: 10Hz tick loop, simulation update, tactical assistant processing, broadcast to all connected clients

**Demo Autopilot:**
- Location: `src/python/api_main.py` async function `demo_autopilot()`
- Triggers: When `DEMO_MODE=true` environment variable set
- Responsibilities: Autonomous HITL gate bypass, UAV dispatch, COA generation and authorization, engagement simulation

## Error Handling

**Strategy:** Defensive with fallback to heuristic methods

**Patterns:**
- **LLM Failures** → `LLMAdapter` catches exceptions and returns `None`; agents fall back to heuristic scoring
- **Agent Failures** → `_process_new_detection()` wraps pipeline in try/except; logs error, skips nomination
- **WebSocket Validation** → `_validate_payload()` returns error string; `_send_error()` notifies client
- **Connection Errors** → `ConnectionManager.broadcast()` catches `asyncio.TimeoutError`, `ConnectionError`, `OSError`, logs at debug level (non-blocking)
- **Rate Limiting** → Client messages exceeding 30/sec are silently dropped (no backlog)
- **Theater Loading** → `theater_loader.py` validates YAML, raises descriptive exception on parse failure

## Cross-Cutting Concerns

**Logging:** Structured logging via `structlog` with context fields (target_id, drone_id, action, status). Configured in `src/python/logging_config.py`.

**Validation:**
- Pydantic models enforce schema at ontology boundary
- WebSocket action payload validation via schema dict lookup
- Theater YAML validation on load

**Authentication:** Not implemented — system assumes trusted network (military C2 context). Frontend WebSocket identifies as `DASHBOARD` or `SIMULATOR`; no credential exchange.

**Concurrency:** `asyncio` coroutines for WebSocket handlers and simulation loop. Critical sections (strike board state, simulation state) protected by assumption of single event loop (CPython GIL).

---

*Architecture analysis: 2026-03-19*
