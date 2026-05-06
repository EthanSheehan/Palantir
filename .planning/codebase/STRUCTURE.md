---
tags: [grid_sentinel, planning, architecture]
---
# Codebase Structure

**Analysis Date:** 2025-03-20

## Directory Layout

```
grid_sentinel/
├── src/
│   ├── python/                           # FastAPI backend + simulation engine
│   │   ├── api_main.py                   # FastAPI app, WebSocket endpoint, 10Hz loop
│   │   ├── sim_engine.py                 # SimulationModel (UAV, target, physics)
│   │   ├── verification_engine.py        # Target state machine (pure function)
│   │   ├── sensor_fusion.py              # Multi-sensor fusion (pure function)
│   │   ├── sensor_model.py               # Sensor detection evaluation
│   │   ├── theater_loader.py             # Load YAML theater configs
│   │   ├── swarm_coordinator.py          # Autonomous UAV transitions
│   │   ├── hitl_manager.py               # Strike board + COA approval gates
│   │   ├── pipeline.py                   # F2T2EA orchestrator
│   │   ├── websocket_manager.py          # ConnectionManager, broadcast logic
│   │   ├── event_logger.py               # Intel/command feed event logging
│   │   ├── intel_feed.py                 # IntelFeedRouter (INTEL_FEED, COMMAND_FEED)
│   │   ├── isr_priority.py               # ISR queue builder
│   │   ├── battlespace_assessment.py     # BattlespaceAssessor (threat rings, coverage)
│   │   ├── llm_adapter.py                # LLMAdapter (OpenAI client wrapper)
│   │   ├── config.py                     # Settings loader (.env)
│   │   ├── logging_config.py             # structlog configuration
│   │   │
│   │   ├── core/                         # Shared data contracts
│   │   │   ├── ontology.py               # Pydantic models (Detection, Location, etc.)
│   │   │   └── state.py                  # LangGraph AnalystState with reducers
│   │   │
│   │   ├── schemas/                      # JSON schema definitions
│   │   │   ├── ontology.json             # Serializable ontology
│   │   │   └── __init__.py
│   │   │
│   │   ├── agents/                       # 9 LangGraph multi-agent orchestration
│   │   │   ├── isr_observer.py           # Sensor fusion, track correlation
│   │   │   ├── strategy_analyst.py       # ROE evaluation, priority scoring
│   │   │   ├── tactical_planner.py       # COA generation (3 options)
│   │   │   ├── effectors_agent.py        # Engagement execution, BDA
│   │   │   ├── pattern_analyzer.py       # Activity pattern analysis
│   │   │   ├── ai_tasking_manager.py     # Sensor retasking optimization
│   │   │   ├── battlespace_manager.py    # Map layers, threat visualization
│   │   │   ├── synthesis_query_agent.py  # SITREP, NL queries
│   │   │   ├── performance_auditor.py    # System performance metrics
│   │   │   └── __init__.py
│   │   │
│   │   ├── vision/                       # Drone video simulator
│   │   │   ├── video_simulator.py        # MJPEG stream generator
│   │   │   └── __init__.py
│   │   │
│   │   ├── utils/                        # Utilities
│   │   │   ├── math_utils.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── tests/                        # pytest test suite
│   │   │   ├── test_pattern_analyzer.py
│   │   │   ├── test_sensor_fusion.py
│   │   │   └── [more tests]
│   │   │
│   │   ├── mission_data/                 # Runtime mission/state files
│   │   ├── data/                         # Generated data cache
│   │   ├── logs/                         # Runtime logs
│   │   └── __init__.py
│   │
│   ├── frontend-react/                   # React + TypeScript frontend
│   │   ├── src/
│   │   │   ├── App.tsx                   # Root component, WebSocket context
│   │   │   ├── main.tsx                  # Vite entry point
│   │   │   │
│   │   │   ├── store/                    # Zustand state management
│   │   │   │   ├── SimulationStore.ts    # Global state (UAVs, targets, zones, UI)
│   │   │   │   └── types.ts              # TypeScript types (UAV, Target, etc.)
│   │   │   │
│   │   │   ├── hooks/                    # Custom React hooks
│   │   │   │   ├── useWebSocket.ts       # WebSocket connection + message routing
│   │   │   │   ├── useCesiumViewer.ts    # Cesium globe reference
│   │   │   │   ├── useDroneCam.ts        # Drone camera PIP stream
│   │   │   │   ├── useSensorCanvas.ts    # Sensor canvas drawing
│   │   │   │   └── useResizable.ts       # Panel resizing logic
│   │   │   │
│   │   │   ├── cesium/                   # Cesium globe integration
│   │   │   │   ├── CesiumContainer.tsx   # Globe rendering + entity updates
│   │   │   │   ├── CameraControls.tsx    # Camera movement/zoom
│   │   │   │   ├── DetailMapDialog.tsx   # Detail map zoom view
│   │   │   │   └── layers/               # Cesium layer definitions
│   │   │   │       ├── index.ts
│   │   │   │       └── [layer files]
│   │   │   │
│   │   │   ├── panels/                   # Sidebar panel components
│   │   │   │   ├── Sidebar.tsx           # Tab switcher (MISSION/ASSETS/ENEMIES/ASSESSMENT)
│   │   │   │   ├── SidebarTabs.tsx       # Tab UI
│   │   │   │   │
│   │   │   │   ├── mission/              # MISSION tab
│   │   │   │   │   ├── MissionTab.tsx    # Main container
│   │   │   │   │   ├── StrikeBoard.tsx   # Target nominations
│   │   │   │   │   ├── StrikeBoardEntry.tsx # Individual entry card
│   │   │   │   │   ├── StrikeBoardCoa.tsx  # COA options dropdown
│   │   │   │   │   ├── AssistantWidget.tsx # Tactical assistant messages
│   │   │   │   │   ├── ISRQueue.tsx      # ISR tasking queue
│   │   │   │   │   ├── IntelFeed.tsx     # Event log (intel + command)
│   │   │   │   │   ├── CommandLog.tsx    # Command history
│   │   │   │   │   ├── GridControls.tsx  # Theater grid visibility
│   │   │   │   │   ├── TheaterSelector.tsx # Theater picker
│   │   │   │   │   ├── CoverageModeToggle.tsx # Balanced/threat-adaptive
│   │   │   │   │   └── AutonomyToggle.tsx # MANUAL/SUPERVISED/AUTONOMOUS
│   │   │   │   │
│   │   │   │   ├── assets/               # ASSETS tab
│   │   │   │   │   ├── AssetsTab.tsx     # Container
│   │   │   │   │   ├── DroneCard.tsx     # Drone status card
│   │   │   │   │   ├── DroneCardDetails.tsx # Expanded details
│   │   │   │   │   ├── DroneModeButtons.tsx # SEARCH/FOLLOW/PAINT/INTERCEPT
│   │   │   │   │   ├── DroneActionButtons.tsx # RTB, RTH, IDLE
│   │   │   │   │   └── TransitionToast.tsx  # Mode change notifications
│   │   │   │   │
│   │   │   │   ├── enemies/              # ENEMIES tab
│   │   │   │   │   ├── EnemiesTab.tsx    # Container
│   │   │   │   │   ├── EnemyCard.tsx     # Target card (SAM, TEL, etc.)
│   │   │   │   │   ├── EnemyUAVCard.tsx  # Enemy drone card
│   │   │   │   │   ├── VerificationStepper.tsx # 4-step progress (DETECTED→CLASSIFIED→VERIFIED→NOMINATED)
│   │   │   │   │   ├── FusionBar.tsx     # Per-sensor confidence chart
│   │   │   │   │   ├── SensorBadge.tsx   # Multi-sensor count badge
│   │   │   │   │   ├── SwarmPanel.tsx    # Swarm coordination UI
│   │   │   │   │   └── ThreatSummary.tsx # Threat summary statistics
│   │   │   │   │
│   │   │   │   └── assessment/           # ASSESSMENT tab
│   │   │   │       ├── AssessmentTab.tsx # Container
│   │   │   │       ├── ZoneThreatHeatmap.tsx # Heatmap by zone
│   │   │   │       ├── CoverageGapAlert.tsx # Low coverage zones
│   │   │   │       └── ThreatClusterCard.tsx # Threat clustering
│   │   │   │
│   │   │   ├── overlays/                 # Full-screen overlays
│   │   │   │   ├── DroneCamPIP.tsx       # Picture-in-picture camera
│   │   │   │   ├── DemoBanner.tsx        # Demo mode indicator
│   │   │   │   ├── MapModeBar.tsx        # Map mode selector (6 tactical views)
│   │   │   │   ├── LayerPanel.tsx        # Layer visibility toggle
│   │   │   │   └── CameraPresets.tsx     # Camera zoom presets
│   │   │   │
│   │   │   ├── shared/                   # Shared utilities
│   │   │   │   ├── api.ts                # API helper functions
│   │   │   │   └── constants.ts          # App-wide constants
│   │   │   │
│   │   │   ├── theme/                    # Blueprint theme customization
│   │   │   │   └── [theme files]
│   │   │   │
│   │   │   ├── index.css                 # Global styles
│   │   │   └── vite-env.d.ts             # Vite type definitions
│   │   │
│   │   ├── public/                       # Static assets
│   │   ├── dist/                         # Vite build output
│   │   ├── vite.config.ts                # Vite configuration
│   │   ├── tsconfig.json                 # TypeScript config
│   │   ├── package.json                  # React dependencies
│   │   └── node_modules/
│   │
│   └── frontend/                         # Legacy vanilla JS frontend (deprecated)
│
├── configs/                              # Configuration files
│   ├── .env.example                      # Environment template
│   └── [other configs]
│
├── theaters/                             # Theater YAML definitions
│   ├── romania.yaml
│   ├── south_china_sea.yaml
│   └── baltic.yaml
│
├── .planning/                            # GSD project management
│   ├── STATE.md
│   ├── PROJECT.md
│   ├── REQUIREMENTS.md
│   ├── ROADMAP.md
│   ├── codebase/                         # Codebase analysis docs
│   │   ├── ARCHITECTURE.md
│   │   └── STRUCTURE.md
│   ├── phases/                           # Phase execution plans (Phase 0-10)
│   └── milestones/
│
├── .ralph/                               # Ralph autonomous execution config
│   ├── fix_plan.md
│   └── .ralphrc
│
├── grid_sentinel.sh                           # Launch script (backend + frontend + simulator)
├── requirements.txt                      # Python dependencies
├── package.json                          # Node.js root (monorepo)
├── CLAUDE.md                             # Project guidelines for Claude
├── README.md
└── [other project files]
```

