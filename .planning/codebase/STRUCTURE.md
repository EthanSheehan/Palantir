# Codebase Structure

**Analysis Date:** 2026-03-19

## Directory Layout

```
Palantir/
├── src/
│   ├── python/                 # FastAPI backend, agents, simulation
│   │   ├── agents/             # LangGraph/LangChain agent implementations
│   │   ├── core/               # Shared ontology and state models
│   │   ├── schemas/            # Pipeline-specific Pydantic models
│   │   ├── mission_data/       # Asset registries, historical activity
│   │   ├── data/               # Data synthesizers, loaders
│   │   ├── tests/              # Unit/integration tests (pytest)
│   │   ├── utils/              # Geo utilities, helpers
│   │   ├── vision/             # Drone video processing, coordinate transforms
│   │   ├── api_main.py         # FastAPI entry point, WebSocket server
│   │   ├── sim_engine.py       # Physics simulation, UAV/target movement
│   │   ├── pipeline.py         # F2T2EA orchestrator
│   │   ├── sensor_fusion.py    # Multi-sensor detection fusion
│   │   ├── sensor_model.py     # Detection probability calculations
│   │   ├── llm_adapter.py      # LLM abstraction with heuristic fallback
│   │   ├── hitl_manager.py     # Strike board, approval gates
│   │   ├── websocket_manager.py # Connection pooling, broadcast
│   │   ├── config.py           # Settings loader (environment vars)
│   │   └── logging_config.py   # Structured logging setup
│   │
│   ├── frontend-react/         # React 18 + Cesium 3D frontend
│   │   ├── src/
│   │   │   ├── cesium/         # Cesium integration hooks and components
│   │   │   ├── panels/         # Sidebar panels (Mission, Assets, Enemies tabs)
│   │   │   ├── hooks/          # React hooks (WebSocket, Cesium, resizing)
│   │   │   ├── store/          # Zustand state management
│   │   │   ├── shared/         # Shared constants, utilities, API helpers
│   │   │   ├── overlays/       # Floating widgets (DemoBanner, DroneCamPIP)
│   │   │   ├── App.tsx         # Root app, WebSocket context, layout
│   │   │   └── main.tsx        # React hydration entry point
│   │   ├── dist/               # Build output (Vite)
│   │   ├── vite.config.ts      # Vite bundler config
│   │   ├── tsconfig.json       # TypeScript config
│   │   └── package.json        # npm dependencies
│   │
│   └── frontend/               # Legacy vanilla JS frontend (pre-React migration)
│       ├── app.js             # Main app controller
│       ├── drones.js          # Drone state and updates
│       ├── map.js             # Cesium map setup
│       ├── websocket.js       # WebSocket client
│       ├── targets.js         # Target management
│       ├── strikeboard.js     # Strike board UI
│       ├── assistant.js       # Tactical assistant widget
│       └── ...                # Other module files
│
├── theaters/                   # Theater configuration YAMLs
│   ├── romania.yaml           # Romania theater (default)
│   ├── south_china_sea.yaml   # SCS theater
│   └── baltic.yaml            # Baltic theater
│
├── docs/                       # Documentation
│   ├── prompts/               # LLM system prompts
│   ├── ARCHITECTURE.md        # Legacy architecture notes
│   └── ...                    # API docs, design docs
│
├── tests/                      # E2E tests (Playwright)
│   ├── e2e/
│   │   ├── fixtures/          # Test data
│   │   ├── pages/             # Page object model
│   │   └── helpers/           # Test utilities
│   └── playwright.config.ts   # Playwright config
│
├── .planning/                  # GSD phase tracking
│   ├── codebase/              # Codebase analysis (ARCHITECTURE.md, STRUCTURE.md, etc.)
│   ├── phases/                # Per-phase plans
│   ├── STATE.md               # Current GSD phase progress
│   ├── ROADMAP.md             # Phase roadmap
│   └── PROJECT.md             # Project spec
│
├── .ralph/                     # Ralph autonomous task loop config
│   ├── fix_plan.md            # Task list for autonomous execution
│   ├── specs/                 # Task specifications
│   └── logs/                  # Execution logs
│
├── configs/                    # Build/deploy configs (unused currently)
├── resources/                  # Legacy test resources
├── palantir.sh                # Launch script (backend + frontend)
├── README.md                   # Project overview
├── CLAUDE.md                   # Claude Code instructions
├── requirements.txt           # Python dependencies
├── package.json               # npm dependencies
└── .env                       # Runtime environment vars (secrets)
```

