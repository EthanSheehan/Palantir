# AMS v0.2 (Grid 11) — Complete System Architecture Document

> **Purpose**: Comprehensive technical reference for the planner agent. Describes every subsystem, file, data flow, interaction pattern, and known limitation in the Grid 11 codebase.
>
> **Last updated**: Grid 11 AMS v0.2 — reflects satellite lens, omnipresent right-click menu, compass resize, timeline fixes, workspace drag fixes, multi-UAV selection, start.py robustness (pipe draining, process tree cleanup, NoCache, GroundPrimitive ready guard).

---

## 1. System Overview

AMS (Advanced Macro System) v0.1 is a real-time UAV fleet management platform built around a **macro-grid** demand/supply rebalancing model over Romania. It combines a 3D Cesium.js geospatial viewer with a domain-driven FastAPI backend, connected via dual WebSocket channels.

### High-Level Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Desktop wrapper | PyQt5 + QWebEngineView (`start.py`) | — |
| 3D Map / UI | Cesium.js 1.114, vanilla JS (IIFE modules), HTML/CSS | 8093 |
| HTTP API | FastAPI (Python) | 8012 |
| Legacy WebSocket | `/ws/stream` — 10Hz simulation state broadcast | 8012 |
| Event WebSocket | `/ws/events` — domain event stream | 8012 |
| Database | SQLite (`ams.db`) | — |
| Simulation | `sim.py` — 20 UAVs, macro-grid flow model | — |

### Startup Sequence

1. `start.py` checks ports 8012/8093 are free, spawns backend (`python main.py` in `backend/`), polls `/health` until ready, spawns frontend (`python -m http.server 8093` in `frontend/`), drains subprocess stdout pipes via daemon threads to prevent buffer deadlock, then opens PyQt5 window with `NoCache` profile
2. Backend `main.py` initializes: SQLite schema → AppContext (repos + services + event bus) → event broadcast wiring → asset registration → starts `simulation_loop()` (10Hz) and `telemetry_ingestion_loop()` (1Hz)
3. Frontend `index.html` loads all JS modules, initializes Cesium viewer, connects legacy WS (`/ws/stream`) and event WS (`/ws/events`), initializes all panel modules

---

## 2. Directory Structure

```
grid 11 claude/
├── .claude/
│   └── launch.json              # Dev server configs (backend:8012, frontend:8093)
├── backend/
│   ├── main.py                  # FastAPI app, WS endpoints, async loops
│   ├── sim.py                   # Simulation model (UAV class, SimulationModel)
│   ├── romania_grid.py          # Symlink/copy — imported by sim.py
│   ├── ams.db                   # SQLite database (auto-created)
│   └── app/
│       ├── config.py            # DB_PATH, TICK_RATE, ADAPTER_TYPE, TELEMETRY_PERSIST_INTERVAL
│       ├── dependencies.py      # AppContext singleton — wires repos, services, bus
│       ├── event_bus.py         # Pub/sub EventBus with pattern matching
│       ├── domain/
│       │   ├── enums.py         # All status/state/type enums
│       │   ├── models.py        # Pydantic entity models (Asset, Mission, Task, Command, etc.)
│       │   └── state_machines.py # Transition maps + validation
│       ├── adapters/
│       │   ├── base.py          # ABC: ExecutionAdapter, TelemetryUpdate, AdapterResult
│       │   ├── simulator_adapter.py  # Wraps sim.py behind adapter interface
│       │   ├── mavlink_stub.py  # Placeholder for real MAVLink integration
│       │   └── playback_adapter.py   # Placeholder for log replay
│       ├── persistence/
│       │   ├── database.py      # SQLite schema init, connection factory
│       │   └── repositories.py  # CRUD repos for all entities + event log
│       ├── services/
│       │   ├── asset_service.py      # Telemetry updates, status transitions
│       │   ├── mission_service.py    # Mission lifecycle (draft→active→completed)
│       │   ├── command_service.py    # Command creation, dispatch, completion
│       │   ├── timeline_service.py   # Reservation management, conflict detection
│       │   ├── alert_service.py      # Auto-alert generation from domain events
│       │   └── macrogrid_service.py  # Recommendation generation from grid flows
│       └── api/
│           ├── router.py        # Mounts all sub-routers under /api/v1
│           ├── assets.py        # GET /assets, GET /assets/{id}
│           ├── missions.py      # CRUD + state transitions for missions
│           ├── tasks.py         # CRUD for mission tasks
│           ├── commands.py      # Command creation + lifecycle
│           ├── timeline.py      # Reservation queries
│           ├── alerts.py        # Alert listing, ack, clear
│           ├── macrogrid.py     # Zone states, recommendations, convert-to-mission
│           ├── events.py        # Event log queries
│           └── ws.py            # /ws/events endpoint + event broadcast handler
├── frontend/
│   ├── index.html               # Main HTML — sidebar, tabs, Cesium container
│   ├── style.css                # 947 lines — dark theme, all component styles
│   ├── state.js                 # AppState — centralized state + pub/sub + snapshot buffer
│   ├── api-client.js            # REST client for /api/v1/*
│   ├── ws-client.js             # Event WebSocket client (/ws/events)
│   ├── app.js                   # ~1400 lines — Cesium setup, 3D rendering, WS bridge, interactions, satellite lens
│   ├── Fixed V2.glb             # 3D drone model (grey quadrotor)
│   └── panels/
│       ├── toolbar.js           # Mode selector, connection status, scrub indicator
│       ├── mission-panel.js     # Mission CRUD UI
│       ├── alerts-panel.js      # Alert display + acknowledge
│       ├── inspector-panel.js   # Context-sensitive entity detail view
│       ├── timeline-panel.js    # Canvas timeline with playhead scrubbing
│       └── macrogrid-panel.js   # Grid recommendations + convert-to-mission
├── romania_grid.py              # Root-level grid class (imported by backend)
├── start.py                     # PyQt5 desktop launcher
├── docs/                        # Design documents (architecture, API contract, etc.)
└── updates/
    └── update_plan_1.md         # Phase 0-6 implementation plan
```

