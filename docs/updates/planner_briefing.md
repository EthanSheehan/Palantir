# Grid 11 — Planner Agent Briefing
**Generated:** 2026-03-19
**Purpose:** Complete technical status of the codebase for planning next changes.

---

## 1. System Overview

Grid 11 is a drone fleet management dashboard built on:
- **Backend:** Python FastAPI (port 8012), SQLite, domain-driven architecture with event sourcing
- **Frontend:** Vanilla JavaScript (IIFE modules, no build system), CesiumJS 3D globe, canvas-based timeline
- **Desktop:** PyQt5 WebEngineView wrapper launched via `start.py`
- **Simulation:** 20 UAVs across Romania macro-grid zones with Poisson demand, greedy assignment, and macro-flow rebalancing

---

## 2. Architecture

### 2.1 Backend Stack

```
start.py
  └── backend/main.py (FastAPI, uvicorn, port 8012)
        ├── sim.py (SimulationModel: 20 UAVs, RomaniaMacroGrid)
        ├── app/adapters/simulator_adapter.py (bridges sim to services)
        ├── app/services/
        │     ├── asset_service.py (register, telemetry, status)
        │     ├── mission_service.py (CRUD, state machine)
        │     ├── command_service.py (create, validate, dispatch)
        │     ├── timeline_service.py (reservations, ETAs)
        │     ├── alert_service.py (auto-generation from events)
        │     └── macrogrid_service.py (recommendations, zone states)
        ├── app/event_bus.py (pub/sub with fnmatch patterns)
        ├── app/persistence/ (SQLite repos, ams.db)
        ├── app/domain/ (models, enums, state_machines)
        └── app/api/ (REST + WebSocket endpoints)
```

**Two WebSocket endpoints coexist:**
1. `/ws/stream` (legacy) — broadcasts full sim state at 10Hz to all clients. Used by `app.js` for entity rendering.
2. `/ws/events` (new) — forwards domain events from EventBus. Used by `ws-client.js` for AppState sync.

**Background loops in main.py:**
- `simulation_loop()` at 10Hz: ticks sim, broadcasts state to legacy WS clients
- `telemetry_ingestion_loop()` at 1Hz: reads adapter, persists telemetry, processes macrogrid dispatches

### 2.2 Frontend Stack

```
index.html (entry point, loads all scripts via <script> tags)
  ├── state.js (AppState: centralized pub/sub store)
  ├── api-client.js (REST client for /api/v1/*)
  ├── ws-client.js (WebSocket client for /ws/events)
  ├── workspace-shell.js (layout manager: regions, splitters, tabs, timeline pill/drawer)
  ├── workspace-shell.css (grid layout, floating overlays)
  ├── map-tool-controller.js (Cesium interaction tools: select, waypoint)
  ├── layout-persistence.js (localStorage save/load)
  ├── pane-registry.js + pane-definitions.js (pane metadata)
  ├── panels/
  │     ├── toolbar.js (scrub controls)
  │     ├── timeline-panel.js (canvas swimlane)
  │     ├── mission-panel.js (mission CRUD)
  │     ├── alerts-panel.js (alert list + ack)
  │     ├── inspector-panel.js (entity details)
  │     └── macrogrid-panel.js (recommendations)
  ├── app.js (Cesium viewer init, render loop, entity management, legacy WS client)
  └── style.css (global styles, dark theme)
```

**All JS modules use the IIFE singleton pattern:**
```javascript
const ModuleName = (() => {
    // private state
    return { init, publicMethod };
})();
```

### 2.3 Data Flow

```
SimulationModel.tick() [10Hz]
  └── main.py broadcasts state via legacy WS → app.js receives → updates Cesium entities + requestRender()

SimulatorAdapter.fetch_asset_updates() [1Hz]
  └── AssetService.update_telemetry() → EventBus.publish('asset.telemetry_received')
        └── _broadcast_event() → /ws/events → ws-client.js → AppState.handleEvent()
              └── subscribers notified (panels, timeline, inspector)

User clicks drone on map:
  └── MapToolController._triggerDroneSelection(entity)
        ├── AppState.select('asset', 'ast_N') → 'selection.changed' → timeline re-renders
        └── viewer.flyTo(entity) [if _zoomOnSelect=true]
```