## Directory Purposes

**`src/python/agents/`:**
- Purpose: Multi-agent kill-chain implementation using LangGraph
- Contains: 9 agent Python modules (ISRObserver, StrategyAnalyst, TacticalPlanner, EffectorsAgent, AITaskingManager, BattlespaceManager, SynthesisQueryAgent, PatternAnalyzer, PerformanceAuditor)
- Key files:
  - `isr_observer.py` — Sensor fusion, track correlation, classification
  - `strategy_analyst.py` — ROE evaluation, priority scoring, nominations
  - `tactical_planner.py` — COA generation with effect prediction
  - `effectors_agent.py` — Strike execution and BDA

**`src/python/core/`:**
- Purpose: Shared data contract across all agents (domain ontology)
- Contains: Base Pydantic models (Detection, Track, ActionableTarget, etc.)
- Key files:
  - `ontology.py` — Core types: Location, Detection, FriendlyForce, RuleOfEngagement, SensorType enums
  - `state.py` — LangGraph state definition for AnalystState workflow

**`src/python/schemas/`:**
- Purpose: Pipeline-specific, detailed Pydantic models (extends core ontology)
- Contains: ISRObserverOutput, StrategyAnalystOutput, TacticalPlannerOutput, CourseOfAction
- Key files:
  - `ontology.py` — Full pipeline types with JSON schema export

**`src/python/mission_data/`:**
- Purpose: Runtime asset and historical data
- Contains: Asset registry (available effectors, friendly forces), historical activity patterns
- Key files:
  - `asset_registry.py` — Effector definitions (missiles, drones, artillery)

**`src/python/vision/`:**
- Purpose: Drone video processing and frame correlation
- Contains: Video simulator (MJPEG generator), coordinate transformer (pixel → WGS-84), dashboard connector
- Key files:
  - `video_simulator.py` — Fake drone camera feed generator
  - `vision_processor.py` — Processed video frame output

**`src/python/tests/`:**
- Purpose: Unit and integration test suite
- Contains: 15+ test files covering agents, sensor fusion, HITL, simulation
- Key files:
  - `conftest.py` — Pytest fixtures (mock agents, sample data)
  - `test_*.py` — Individual test modules
- Run: `./venv/bin/python3 -m pytest src/python/tests/`

**`src/frontend-react/src/cesium/`:**
- Purpose: Cesium 3D visualization hooks and components
- Contains: Custom hooks for entity management (drones, targets, zones, flow lines, range rings, waypoints, lock indicators)
- Key files:
  - `CesiumContainer.tsx` — Main container, initializes viewer and entity hooks
  - `useCesium*.ts` — Individual hooks for entity types (300-400 lines each)
  - `DetailMapDialog.tsx` — Modal for detailed target information
  - `CameraControls.tsx` — Third-person camera controller

**`src/frontend-react/src/hooks/`:**
- Purpose: React hooks for cross-cutting concerns
- Contains: WebSocket integration, Cesium viewer initialization, drone camera, resizable panels
- Key files:
  - `useWebSocket.ts` — WebSocket connection manager, message routing
  - `useCesiumViewer.ts` — Cesium viewer instantiation, auto-cleanup
  - `useDroneCam.ts` — Drone video feed subscription
  - `useResizable.ts` — DOM element resizing