> **Note**: `docs/satellite_lens_spec.md` contains the full detailed spec for the satellite lens feature added in v0.2.

---

## 3. Backend Architecture

### 3.1 Simulation Engine (`sim.py`)

The simulation runs a **demand/supply rebalancing** model over Romania's geography.

**UAV Class** — Individual drone agent:
- State: `(x, y)` position in degrees, `(vx, vy)` velocity in deg/s
- Modes: `idle` (random loiter drift), `serving` (timer countdown), `repositioning` (move to target)
- `commanded_target` takes priority over `target` (manual commands override grid dispatches)
- Loiter drift: random perturbation with 0.95 damping, capped at 30% of max speed
- Arrival threshold: 0.005 degrees (~500m)

**SimulationModel** — Fleet orchestrator:
- `NUM_UAVS = 20`
- `SPEED_DEG_PER_SEC = 0.02` (~2.2 km/s for repositioning, ~0.66 km/s idle drift)
- `SERVICE_TIME_SEC = 2.0` seconds per service event

**Tick cycle** (called at 10Hz):
1. **Zone association**: Count UAVs per zone, pull out-of-bounds UAVs to grid center
2. **Demand generation**: Poisson arrivals per zone based on `demand_rate * dt`
3. **Mission assignment**: Idle UAVs in zones with queued demand → `serving` mode
4. **Macro flow calculation**: `RomaniaMacroGrid.calculate_macro_flow(dt)` → dispatch list
5. **Dispatch execution**: Move idle UAVs from surplus zones to deficit zones
6. **Kinematics update**: `uav.update(dt, speed)` for all UAVs

**`get_state()`** returns:
```json
{
  "uavs": [{"id": 0, "lon": 25.1, "lat": 45.3, "mode": "idle"}, ...],
  "zones": [{"x_idx": 5, "y_idx": 10, "lon": 25.0, "lat": 45.0, "width": 0.192, "height": 0.094, "queue": 3, "uav_count": 2, "imbalance": -1}, ...],
  "flows": [{"source": [25.0, 45.0], "target": [26.0, 46.0]}, ...]
}
```

### 3.2 Romania Macro Grid (`romania_grid.py`)

**Geographic bounds**: LON [20.2, 29.8], LAT [43.6, 48.3]
**Cell size**: 0.192° lon × 0.094° lat (~50×50 grid, ~1532 zones inside Romania polygon)
**Romania polygon**: 43-vertex boundary used for point-in-polygon filtering

**GridZone** attributes:
- `id = (x_idx, y_idx)`, center `(lon, lat)`, dimensions `(width_deg, height_deg)`
- `base_lambda = 0.1` (base demand rate per second)
- `demand_rate` (mutable), `queue` (pending demand), `uav_count`, `imbalance`
- `neighbors`: list of adjacent zones (4-connectivity)

**Flow calculation** (`calculate_macro_flow`):
1. For each zone: `imbalance = MU_CAPACITY_FACTOR * uav_count - queue` (where `MU_CAPACITY_FACTOR = 10.0`)
2. For each neighbor pair: `flow = K_GAIN * (imbalance_target - imbalance_source)` (where `K_GAIN = 0.3`)
3. Positive flow → accumulate in `flow_accum[(source, target)]`
4. When accumulated flow ≥ 1.0: emit dispatch, decrement accumulator

### 3.3 Application Layer (`app/`)

#### Domain Models (`domain/models.py`)

All entities are Pydantic BaseModel with auto-generated UUIDs:

| Entity | Prefix | Key Fields |
|--------|--------|------------|
| Asset | `ast_` | position, velocity, heading, battery, link_quality, status, mode, health |
| Mission | `msn_` | name, type, priority, state, constraints, assigned assets/tasks |
| Task | `tsk_` | mission_id, type, target, state, dependencies |
| Command | `cmd_` | type, target_type, target_id, payload, state lifecycle timestamps |
| TimelineReservation | `res_` | asset_id, phase, start/end time, status, source |
| Alert | `alt_` | type, severity, state, message, source_type/id |
| DomainEvent | `evt_` | type, source_service, entity_type/id, payload, timestamp |