## Directory Purposes

**`src/python/`**
- Purpose: FastAPI backend, simulation engine, multi-agent orchestration
- Contains: API server, WebSocket handler, physics sim, target verification, sensor fusion, 9 LangGraph agents
- Key files: `api_main.py` (entry point), `sim_engine.py` (UAV/target dynamics), `verification_engine.py` (state machine)

**`src/python/agents/`**
- Purpose: LangGraph-based multi-agent orchestration for F2T2EA kill chain
- Contains: Four core agents (ISR Observer, Strategy Analyst, Tactical Planner, Effectors) + five support agents
- Architecture: All agents communicate via `core/ontology.py` Pydantic models
- No persistent state: Agents are stateless, state managed via LangGraph framework

**`src/python/core/`**
- Purpose: Shared data contracts and state definitions
- Contains: `ontology.py` (Pydantic models), `state.py` (LangGraph AnalystState with reducers)
- Critical: All agents must use these models; deviations break the interface contract

**`src/frontend-react/src/store/`**
- Purpose: Global Zustand state store
- Contains: Full simulation state (UAVs, targets, zones, strike board, feeds, UI state)
- Pattern: Single `useSimStore` hook used throughout React app; no prop drilling

**`src/frontend-react/src/panels/`**
- Purpose: Tabbed sidebar UI components
- Organization: One directory per tab (mission, assets, enemies, assessment)
- Pattern: Each tab reads from `useSimStore`, no inter-component state; one-way data flow