**`src/frontend-react/src/panels/`:**
- Purpose: Sidebar UI panels for mission control
- Contains: Three main tabs (Mission, Assets, Enemies) + sub-components
- Key files:
  - `Sidebar.tsx` — Panel container
  - `SidebarTabs.tsx` — Tab switcher
  - `mission/MissionTab.tsx` — Strike board, COA display, grid controls
  - `assets/AssetsTab.tsx` — Drone list with mode buttons
  - `enemies/EnemiesTab.tsx` — Target list with threat summary

**`src/frontend-react/src/store/`:**
- Purpose: Global state management (Zustand)
- Contains: SimulationStore (UAVs, targets, zones, strike board, UI flags)
- Key files:
  - `SimulationStore.ts` — Main store with setters/getters
  - `types.ts` — TypeScript interfaces for store data

**`src/frontend-react/src/shared/`:**
- Purpose: Shared utilities across frontend
- Contains: API endpoints, constants, geo helpers
- Key files:
  - `api.ts` — API base URL, fetch wrappers
  - `constants.ts` — Max messages, timeouts, UI limits
  - `geo.ts` — Coordinate transforms, distance calculations

**`src/python/`:**
- Purpose: FastAPI backend entry point and core modules
- Key files:
  - `api_main.py` — FastAPI server, WebSocket handler, 10Hz simulation loop
  - `sim_engine.py` — Physics engine (UAVs, targets, behaviors)
  - `pipeline.py` — F2T2EA orchestrator (ISR→Strategy→Tactical→HITL→Effectors)
  - `hitl_manager.py` — Strike board, approval gates (frozen dataclasses)
  - `websocket_manager.py` — Connection pooling, rate limiting
  - `sensor_fusion.py` — Multi-sensor detection fusion
  - `llm_adapter.py` — LLM abstraction with heuristic fallback
  - `config.py` — Settings loader from environment
  - `logging_config.py` — Structured logging with structlog

**`theaters/`:**
- Purpose: Theater configuration (YAML)
- Contains: Romania (default), South China Sea, Baltic theaters
- Structure: Defines zones, base locations, theater bounds, enemy unit placements
- Key files:
  - `romania.yaml` — 9x9 grid theater (default for demos)

**`.planning/`:**
- Purpose: GSD (Get Shit Done) phase tracking
- Contains: Phase plans, state tracking, roadmap
- Key files:
  - `STATE.md` — Current phase progress
  - `ROADMAP.md` — Phase roadmap (phases 0-2+)
  - `codebase/` — Codebase analysis docs

## Key File Locations

**Entry Points:**
- Backend: `src/python/api_main.py` (FastAPI, WebSocket, simulation loop)
- Frontend: `src/frontend-react/src/main.tsx` (React hydration)
- Frontend (legacy): `src/frontend/serve.py` (HTTP dev server for vanilla JS)

**Configuration:**
- Backend config: `src/python/config.py` (loads from `.env`)
- Frontend config: `src/frontend-react/vite.config.ts` (Vite bundler)
- TypeScript: `src/frontend-react/tsconfig.json`

**Core Logic:**
- Simulation: `src/python/sim_engine.py` (physics, UAV modes, target behaviors)
- Agents: `src/python/agents/*.py` (ISR, Strategy, Tactical, Effectors)
- Data Models: `src/python/core/ontology.py` (shared types)
- State: `src/python/core/state.py` (LangGraph state definition)
- HITL: `src/python/hitl_manager.py` (strike board, approval gates)

**Testing:**
- Python tests: `src/python/tests/*.py` (pytest)
- E2E tests: `tests/e2e/*.spec.ts` (Playwright)
- Test config: `tests/playwright.config.ts`

**Documentation:**
- Project: `README.md`, `CLAUDE.md`
- Plans: `.planning/ROADMAP.md`, `.planning/phases/`
- Architecture: `.planning/codebase/ARCHITECTURE.md` (this document)