#### State Machines (`domain/state_machines.py`)

Enforced transition maps for all stateful entities:

**Asset**: idle → reserved → launching → transiting → on_task → returning → landing → charging/idle. Wildcard: any → degraded/lost/offline.

**Mission**: draft → proposed → approved → queued → active → paused/completed/aborted/failed → archived.

**Task**: waiting → ready → assigned → transit → active → completed/failed/blocked → cancelled.

**Command**: proposed → validated → rejected/approved → queued → sent → acknowledged → active → completed/failed/expired.

**Alert**: open → acknowledged → cleared.

#### Event Bus (`event_bus.py`)

- Pattern-based pub/sub: exact match, wildcard `*`, or fnmatch glob
- Every `publish()` persists to the event log (SQLite) then dispatches to handlers
- Handlers are async coroutines
- Used for: WS broadcast, alert auto-generation, cross-service communication

#### Services

**AssetService**: `register_asset()`, `update_telemetry()`, `change_status()`, `list_assets()`, `get_asset()`

**MissionService**: `create_mission()`, `propose()`, `approve()`, `reject()`, `queue()`, `activate()`, `pause()`, `resume()`, `complete()`, `abort()`, `fail()`, `archive()`

**CommandService**: `create_command()`, `validate()`, `approve()`, `dispatch()`, `handle_acknowledgement()`, `handle_completion()`, `handle_failure()`

**TimelineService**: `create_reservation()`, `update_reservation()`, `detect_conflicts()`, `list_reservations()`

**AlertService**: `create_alert()`, `acknowledge()`, `clear()`, `setup_subscriptions()` — auto-generates alerts from domain events (low battery, link loss, stale telemetry, command failure)

**MacroGridService**: `process_dispatches()` → converts grid flow dispatches into recommendations with 5-min TTL, `get_recommendations()`, `get_zone_states()`, `convert_to_mission()` → creates rebalance mission from recommendation

#### Adapters

**ExecutionAdapter** (ABC): `send_command()`, `fetch_asset_updates()`, `get_connection_status()`

**SimulatorAdapter**: Wraps `sim.py`. Maps `move_to` commands to `sim.command_move()`. Generates `TelemetryUpdate` from UAV state. Simulates battery drain and link quality fluctuation. Tracks pending commands for completion detection.

**MavlinkStub / PlaybackAdapter**: Placeholders for future real-world and replay modes.

### 3.4 API Endpoints (`api/`)

All REST endpoints under `/api/v1`:

| Route | Methods | Description |
|-------|---------|-------------|
| `/assets` | GET | List assets with filters (status, mode, health, mission_id, capability) |
| `/assets/{id}` | GET | Get single asset |
| `/missions` | GET, POST | List/create missions |
| `/missions/{id}` | GET | Get mission detail |
| `/missions/{id}/propose` | POST | Propose draft mission |
| `/missions/{id}/approve` | POST | Approve proposed mission |
| `/missions/{id}/pause` | POST | Pause active mission |
| `/missions/{id}/resume` | POST | Resume paused mission |
| `/missions/{id}/abort` | POST | Abort active/paused mission |
| `/tasks?mission_id=` | GET, POST | List/create tasks for mission |
| `/commands` | GET, POST | List/create commands |
| `/timeline/reservations` | GET | List timeline reservations |
| `/alerts` | GET | List alerts |
| `/alerts/{id}/ack` | POST | Acknowledge alert |
| `/alerts/{id}/clear` | POST | Clear alert |
| `/macrogrid/zones` | GET | Get all zone states |
| `/macrogrid/recommendations` | GET | Get active recommendations |
| `/macrogrid/recommendations/{id}/convert` | POST | Convert recommendation to mission |
| `/events` | GET | Query event log |

### 3.5 WebSocket Endpoints

**Legacy WS** (`/ws/stream` in `main.py`):
- Accepts commands: `spike`, `move_drone`, `reset`
- Broadcasts full simulation state at 10Hz to all connected clients
- Payload: `{"type": "state", "data": {uavs, zones, flows}}`

**Event WS** (`/ws/events` in `app/api/ws.py`):
- On connect: sends `connection.established` with full asset snapshot
- Forwards ALL domain events from EventBus to connected clients
- Also accepts legacy commands (`spike`, `move_drone`, `reset`) + domain commands
- Used by `ws-client.js` on the frontend

### 3.6 Async Loop Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    asyncio event loop                     │
│                                                          │
│  simulation_loop() ─── 10Hz ──────────────────────────  │
│    sim.tick() → get_state() → JSON → send_text(clients) │
│    await asyncio.sleep(0.1)                              │
│                                                          │
│  telemetry_ingestion_loop() ─── 1Hz ─────────────────── │
│    → asyncio.create_task(_do_telemetry_batch)            │
│      → adapter.fetch_asset_updates() (20 UAVs)          │
│      → asset_service.update_telemetry() × 20             │
│        → bus.publish() → DB persist + WS broadcast       │
│      → adapter.check_completions()                       │
│      → macrogrid_service.process_dispatches()            │
│    await asyncio.sleep(1.0)                              │
│                                                          │
│  [Note: telemetry batch is fire-and-forget via           │
│   create_task to avoid blocking the sim broadcast loop]  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Frontend Architecture