**`src/frontend-react/src/cesium/`**
- Purpose: Cesium globe rendering and entity management
- Contains: `CesiumContainer` (main globe), entity update logic, layer definitions
- Integration: Reads store state, updates Cesium entities; listens to custom window events from Cesium

**`src/frontend-react/src/hooks/`**
- Purpose: Custom React hooks for cross-cutting concerns
- Contains: WebSocket connection, Cesium ref management, drone camera stream, canvas rendering, panel resize
- Pattern: Each hook owns its lifecycle (useEffect cleanup)

**`src/frontend-react/src/overlays/`**
- Purpose: Full-screen overlays (drone camera, demo banner, map mode bar)
- Pattern: Rendered on top of CesiumContainer; z-index managed via CSS
- Not integrated into sidebar flow; independent rendering

**`theaters/`**
- Purpose: Theater configuration files (tactical theaters)
- Format: YAML with waypoints, zones, SAM positions, initial target placements
- Loaded at runtime by `theater_loader.py`
- Examples: `romania.yaml`, `south_china_sea.yaml`, `baltic.yaml`

**`.planning/`**
- Purpose: GSD project management (phases, roadmap, state tracking)
- Contains: Phase execution plans (Phase 0-10), milestone tracking, codebase analysis docs
- Updated by: `/gsd:execute-phase`, `/gsd:progress` commands
- Not code; metadata for orchestration