## Naming Conventions

**Files:**
- Python: `snake_case.py` (modules, agents, utilities)
- React: `PascalCase.tsx` (components), `camelCase.ts` (hooks, utilities)
- YAML: `lowercase_with_underscores.yaml` (theater configs)

**Directories:**
- Feature-based grouping: `agents/`, `panels/`, `cesium/`, `hooks/`
- Type-based grouping: `schemas/`, `core/`, `tests/`
- Stage-based grouping: `src/python/` (backend), `src/frontend-react/` (modern), `src/frontend/` (legacy)

**Functions & Variables:**
- Python: `snake_case` for functions, `UPPERCASE` for constants, `PascalCase` for classes
- React: `camelCase` for functions/variables, `PascalCase` for components, `UPPERCASE` for constants

**Pydantic Models:**
- Core ontology: `src/python/core/ontology.py` (Detection, Track, FriendlyForce, etc.)
- Pipeline extensions: `src/python/schemas/ontology.py` (ISRObserverOutput, StrategyAnalystOutput, etc.)
- Naming pattern: Singular nouns for data objects (Detection, not Detections)

## Where to Add New Code

**New Feature (e.g., new sensor type):**
- Primary code:
  - Add sensor enum: `src/python/core/ontology.py` (SensorType enum)
  - Sensor model: New file `src/python/sensor_model_<type>.py` or extend `sensor_model.py`
  - Agent integration: Modify `src/python/agents/isr_observer.py` to handle new sensor
- Tests: `src/python/tests/test_<feature>.py`

**New Agent (e.g., new reasoning module):**
- Implementation: `src/python/agents/new_agent.py` (inherit from base agent pattern)
- Integration: Update `src/python/pipeline.py` to wire into orchestrator
- Tests: `src/python/tests/test_new_agent.py`

**New React Component:**
- Component file: `src/frontend-react/src/panels/<category>/<ComponentName>.tsx`
- Tests: `tests/e2e/<ComponentName>.spec.ts` (if critical UI flow)
- Export: Add to parent barrel file or import directly

**New Cesium Entity Type:**
- Hook: `src/frontend-react/src/cesium/useCesium<EntityType>.ts` (follow existing hook pattern)
- Integration: Add hook call to `src/frontend-react/src/cesium/CesiumContainer.tsx`
- Store: Add entity type to `src/frontend-react/src/store/types.ts`

**Utilities:**
- Geo helpers: `src/python/utils/geo_utils.ts` (Python) or `src/frontend-react/src/shared/geo.ts` (React)
- Shared constants: `src/frontend-react/src/shared/constants.ts`
- Test fixtures: `src/python/tests/conftest.py` (pytest)

**New Theater:**
- Config: `theaters/new_theater.yaml`
- Registration: Add to `src/python/theater_loader.py` (`list_theaters()`)
- Validation: YAML structure must match expected schema (zones, bounds, units)

## Special Directories

**`src/python/vision/`:**
- Purpose: Drone video processing (currently video_simulator only)
- Generated: Yes (MJPEG frames from simulator)
- Committed: Yes (source code)
- Future: Real video processor will live here

**`src/frontend-react/dist/`:**
- Purpose: Built React + Cesium bundle
- Generated: Yes (by `vite build`)
- Committed: No (.gitignore)

**`.planning/codebase/`:**
- Purpose: Auto-generated codebase analysis (ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md)
- Generated: Yes (by `/gsd:map-codebase` command)
- Committed: Yes (reference docs)

**`.pytest_cache/`, `.playwright-mcp/`:**
- Purpose: Test framework caches
- Generated: Yes
- Committed: No (.gitignore)

**`node_modules/`, `venv/`:**
- Purpose: Dependency installations
- Generated: Yes (by npm/pip)
- Committed: No (.gitignore)

---

*Structure analysis: 2026-03-19*