### 4.1 Module Loading Order

Scripts are loaded in `index.html` in this order:
1. `Cesium.js` (CDN)
2. `state.js` → `AppState` global
3. `api-client.js` → `ApiClient` global
4. `ws-client.js` → `WsClient` global
5. `panels/toolbar.js` → `Toolbar` global
6. `panels/mission-panel.js` → `MissionPanel` global
7. `panels/alerts-panel.js` → `AlertsPanel` global
8. `panels/inspector-panel.js` → `InspectorPanel` global
9. `panels/timeline-panel.js` → `TimelinePanel` global
10. `panels/macrogrid-panel.js` → `MacrogridPanel` global
11. `app.js` (v19) — main application logic, initializes everything

All modules use the IIFE pattern: `const ModuleName = (() => { ... return { init, render }; })();`

### 4.2 State Management (`state.js`)

**AppState** is a centralized store with path-based pub/sub:

```javascript
// State shape
{
  assets: Map<id, object>,         // UAV/asset data
  missions: Map<id, object>,       // Mission lifecycle
  tasks: Map<id, object>,          // Mission tasks
  commands: Map<id, object>,       // Command lifecycle
  alerts: Map<id, object>,         // System alerts
  reservations: Map<id, object>,   // Timeline reservations
  recommendations: Map<id, object>,// Grid recommendations
  selection: {
    assetId: null,       // primary selected drone (always = assetIds[0])
    assetIds: [],        // ordered multi-selection: [primary, ...secondaries]
    missionId: null, taskId: null, commandId: null, alertId: null
  },
  timeCursor: null | ms,           // Scrub playhead position (null = live)
  timeMode: 'live' | 'scrub' | 'replay' | 'preview',
  playbackSpeed: 1,
  connected: false,                // Legacy WS connected
  eventWsConnected: false,         // Event WS connected
  filters: { assetStatus, missionState, alertSeverity }
}
```

**Subscription system**: `AppState.subscribe('assets.*', callback)` — supports exact, prefix, and wildcard matching.

**Event reducer**: `AppState.handleEvent(event)` dispatches domain events to update the correct state slice and notify subscribers.

**Snapshot buffer** (for timeline scrubbing):
- Circular buffer of `{time: ms, data: simState}` objects
- Samples at 1Hz (skips if <1s since last push)
- Retains 10 minutes of history
- `getSnapshotAt(ms)` — binary search for closest snapshot
- `getSnapshotBufferRange()` — returns `{start, end}` timestamps

**Multi-selection mutation** (`selectMulti(ids)`):
- `ids` is an ordered array: index 0 is the primary drone, the rest are secondaries
- Sets `assetIds` and keeps `assetId = ids[0]` (or `null` if empty)
- Fires `'selection.changed'` with `{ type: 'asset', id, ids }`
- All existing single-drone consumers (`assetId`) continue to work unchanged

**Time cursor**:
- `setTimeCursor(ms)` — sets cursor, auto-switches timeMode between `live` and `scrub`
- `setTimeCursor(null)` — returns to live mode
- Notifies `time.cursorChanged` and `time.modeChanged`

### 4.3 Communication Layer

**ApiClient** (`api-client.js`):
- Base URL: `http://{hostname}:8012/api/v1`
- Methods for all CRUD + state transition operations
- JSON request/response with error parsing

**WsClient** (`ws-client.js`):
- Connects to `ws://{hostname}:8012/ws/events`
- Auto-reconnect on disconnect (2s delay)
- Routes incoming events to `AppState.handleEvent()`
- Sets `AppState.setEventWsConnected()`

**Legacy WS** (in `app.js`):
- Connects to `ws://{hostname}:8012/ws/stream`
- Receives 10Hz state broadcasts
- Drives `updateSimulation()` for 3D map rendering
- Sends commands: `spike`, `move_drone`, `reset`
- Buffers snapshots via `AppState.pushSnapshot()`
- Skips map updates when in scrub mode (`timeMode !== 'live'`)

### 4.4 3D Visualization (`app.js`)

**Cesium Viewer Configuration**:
- CartoDB Dark Matter basemap with brightness 1.8, gamma 1.2
- World terrain enabled
- Cinematic lighting, sun/moon disabled
- Initial camera: lon 24.9668, lat 41.2, altitude 500km, pitch -45°
- Clock frozen at 2023-06-21T10:00:00Z (summer solstice for consistent lighting)
- Request render mode (not continuous) — `viewer.scene.requestRender()` called explicitly