---

## 3. Current UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  TOP TOOLBAR (48px)  [SYSTEM DASHBOARD]  [SELECT][WAYPOINT] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─LEFT PANE (abs)─┐                     ┌─CAM CTRL─┐      │
│  │ [M][A][O][!][G]                    │   🌐     │      │
│  │                 │   CESIUM 3D MAP      │   ✖      │      │
│  │  Active tab     │   (full viewport)    │   ⊡      │      │
│  │  content area   │                     └──────────┘      │
│  │                 │                                        │
│  │                 │                                        │
│  │                 │            ┌──DATE PILL──────┐         │
│  │                 │            │ 17 March 2026 … │         │
│  └─────────────────┘            └─────────────────┘         │
│                  ┌──TIMELINE DRAWER (when open)──┐          │
│                  │ [scrub controls in header]     │          │
│                  │ [canvas: selected UAV lanes]   │          │
│                  └───────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

**Left pane:** `position: absolute; top: 8px; left: 8px; bottom: 8px;` — floats over map with gaps. Tab bar uses 32x32 icon buttons that expand when active. Contains 5 tabs: Mission(M), Assets(A), Ops(O), Alerts(!), Grid(G).

**Timeline pill:** Always visible at bottom-right. Shows live date+time. Click toggles drawer.

**Timeline drawer:** Slides up from bottom with 8px gaps. Left edge respects sidebar width. Vertically resizable. Height persists via LayoutPersistence. Only shows selected UAV's timeline.

**Camera controls:** Permanent pill at top-right (z-index 100). Three buttons: Global view (🌐), Disconnect (✖), Zoom-lock toggle (⊡/⊞).

**Z-index stack:** 100 (toolbar, camera) → 95 (pill) → 90 (drawer) → 85 (splitters) → 80 (left pane)

---

## 4. Key State & Configuration

### 4.1 Layout Persistence (localStorage: `ams.workspace.layout`)
```json
{
    "version": 1,
    "left": { "width": 380, "collapsed": false, "activeTab": "missions" },
    "right": { "width": 340, "visible": false },
    "bottom": { "timelineExpanded": false, "timelineHeight": 30 }
}
```

### 4.2 AppState Structure
```javascript
{
    assets: Map<id, asset>,       // id format: "ast_0" .. "ast_19"
    missions: Map<id, mission>,
    tasks: Map<id, task>,
    commands: Map<id, command>,
    alerts: Map<id, alert>,
    reservations: Map<id, reservation>,
    recommendations: Map<id, recommendation>,
    selection: { assetId, missionId, taskId, commandId, alertId },
    timeCursor: null,             // ms timestamp or null for live
    timeMode: 'live',             // 'live' | 'replay' | 'preview'
    playbackSpeed: 1,
    connected: false,
    eventWsConnected: false,
    filters: { assetStatus: null, missionState: null, alertSeverity: null }
}
```

### 4.3 Cesium Rendering
```javascript
viewer.scene.requestRenderMode = true;
viewer.scene.maximumRenderTimeChange = Infinity;
// Only renders on explicit requestRender() calls from the 10Hz data loop
```

### 4.4 Simulation Constants
- 20 UAVs, `SPEED_DEG_PER_SEC = 0.02`, `SERVICE_TIME_SEC = 2.0`
- UAV modes: idle, serving, repositioning
- Demand: Poisson arrival per zone
- Dispatch: macro-flow rebalancing between zones

### 4.5 ID Conventions
- Cesium entities: `uav_0` .. `uav_19`
- AppState assets: `ast_0` .. `ast_19`
- Bridge in `map-tool-controller.js`: `entity.id.replace('uav_', 'ast_')`

### 4.6 Ports
- Backend API + WS: `8012`
- Frontend HTTP server: `8093`

---

## 5. Known Bugs (Currently Present)

### 5.1 Backend — Silent Error Spam

These errors exist in the running backend but are **hidden** because `start.py` pipes stdout to `subprocess.PIPE` and drains it via a daemon thread:

**Bug 1: `UnboundLocalError` in `ws.py` line 26**
```python
async def _broadcast_event(event: DomainEvent):
    if not _event_clients:     # ← UnboundLocalError
        return
    ...
    _event_clients -= dead     # ← this assignment makes Python treat it as local
```
The `_event_clients -= dead` is an augmented assignment, which makes Python's compiler treat `_event_clients` as a local variable in the entire function scope. The `if not _event_clients:` check then fails because the local hasn't been assigned yet. **Fix:** add `global _event_clients` at top of function.

**Bug 2: `RuntimeError: Set changed size during iteration` in `ws.py`**
When a WebSocket disconnects, the `finally` block calls `_event_clients.discard(ws)` while `_broadcast_event` may be iterating over the same set. **Fix:** iterate over `list(_event_clients)` instead.

**Bug 3: `KeyError: 'source_id'` in `macrogrid_service.py` line 55**
`main.py` passes `sim.active_flows` to `process_dispatches()`, but `active_flows` contains `{"source": coord, "target": coord}` dicts (for rendering flow lines on the frontend). The macrogrid service expects `{"source_id": zone_tuple, "target_id": zone_tuple, "count": N, ...}` dicts from `grid.calculate_macro_flow()`. **Fix:** store raw dispatches from `calculate_macro_flow()` on the sim object and pass those instead.

**Bug 4: Undefined `_ctx` in `ws.py` line 94-95**
The `reset` action handler references `_ctx` which is only defined inside the `spike` branch's local import. Should use `ctx` (the module-level import). Currently unreachable unless user sends a "reset" action via the event WebSocket.

**Impact:** Bug 1 fires on every telemetry event (20x/sec), Bug 3 fires every 1s during telemetry ingestion. Both produce massive log spam but don't crash the server. The frontend continues to work because the legacy `/ws/stream` endpoint is unaffected.

### 5.2 Frontend — No Known Blocking Bugs

The frontend works correctly in the current state. Minor observations:
- Timeline canvas is not DPI-aware (blurry on high-DPI displays)
- No favicon (404 in server logs)
- Snapshot buffer grows unbounded in very long sessions

---

## 6. Attempted & Reverted Changes

The following changes were attempted in this session but **reverted** because they caused regressions:

### 6.1 `start.py` Rewrite
**What was tried:** Auto-kill stale processes on ports, stream backend output with `[BACKEND]`/`[FRONTEND]` prefixes via background threads, increase health timeout to 20s, replace PyQt5 with `webbrowser.open()`.
**Why reverted:** The browser launch worked but PyQt5 is the user's preferred desktop wrapper. The auto-kill and streamed output features were useful but bundled with other changes.

### 6.2 `backend/main.py` — Remove `reload=True`
**What was tried:** Remove uvicorn's `reload=True` to prevent the file-watcher child process from interfering with subprocess management.
**Why reverted:** Reverted as part of full rollback. The reload=True is needed for development workflow.

### 6.3 Backend Bug Fixes (ws.py, sim.py, main.py)
**What was tried:** Fix `global _event_clients`, iterate `list()`, add `sim.last_dispatches`, pass to macrogrid service.
**Why reverted:** Fixes were correct but reverted as part of full rollback to known-good state. **These bugs still exist and should be re-applied.**

### 6.4 `app.js` — Globe Rendering Changes
**What was tried (multiple iterations):**

| Attempt | Setting | Result |
|---------|---------|--------|
| 1 | `requestRenderMode = false` | Globe loads, but simulation becomes very slow (continuous 60fps) |
| 2 | `requestRenderMode = true` + 15s tile kick interval | Globe loads initially but stops streaming detail on zoom |
| 3 | + `tileLoadProgressEvent` listener + `camera.moveEnd` listener | Still didn't maintain detail, and simulation remained slow |

**Root cause:** `requestRenderMode = true` + `maximumRenderTimeChange = Infinity` means Cesium ONLY renders when `requestRender()` is called explicitly. The 10Hz data loop calls it, which is enough for entity movement but NOT for Cesium's tile-streaming pipeline (needs camera-triggered renders for progressive detail loading). Setting `requestRenderMode = false` fixes tile loading but burns GPU at 60fps continuously, making the simulation visually sluggish.

**Current state:** Reverted to `requestRenderMode = true` + `maximumRenderTimeChange = Infinity`. Globe loads and works in PyQt5 (the original configuration that was working before any changes). The trade-off is that zooming in may show lower-detail tiles until the next data update triggers a render.