## Key File Locations

**Entry Points:**

- `src/python/api_main.py`: FastAPI server startup, WebSocket `/ws` endpoint, 10Hz main loop
- `src/frontend-react/src/main.tsx`: Vite dev server entry, renders React into DOM
- `src/frontend-react/src/App.tsx`: Root React component, WebSocket context provider

**Configuration:**

- `src/python/config.py`: Loads settings from `.env` (OPENAI_API_KEY, DEMO_MODE, etc.)
- `src/python/logging_config.py`: structlog configuration (JSON output, log level)
- `src/frontend-react/vite.config.ts`: Vite build settings, proxy to `:8000` for API
- `tsconfig.json`: TypeScript compiler options

**Core Logic:**

- `src/python/sim_engine.py`: UAV positions, target movement, physics (the SimulationModel)
- `src/python/verification_engine.py`: Pure function target state transitions (DETECTED→CLASSIFIED→VERIFIED)
- `src/python/sensor_fusion.py`: Complementary multi-sensor fusion (1 - ∏(1-c_i))
- `src/python/hitl_manager.py`: Strike board + COA approval gates (immutable data objects)
- `src/python/pipeline.py`: F2T2EA orchestrator (ties 4 core agents together)

**Testing:**

- `src/python/tests/`: pytest suite
- Run via: `./venv/bin/python3 -m pytest src/python/tests/`

**Multi-Agent Orchestration:**

- `src/python/agents/*.py`: Nine LangGraph agents
- `src/python/llm_adapter.py`: Wrapper around OpenAI client
- `src/python/core/ontology.py`: Shared data contract (Detection, Location, TargetClassification, etc.)

**WebSocket Communication:**

- `src/python/websocket_manager.py`: ConnectionManager (broadcast, subscriptions, busy tracking)
- `src/python/api_main.py`: WebSocket endpoint handler (routes actions to handlers)
- `src/frontend-react/src/hooks/useWebSocket.ts`: Frontend listener + Zustand updates

**State Management:**

- `src/frontend-react/src/store/SimulationStore.ts`: Zustand store (entire simulation state)
- `src/frontend-react/src/store/types.ts`: TypeScript type definitions for store

## Naming Conventions

**Files:**

- Python: `snake_case.py` (e.g., `sim_engine.py`, `isr_observer.py`)
- TypeScript: `PascalCase.tsx` for components, `camelCase.ts` for utilities (e.g., `CesiumContainer.tsx`, `useWebSocket.ts`)
- YAML: `theater_name.yaml` (e.g., `romania.yaml`)

**Directories:**

- Feature modules: lowercase plural (e.g., `agents/`, `panels/`, `hooks/`)
- Core abstractions: `core/` (shared contracts)
- Generated/runtime: `data/`, `logs/`, `mission_data/`

**Functions:**