**Grid Visualization** (`initOrUpdateZonesPrimitive`):
- Uses Cesium `GroundPrimitive` with `GeometryInstance` per zone for high performance
- Zone fill color: red intensity proportional to queue size
- Zone borders: separate primitive with dark blue outlines
- Three visibility states: ON (fill + borders), SQUARES ONLY (borders only), OFF

**UAV Rendering** (per drone):
- `SampledPositionProperty` with Hermite interpolation for smooth movement
- `SampledProperty(Quaternion)` for smooth heading rotation
- Three LOD levels via `distanceDisplayCondition`:
  - 0-20km: 3D model (`Fixed V2.glb`, grey quad)
  - 2km-800km: SVG billboard (colored pin)
  - 800km+: Point primitive (colored dot)
- Ground tether: `CallbackProperty` polyline from drone to ground
- Color coding: blue (idle), green (serving), yellow (repositioning)

**Interpolation buffer system**:
- Each WS frame adds a position sample 0.3s into the future
- Subsequent samples spaced exactly 0.1s apart
- Drift check: if buffer < 0.1s or > 0.5s from now → resync to now + 0.3s
- This absorbs network jitter and produces smooth 60fps movement from 10Hz updates

**Heading calculation**:
- Derived from velocity vector with map projection correction (`cos(lat)`)
- 180° rotation applied (model faces backward)
- Low-pass filter: 30% blend per tick to prevent snapping
- Movement threshold: 0.002° to suppress jitter

**Flow lines**: Cesium polyline entities with cyan glow material, recreated each frame.

**Waypoint system**:
- Per-drone waypoint markers: green cylinder (2km tall, 20m radius)
- Dashed trajectory line from drone to waypoint (CallbackProperty)
- Auto-cleared when drone arrives (mode changes from `repositioning`)
- Visibility controlled by "All Waypoints" toggle or tracking state

**Range visualization**:
- Per-drone 50km range cone: 3 concentric rings at altitudes 500m, 1500m, 3000m
- Rings follow drone position via CallbackProperty
- Toggle via "Range" button on tracked drone card

### 4.5 Timeline Scrubbing System