**What needs investigation:**
1. `maximumRenderTimeChange` set to a small value (e.g., `0.5`) instead of `Infinity` — allows periodic re-renders without full 60fps
2. Only call `requestRender()` on camera events (moveEnd, changed) — targeted renders for tile streaming
3. Profile whether the actual bottleneck is rendering or the data pipeline (Pydantic `model_dump()` at 20 UAVs × 10Hz)

---

## 7. File Inventory

### Frontend (C:\Users\victo\Downloads\grid 11 claude\frontend\)

| File | Lines | Purpose | Cache Version |
|------|-------|---------|---------------|
| `index.html` | 196 | Entry point, DOM structure, script loading | N/A |
| `app.js` | ~1250 | Cesium init, render loop, entity management, legacy WS | `?v=32` |
| `state.js` | 319 | Centralized AppState with pub/sub | — |
| `api-client.js` | ~120 | REST client for /api/v1/* | — |
| `ws-client.js` | ~80 | WebSocket client for /ws/events | — |
| `workspace-shell.js` | 654 | Layout: regions, splitters, tabs, timeline pill/drawer | `?v=14` |
| `workspace-shell.css` | 391 | Layout styles, floating overlays | `?v=16` |
| `map-tool-controller.js` | 496 | Map interaction tools (select, waypoint, zoom-lock) | `?v=14` |
| `layout-persistence.js` | ~60 | localStorage layout save/load | — |
| `pane-registry.js` | ~50 | Pane metadata registry | — |
| `pane-definitions.js` | ~80 | Pane declarations | — |
| `style.css` | 939 | Global component styles, theme | `?v=17` |
| `panels/toolbar.js` | 51 | Scrub controls for timeline header | `?v=11` |
| `panels/timeline-panel.js` | 376 | Canvas swimlane timeline | `?v=19` |
| `panels/mission-panel.js` | ~200 | Mission list + create form | — |
| `panels/alerts-panel.js` | ~120 | Alert list + acknowledge | — |
| `panels/inspector-panel.js` | ~150 | Entity detail inspector | — |
| `panels/macrogrid-panel.js` | ~100 | Grid recommendations | — |
| `Fixed V2.glb` | binary | 3D drone model | — |

### Backend (C:\Users\victo\Downloads\grid 11 claude\backend\)

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 197 | FastAPI app, WS endpoints, background loops |
| `sim.py` | 211 | Simulation model (20 UAVs, Romania grid) |
| `app/event_bus.py` | 58 | Pub/sub with pattern matching |
| `app/dependencies.py` | ~30 | Global application context |
| `app/config.py` | ~15 | Configuration constants |
| `app/domain/models.py` | ~200 | Pydantic domain models |
| `app/domain/enums.py` | ~100 | Status/type enumerations |
| `app/domain/state_machines.py` | ~80 | State transition validation |
| `app/services/asset_service.py` | ~80 | Asset CRUD + telemetry |
| `app/services/mission_service.py` | ~120 | Mission lifecycle |
| `app/services/command_service.py` | ~100 | Command pipeline |
| `app/services/timeline_service.py` | ~80 | Reservation management |
| `app/services/alert_service.py` | ~60 | Alert generation |
| `app/services/macrogrid_service.py` | 122 | Recommendations |
| `app/persistence/database.py` | ~50 | SQLite schema + init |
| `app/persistence/repositories.py` | ~200 | Repository pattern |
| `app/api/router.py` | ~20 | Route aggregator |
| `app/api/assets.py` | ~40 | Asset endpoints |
| `app/api/missions.py` | ~80 | Mission endpoints |
| `app/api/tasks.py` | ~60 | Task endpoints |
| `app/api/commands.py` | ~60 | Command endpoints |
| `app/api/timeline.py` | ~40 | Timeline endpoints |
| `app/api/alerts.py` | ~40 | Alert endpoints |
| `app/api/macrogrid.py` | ~30 | Macrogrid endpoints |
| `app/api/events.py` | ~30 | Event log endpoints |
| `app/api/ws.py` | 111 | Event WebSocket endpoint |
| `app/adapters/simulator_adapter.py` | ~80 | Sim-to-service bridge |
| `app/adapters/base.py` | ~20 | Adapter interface |
| `app/adapters/playback_adapter.py` | ~40 | Replay adapter stub |
| `app/adapters/mavlink_stub.py` | ~20 | MAVLink stub |

### Other

| File | Purpose |
|------|---------|
| `start.py` | PyQt5 desktop launcher |
| `romania_grid.py` | Grid model with 7 macro-zones |
| `ams.db` | SQLite database (WAL mode) |
| `updates/update_plan_1.md` | Architecture restructuring plan |
| `updates/update_plan_2.md` | Workspace shell refactor plan |
| `updates/report_2.md` | UI overhaul documentation |
| `docs/*.md` | 13 specification documents |

---

## 8. Cache Busting Protocol

The frontend uses Python's `http.server` which caches aggressively. When modifying JS/CSS files, you MUST bump the `?v=N` query param in `index.html`:

```html
<script src="app.js?v=32"></script>                <!-- bump this -->
<script src="workspace-shell.js?v=14"></script>     <!-- bump this -->
<script src="map-tool-controller.js?v=14"></script> <!-- bump this -->
<script src="panels/toolbar.js?v=11"></script>      <!-- bump this -->
<script src="panels/timeline-panel.js?v=19"></script><!-- bump this -->
<link href="style.css?v=17" rel="stylesheet">        <!-- bump this -->
<link href="workspace-shell.css?v=16" rel="stylesheet"> <!-- bump this -->
```

Files without `?v=` (state.js, api-client.js, etc.) haven't been modified recently and can be added when needed.

---

## 9. API Endpoints Summary

### REST (http://localhost:8012/api/v1/)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /assets | List assets (filter: status, mode, health) |
| GET | /assets/{id} | Get single asset |
| GET | /missions | List missions (filter: state, priority) |
| GET | /missions/{id} | Get single mission |
| POST | /missions | Create mission |
| POST | /missions/{id}/propose | Propose mission |
| POST | /missions/{id}/approve | Approve mission |
| POST | /missions/{id}/pause | Pause mission |
| POST | /missions/{id}/resume | Resume mission |
| POST | /missions/{id}/abort | Abort mission |
| GET | /tasks?mission_id={id} | List tasks for mission |
| POST | /tasks | Create task |
| GET | /commands | List commands |
| POST | /commands | Create command |
| POST | /commands/{id}/approve | Approve command |
| POST | /commands/{id}/dispatch | Dispatch command |
| GET | /timeline | Get reservations |
| GET | /alerts | List alerts |
| POST | /alerts/{id}/acknowledge | Acknowledge alert |
| GET | /macrogrid/recommendations | Get recommendations |
| POST | /macrogrid/recommendations/{id}/convert | Convert to mission |
| GET | /events | Query event log |
| GET | /health | Health check |

### WebSocket

| Endpoint | Protocol | Purpose |
|----------|----------|---------|
| `/ws/stream` | Legacy JSON | Full state broadcast at 10Hz |
| `/ws/events` | Domain events | EventBus forwarding + initial snapshot |

---

## 10. What Works / What Doesn't

### Works Correctly
- Cesium 3D globe renders with dark CartoDB tiles
- 20 UAVs animate in real-time on the map
- Zone coloring based on imbalance
- Flow lines between zones
- Drone selection → camera tracking
- Waypoint placement via map click
- Left sidebar with 5 tabs (Mission, Assets, Ops, Alerts, Grid)
- Mission CRUD (create, propose, approve, pause, abort)
- Alert list with acknowledge
- Macrogrid recommendations with convert-to-mission
- Timeline pill shows live date/time
- Timeline drawer expands/collapses with persist
- Timeline shows selected UAV's reservation lanes
- Camera controls pill (global view, disconnect, zoom-lock)
- Layout persistence across page reloads
- PyQt5 desktop wrapper launches correctly

### Has Bugs (Non-Blocking)
- Backend error spam (ws.py UnboundLocalError, set iteration, macrogrid KeyError) — hidden in piped output
- `_ctx` undefined in ws.py reset handler
- No favicon (404 on every page load)

### Needs Investigation
- Globe tile detail vs performance trade-off (see Section 6.4)
- Whether `maximumRenderTimeChange` can be tuned for both tile loading and performance
- Long-session memory growth (snapshot buffer, entity cache)