- Python: `snake_case()` (e.g., `evaluate_target_state()`, `fuse_detections()`)
- TypeScript: `camelCase()` (e.g., `useCesiumViewer()`, `setSimData()`)
- Handlers: `handle*` prefix (e.g., `handleScanArea()`, `handleApproveTarget()`)

**Variables:**

- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_TURN_RATE`, `FOLLOW_ORBIT_RADIUS_DEG`)
- State: `camelCase` (e.g., `targetId`, `selectedDroneId`)
- Props: `camelCase` (e.g., `droneCard`, `entryId`)

**Types:**

- TypeScript interfaces: `PascalCase` (e.g., `SimState`, `UAV`, `Target`)
- Pydantic models: `PascalCase` (e.g., `Detection`, `ActionableTarget`, `CourseOfAction`)
- Enums: `PascalCase` with `UPPER_CASE` values (e.g., `DetectionType.VEHICLE`, `ROEAction.ENGAGE`)

## Where to Add New Code

**New Feature (e.g., fusion improvements):**
- Primary code: `src/python/` module (e.g., `sensor_fusion.py` for fusion algorithms)
- Tests: `src/python/tests/` with matching name (e.g., `test_sensor_fusion.py`)
- If agent behavior: Update relevant agent in `src/python/agents/`
- If UI: Add component to `src/frontend-react/src/panels/` or `overlays/`

**New Agent (LangGraph):**
- Implementation: `src/python/agents/new_agent_name.py`
- Inputs: Expect Pydantic models from `src/python/core/ontology.py`
- Outputs: Return Pydantic models compatible with ontology
- Integration: Register in `src/python/pipeline.py` or instantiate in `src/python/api_main.py`

**New React Component:**
- Co-located tests: `ComponentName.test.tsx` in same directory
- If feature-specific: Place in `src/frontend-react/src/panels/feature_name/`
- If shared: Place in `src/frontend-react/src/shared/`
- Hook into store via `useSimStore()` for state
- Send WebSocket messages via `useSendMessage()` context

**New Utility Module:**
- Python: `src/python/utils/module_name.py` (add to `__init__.py`)
- TypeScript: `src/frontend-react/src/shared/util_name.ts`
- Both: Write unit tests in adjacent `test_*.py` or `*.test.ts`

**New Theater Config:**
- Location: `theaters/theater_name.yaml`
- Format: Follow `romania.yaml` template (waypoints, zones, SAM positions, initial targets)
- Load via: `theater_loader.load_theater('theater_name')`

**New Verification Threshold (target type):**
- File: `src/python/verification_engine.py`
- Add to: `VERIFICATION_THRESHOLDS` dict with frozen `VerificationThreshold`
- Example: SAM requires 0.7 confidence, 2 sensor types, 10s sustained detection

## Special Directories

**`src/python/logs/`**
- Purpose: Structured event logs (INTEL_FEED, COMMAND_FEED)
- Generated: Yes (at runtime)
- Committed: No (in .gitignore)
- Format: JSON lines (one event per line)
- Rotation: `rotate_logs()` in `event_logger.py` archives old logs

**`src/python/mission_data/`**
- Purpose: Per-mission state files (target tracks, engagement records)
- Generated: Yes (per session)
- Committed: No (in .gitignore)
- Format: JSON serialized state

**`src/python/data/`**
- Purpose: Generated data cache (theater preloads, sensor models)
- Generated: Yes (build step)
- Committed: No (in .gitignore)
- Usage: Speed up initialization

**`src/frontend-react/dist/`**
- Purpose: Vite build output
- Generated: Yes (`npm run build`)
- Committed: No (in .gitignore)
- Cesium assets included in distribution

**`.planning/phases/`**
- Purpose: Phase execution plans (one per phase: 00-foundation, 01-fusion, etc.)
- Generated: Yes (via `/gsd:plan-phase`)
- Committed: Yes (tracking evolution)
- Structure: PLAN.md per phase with objectives, tasks, checklist

**`theaters/`**
- Purpose: Tactical theater configuration (YAML)
- Generated: No (hand-authored)
- Committed: Yes (part of codebase)
- Editable: Terrain, waypoints, SAM positions, target placements

---

*Structure analysis: 2025-03-20*