**Timeline Panel** (`panels/timeline-panel.js`):
- Canvas-based renderer with dark background (#0a0f19)
- Horizontal time axis with auto-scaling tick intervals — **always rendered** even when no UAV is selected
- Swimlanes per asset showing reservation phases (color-coded) — one lane per selected UAV
- Multi-UAV lane rendering: reads `AppState.state.selection.assetIds` to show all selected drones as ordered swimlanes; time axis renders with no lanes when `assetIds` is empty
- Red "now" marker line
- Gold (#facc15) playhead with triangle handle and timestamp label
- Subtle yellow tint showing snapshot buffer range

**Interaction model**:
| Action | Result |
|--------|--------|
| Click on data area (not near playhead) | Place playhead at clicked time |
| Click near playhead + drag | Scrub through time |
| Drag on background (not playhead) | Pan the time window |
| Double-click on data area | Return to live, remove playhead |
| Scroll wheel | Zoom in/out — anchored on gold scrub bar if active, otherwise red "now" line |

**Timeline zoom anchor**: Zoom pivots on `_playheadMs` (yellow scrub bar) if set, otherwise `Date.now()` (red now line). Falls back to viewport center only if the anchor is off-screen.

**Scrub rendering** (`scrubToSnapshot` in `app.js`):
- Uses `ConstantPositionProperty` instead of `SampledPositionProperty`
- Stashes the live position property in `marker._livePosProperty`
- Updates zones and flows normally
- Does NOT corrupt the interpolation buffer

**Return to live** (`restoreLivePositions` in `app.js`):
- Restores stashed `SampledPositionProperty`
- Resets `marker._lastTargetTime = null` so interpolation re-syncs
- Triggers `viewer.scene.requestRender()`

**Toolbar indicator** (`panels/toolbar.js`):
- Shows "SCRUB: HH:MM:SS" with gold pulsing animation when scrubbing
- "RETURN TO LIVE" button calls `AppState.setTimeCursor(null)`

### 4.6 Multi-UAV Selection

The system supports selecting multiple UAVs simultaneously. Selected UAVs are shown as parallel swimlanes in the timeline and highlighted with secondary (cyan) ring entities on the globe.

#### State shape

```javascript
// AppState.state.selection
{
  assetId: "ast_0",          // primary selected drone — always assetIds[0]
  assetIds: ["ast_0", "ast_3", "ast_7"],  // ordered multi-selection
  ...
}
```

**Invariant**: `assetId` is always equal to `assetIds[0]` (or `null` if empty). All existing single-drone consumers (inspector, compass, satellite lens, waypoints) use `assetId` and continue to work unchanged.

#### Adding/removing drones (`map-tool-controller.js`)

**Shift+click on globe** — Cesium fires `LEFT_CLICK` with `KeyboardEventModifier.SHIFT` as a **separate event type** from plain `LEFT_CLICK`. You must register a dedicated handler:

```javascript
// In MapToolController.init():
handler.setInputAction((movement) => {
    _tools[_activeTool]?.onShiftLeftClick?.(movement);
}, Cesium.ScreenSpaceEventType.LEFT_CLICK, Cesium.KeyboardEventModifier.SHIFT);
```

The `_selectTool.onShiftLeftClick` handler calls `_triggerDroneSelectionAdditive(entity)`, which:
1. If entity is not in `assetIds` — appends it (no camera move for secondaries)
2. If entity IS the primary — removes it and promotes the next drone to primary
3. If entity is a secondary — removes it from the array
4. Calls `AppState.selectMulti(newIds)` to commit

#### Adding via drag-and-drop (`app.js` → `panels/timeline-panel.js`)

Drone cards in the ASSETS panel have `draggable="true"` and a `dragstart` handler setting `dataTransfer.setData('uavId', String(u.id))`.

The timeline canvas has `dragover` (preventDefault) and `drop` listeners. On drop, the `uavId` is read from `dataTransfer`, the Cesium entity `'uav_' + uavId` is looked up, and `MapToolController._triggerDroneSelectionAdditive(entity)` is called. Dropping an already-selected UAV is a no-op (additive logic deduplicates).

#### Removing via × button in timeline (`panels/timeline-panel.js`)

Each lane header shows a `×` button on hover. It is drawn directly on the `<canvas>`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `REMOVE_BTN_X` | `2` | X pixel offset of × button from left edge |
| `LANE_HEIGHT` | `28` | Total lane height; button is `LANE_HEIGHT - 8 = 20px` square |
| label X (hovering) | `REMOVE_BTN_X + (LANE_HEIGHT - 8) + 4 = 26` | UAV label shifts right when × is visible |

Mouse tracking uses `mousemove` on the canvas container: when `canvasX < HEADER_WIDTH`, the hovered lane index is computed and stored in `_hoveredLaneIdx`. On `click`, if the click falls within the × hit area (`canvasX < REMOVE_BTN_X + 20`), `AppState.selectMulti(assetIds.filter(id => id !== removedId))` is called.

#### Secondary rings on globe (`app.js`)

`_syncSecondaryRings()` runs on every `'selection.changed'` event. It reconciles the `_secondarySelectionRings[]` entity array with `assetIds.slice(1)` (all non-primary selections). Each secondary ring is a Cesium polyline entity with:
- Color: `#22d3ee` (cyan)
- Radius: `~1100m`
- Position: `CallbackProperty` returning the current drone entity position

Rings for deselected drones are removed from `viewer.entities` and the array is spliced.

### 4.7 Camera System (was 4.6)

**Three camera modes**:

1. **Global view**: Default. Free camera at 500km altitude over Romania.
2. **Macro tracking** (single-click drone): Flies to 10km altitude above drone. Uses manual position nudging (`macroTrackedId` + `isMacroTrackingReady`) instead of Cesium's `trackedEntity` to prevent snapping.
3. **Third-person** (double-click drone): Locks camera behind drone at 100m offset, 150m range. Uses `entity.viewFrom = new Cesium.Cartesian3(0, -100, 30)` + `viewer.trackedEntity`.

**Camera controls** (visible when tracking):
- "Global View" button: Returns to default 500km view
- "Decouple Camera" button: Stops tracking, keeps current camera position

**3D compass**: Polyline entity (`compassEntity`) pointing north (or drone heading when tracking) from the compass center. A ring entity (`compassRingEntity`) draws a 64-segment circle at the same center. Both use `CallbackProperty` referencing `getCompassCenter()` and `_compassScale`.

**Compass resize**: `Shift+scroll` on the Cesium canvas multiplies `_compassScale` by 0.9 or 1.1 per tick, clamped to `[0.1, 10.0]`. Affects needle length (`2000 * _compassScale` metres) and ring radius (`1500 * _compassScale` metres).

**`getCompassCenter()`**: Returns compass/lens anchor — the tracked drone's ground projection (height=0) if a drone is tracked, otherwise `currentMousePosition`.

**Satellite lens**: A second `Cesium.Viewer` (`_lensViewer`) renders Bing Maps Aerial (Ion asset 2) clipped to the compass ring area. See `docs/satellite_lens_spec.md` for full details. Key variables: `_lensActive` (bool toggle), `_lensViewer` (lazy-initialized on first activation). Toggled by `🔭` button (`#satelliteLensBtn`).

**Right-click context menu** (`#drone-context-menu`): Opens on every right-click anywhere on the globe (not just over drones). Three items:
- **Satellite Circle** — always shown. Label reflects current ON/OFF state. Clicking it triggers `#satelliteLensBtn.click()`.
- **Set Waypoint** — shown only when a drone is currently selected/tracked (`trackedDroneEntity != null`). Acts on the already-selected drone.
- **Range** — shown only when right-clicking directly over a drone entity.
The `RIGHT_CLICK` handler in `map-tool-controller.js` always fires its callbacks, passing `null` as entity when no drone is under the cursor.

### 4.8 Sidebar UI

**5 tabs**: MISSION, ASSETS, OPS, ALERTS, GRID

**MISSION tab**: Mission creation form (name, type, priority, objective) + mission card list sorted by priority. Card shows: name, state badge, type, task/asset counts, action buttons (propose/approve/pause/abort).

**ASSETS tab**: Drone card list with real-time updates. Card shows: ID, status badge. When tracked: altitude, coordinates, Set Waypoint/Range/Detail Waypoint buttons. Single-click → macro track. Double-click → 3rd person.

**OPS tab**: Inspector panel showing context-sensitive details for selected entity (asset/mission/alert).

**ALERTS tab**: Alert cards sorted by severity. Shows: icon, type, state, message, source, acknowledge button.

**GRID tab**: Macro-grid recommendations. Shows: source→target zone, confidence %, suggested asset count, pressure delta. "Convert to Mission" button.

### 4.9 UI Controls

- **Grid Visibility**: Cycles ON → SQUARES ONLY → OFF
- **All Waypoints**: Toggles visibility of all drone waypoints
- **Override: Reset Grid**: Sends reset command to clear all zone queues
- **Set Waypoint**: Click-to-place mode — next map click sends `move_drone` command (accessible via ASSETS tab card or right-click menu when a drone is selected)
- **Detail Waypoint**: Opens modal with coordinate input for precise waypoint
- **Demand Spike**: Double-click on map sends `spike` command at clicked location
- **Satellite Circle** (`🔭`): Toggles satellite lens overlay. Also accessible via right-click context menu anywhere on the globe.
- **Compass resize**: `Shift+scroll` over the globe resizes the compass ring/needle
- **Return to Global** (`🌐`), **Decouple Camera** (`✖`), **Lock Zoom** (`⊡`): Camera control buttons (top-right of globe)

---

## 5. Data Flow Diagrams

### 5.1 Real-Time Update Flow

```
sim.tick() ─10Hz──→ get_state()
                        │
                   JSON serialize
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
     /ws/stream clients      telemetry_ingestion_loop (1Hz)
              │                    │
              ▼                    ▼
    app.js onmessage         SimulatorAdapter.fetch_asset_updates()
              │                    │
     ┌────────┴────────┐          ▼
     ▼                 ▼    AssetService.update_telemetry() ×20
 pushSnapshot()   updateSimulation()    │
     │                 │          ▼
     ▼                 ▼    EventBus.publish("asset.telemetry_received")
  buffer         Cesium 3D         │
  (1Hz sample)   rendering    ┌────┴─────┐
                              ▼          ▼
                         DB persist  /ws/events broadcast
                                         │
                                         ▼
                                   ws-client.js
                                         │
                                         ▼
                                  AppState.handleEvent()
                                         │
                                         ▼
                                  Panel re-renders
```

### 5.2 Command Flow

```
User clicks "Set Waypoint" → clicks map
         │
         ▼
ws.send({action: "move_drone", drone_id, target_lon, target_lat})
         │
         ▼
/ws/stream handler in main.py → sim.command_move(id, lon, lat)
         │
         ▼
UAV.commanded_target = (lon, lat), mode = "repositioning"
         │
         ▼
[next sim.tick()] → UAV moves toward target → state broadcast
         │
         ▼
Frontend sees mode="repositioning" → yellow color, waypoint line
         │
         ▼
[arrival] → commanded_target = None, mode = "idle"
         │
         ▼
Frontend auto-clears waypoint marker
```

### 5.3 Mission Lifecycle

```
User fills form → "CREATE MISSION" button
         │
         ▼
ApiClient.createMission({name, type, priority, objective})
         │
         ▼
POST /api/v1/missions → MissionService.create_mission()
         │                         │
         ▼                         ▼
    DB insert              EventBus → "mission.created"
                                   │
                              ┌────┴────┐
                              ▼         ▼
                         /ws/events   alert_service
                              │       (may generate alert)
                              ▼
                      AppState.handleEvent()
                              │
                              ▼
                      MissionPanel.render()
                      (shows new card with "Propose" button)
```

---

## 6. Database Schema

SQLite database at `backend/ams.db`. Tables:

- **assets** — Full asset state (position, velocity, battery, etc.)
- **missions** — Mission lifecycle with JSON columns for constraints, asset_ids, task_ids, tags
- **tasks** — Mission tasks with JSON columns for target, dependencies, constraints
- **commands** — Command lifecycle with full timestamp tracking
- **timeline_reservations** — Asset phase reservations for timeline display
- **alerts** — System alerts with severity and acknowledgement state
- **event_log** — Append-only event log (sequential ID + JSON domain event)

---

## 7. Key Technical Decisions & Patterns

### Dual WebSocket Architecture
- **Legacy WS** (`/ws/stream`): High-frequency (10Hz) raw simulation state for 3D rendering. Lightweight, no persistence.
- **Event WS** (`/ws/events`): Domain events for UI panel updates. Persisted to event log. Lower frequency but richer data.
- Rationale: The 3D map needs 10Hz position updates but panels only need event-driven updates. Separating these prevents the domain layer from being overwhelmed.

### SampledPositionProperty Interpolation
- Cesium's `SampledPositionProperty` with Hermite interpolation produces 60fps smooth movement from 10Hz data
- Position samples are placed 0.3s in the future with 0.1s spacing
- Buffer drift check prevents starvation or lag buildup
- Critical: scrub mode uses `ConstantPositionProperty` to avoid corrupting the interpolation buffer

### Fire-and-Forget Telemetry
- The telemetry ingestion loop spawns each batch as `asyncio.create_task()` with `await asyncio.sleep(0)` between assets
- This prevents the heavy DB/event work from blocking the simulation broadcast loop
- The simulation loop can maintain 10Hz broadcasts regardless of how long telemetry processing takes

### IIFE Module Pattern
- All frontend JS uses `const Module = (() => { ... return { init, render }; })();`
- No build step, no bundler, no framework
- Modules communicate through `AppState` pub/sub, not direct imports
- Panel initialization is guarded: `if (typeof Module !== 'undefined') Module.init();`

### Drag Resize Without CSS Transition Lag (`ws-dragging`)
Dragging the left-pane splitter or the timeline resize handle was laggy because CSS `transition` properties (e.g., `width 0.2s`, `height 0.35s`) kept animating toward each intermediate drag position. The fix: a single CSS class suppresses all transitions during the drag gesture and is removed immediately on mouseup so animations still work for collapse/expand.

```css
/* workspace-shell.css */
.ws-dragging { transition: none !important; }
```

Applied in `workspace-shell.js`:
- Left splitter drag: `ws-dragging` added to `#ws-region-left` on first mousemove, removed on mouseup
- Timeline pill drag: `ws-dragging` added to both the drawer div and `#ws-timeline-pill` button on mousedown, removed on mouseup
- Additionally, `TimelinePanel.resize()` is called on every left-splitter drag frame so the timeline canvas repaints in sync with the pane width changing

### Frontend Cache-Busting (`?v=N`)
The frontend is served by Python's built-in `http.server` with no cache headers. Browsers aggressively cache JS and CSS files, so edits to `app.js` will NOT be picked up on a normal page reload unless the URL changes.

**The pattern**: All script and link tags in `index.html` use a query-string version suffix:
```html
<script src="app.js?v=32"></script>
<script src="workspace-shell.js?v=14"></script>
<link href="style.css?v=17" rel="stylesheet">
```

**Rule for agents**: Every time you edit a JS or CSS file, increment its `?v=N` counter in `index.html`. The number itself has no meaning — it just makes the browser treat the URL as new and bypass the cache. The current version numbers as of v0.2:

| File | Current `?v=` |
|------|--------------|
| `app.js` | 32 |
| `workspace-shell.js` | 14 |
| `map-tool-controller.js` | 14 |
| `panels/timeline-panel.js` | 19 |
| `panels/toolbar.js` | 11 |
| `style.css` | 17 |
| `workspace-shell.css` | 16 |

Files **without** a version suffix (loaded without `?v=`) do not need incrementing because they are either stable or infrequently edited: `state.js`, `api-client.js`, `ws-client.js`, `pane-registry.js`, `pane-definitions.js`, `layout-persistence.js`, and the panel files not listed above.

After incrementing the version and reloading, always do a **hard reload** (`Ctrl+Shift+R`) in the browser, or verify via the console that `document.querySelector('script[src*="app.js"]').src` shows the new version number.

### State Machine Enforcement
- All entity state transitions are validated against explicit transition maps
- `validate_transition()` raises `InvalidTransitionError` for invalid transitions
- Wildcard transitions (e.g., any asset state → `degraded`/`lost`) handled via `"*"` key

---

## 8. Known Limitations & Technical Debt

1. **No authentication/authorization** — All endpoints are open
2. **SQLite single-writer** — Will not scale to multiple backend instances
3. **No pagination** on list endpoints — All results returned at once
4. **Telemetry not pruned** — Event log grows unbounded
5. **Adapter stubs** — MAVLink and playback adapters are empty placeholders
6. **No test suite** — Zero automated tests
7. **Hardcoded Cesium Ion token** in `app.js` — Should be environment variable
8. **No error boundaries** in frontend — JS errors can break the entire UI
9. **Waypoint persistence** — Waypoints exist only in frontend memory, lost on refresh
10. **Grid reimport** — `romania_grid.py` exists both at root and in backend, no symlink guarantee
11. **Start.py** — PyQt5 WebEngine cache is disabled (NoCache); process tree cleanup uses `taskkill /T` on Windows
12. **No HTTPS/WSS** — All connections are unencrypted
13. **Frozen Cesium clock** — Set to 2023-06-21 for lighting; real-time features may not work correctly with Cesium's time system
14. **Mission→Task→Command pipeline** — Missions can be created but the full automation chain (auto-generate tasks, dispatch commands) is not wired end-to-end
15. **Timeline reservations** — The reservation system exists but is not populated by the simulation; timeline swimlanes are mostly empty unless manually created via API
