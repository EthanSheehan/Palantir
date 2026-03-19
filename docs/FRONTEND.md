# Palantir Frontend — Technical Reference

**Date:** 2026-03-19

> **Note:** This document covers both the **React frontend** (primary, `src/frontend-react/`) and the **legacy vanilla JS frontend** (`src/frontend/`, reference only). The React frontend is the active development target.

---

## React Frontend (Primary)

### Stack

| Property | Detail |
|----------|--------|
| Language | TypeScript |
| Framework | React 18 |
| Build tool | Vite 5 |
| 3D Engine | Cesium JS v1.114 (`cesium` + `vite-plugin-cesium`) |
| UI Kit | Blueprint.js 5 (dark theme) |
| Charts | ECharts 5 (`echarts-for-react`) |
| State | Zustand 4 |
| Dev server | `npm run dev -- --port 3000` |

### File Structure

```
src/frontend-react/src/
  App.tsx                    # Root layout — sidebar + globe + overlays
  main.tsx                   # Entry — Blueprint theme, Zustand, ECharts theme
  store/
    SimulationStore.ts       # Zustand store (sim state + UI state)
    types.ts                 # TS types: UAV, Target, Zone, StrikeEntry, COA…
  hooks/
    useWebSocket.ts          # WebSocket connection, reconnect, message routing
    useDroneCam.ts           # Canvas render loop — synthetic drone camera feed
    useResizable.ts          # Resizable sidebar hook
    useCesiumViewer.ts       # Cesium viewer lifecycle
  cesium/
    CesiumContainer.tsx      # Viewer lifecycle, wires all Cesium hooks
    CameraControls.tsx       # Globe-return + camera decouple buttons
    DetailMapDialog.tsx      # Precision waypoint placement modal
    useCesiumDrones.ts       # UAV 3D entity rendering (mode-colored labels)
    useCesiumTargets.ts      # Target entities (type/ID labels + threat rings)
    useCesiumZones.ts        # Grid zone visualization
    useCesiumFlowLines.ts    # Asset-to-target flow lines
    useCesiumCompass.ts      # Compass needle + ring
    useCesiumMacroTrack.ts   # Smooth camera follow (macro mode)
    useCesiumClickHandlers.ts # Entity picking, waypoint placement, spike
    useCesiumRangeRings.ts   # Sensor range ring overlays
    useCesiumWaypoints.ts    # Waypoint cylinders + trajectory polylines
    useCesiumLockIndicators.ts # Red pulsing lock ring on PAINT targets
  panels/
    Sidebar.tsx              # Resizable sidebar container
    SidebarTabs.tsx          # MISSION / ASSETS / ENEMIES tab navigation
    mission/
      MissionTab.tsx         # Theater selector + assistant + strike board
      TheaterSelector.tsx    # Theater dropdown
      AssistantWidget.tsx    # Tactical AIP message feed
      StrikeBoard.tsx        # Strike board container
      StrikeBoardEntry.tsx   # Nomination entry (Gate 1)
      StrikeBoardCoa.tsx     # COA entry (Gate 2)
      GridControls.tsx       # Zone grid visibility controls
    assets/
      AssetsTab.tsx          # Drone card list
      DroneCard.tsx          # Card with mode tag + drone cam activation
      DroneCardDetails.tsx   # Expanded stats (altitude, sensor, coords)
      DroneModeButtons.tsx   # SEARCH / FOLLOW / PAINT / INTERCEPT buttons
      DroneActionButtons.tsx # Waypoint / range ring toggles
    enemies/
      EnemiesTab.tsx         # Enemy card list (sorted, hysteresis-filtered)
      EnemyCard.tsx          # Target card with type badge, state, tracking info
      VerificationStepper.tsx # 4-step dots + confidence progress bar
      FusionBar.tsx          # Per-sensor confidence stacked bar (ECharts)
      SensorBadge.tsx        # Sensor count badge with intent color
      ThreatSummary.tsx      # Threat level summary
  overlays/
    DroneCamPIP.tsx          # Synthetic drone camera PIP (bottom-right)
    DemoBanner.tsx           # Demo mode indicator strip
  shared/
    constants.ts             # Mode styles, target map, sensor constants
    geo.ts                   # Haversine distance, bearing helpers
    api.ts                   # WebSocket message builder
  theme/
    palantir.ts              # ECharts Palantir dark theme
```

### Enemy Card Components (Verification UI)

The ENEMIES tab renders per-target cards with these verification-specific components:

**VerificationStepper** — Shows the 4-step progression (DETECTED → CLASSIFIED → VERIFIED → NOMINATED) as color-coded dots:
- Completed steps: green
- Current step: orange
- Future steps: gray
- Includes a ProgressBar showing confidence progress toward the next threshold
- Shows a **VERIFY** button on CLASSIFIED targets for manual operator override

**FusionBar** — Stacked horizontal bar chart (ECharts) showing per-sensor-type confidence contributions:
- EO_IR: blue (`#4A90E2`)
- SAR: green (`#7ED321`)
- SIGINT: orange (`#F5A623`)
- Displays total fused confidence as a percentage label

**SensorBadge** — Blueprint Tag showing how many distinct sensor types observe the target:
- 1 sensor: neutral intent
- 2 sensors: warning intent (yellow)
- 3+ sensors: success intent (green)

### Key Differences from Legacy Frontend

| Aspect | Legacy (`src/frontend/`) | React (`src/frontend-react/`) |
|--------|--------------------------|-------------------------------|
| Language | Vanilla ES6 JS | TypeScript |
| 3D engine | Cesium v1.104 (CDN) | Cesium v1.114 (npm) |
| State | Mutable shared object | Zustand store |
| Build | None | Vite |
| UI kit | Custom CSS | Blueprint.js |
| Charts | None | ECharts |
| Verification UI | None | VerificationStepper, FusionBar, SensorBadge |

---

## Legacy Frontend (Reference Only)

> The legacy frontend at `src/frontend/` is kept for reference. All active development uses the React frontend above.

## Table of Contents (Legacy)

1. [Architecture Overview](#architecture-overview)
2. [Module Reference](#module-reference)
   - [state.js — Shared Application State](#statejs--shared-application-state)
   - [app.js — Entry Point](#appjs--entry-point)
   - [map.js — Cesium Viewer](#mapjs--cesium-viewer)
   - [drones.js — UAV 3D Entities](#dronesjs--uav-3d-entities)
   - [dronelist.js — Drone Card Sidebar](#dronelistjs--drone-card-sidebar)
   - [dronecam.js — Drone Camera PIP](#dronecamjs--drone-camera-pip)
   - [enemies.js — ENEMIES Tab](#enemiesjs--enemies-tab)
   - [strikeboard.js — HITL Strike Board](#strikeboard--hitl-strike-board)
   - [sidebar.js — Tab Navigation](#sidebarjs--tab-navigation)
   - [theater.js — Theater Selector](#theaterjs--theater-selector)
   - [websocket.js — WebSocket Client](#websocketjs--websocket-client)
   - [rangerings.js — Sensor Range Rings](#rangeringsjs--sensor-range-rings)
   - [mapclicks.js — Map Click Handlers](#mapclicksjs--map-click-handlers)
   - [detailmap.js — Detail Waypoint Modal](#detailmapjs--detail-waypoint-modal)
   - [serve.py — Dev HTTP Server](#servepy--dev-http-server)
3. [UI Layout](#ui-layout)
4. [Color Scheme](#color-scheme)
5. [WebSocket Protocol](#websocket-protocol)
6. [UAV Mode Reference](#uav-mode-reference)
7. [Target Type Reference](#target-type-reference)
8. [Kill Chain State Progression](#kill-chain-state-progression)

---

## Architecture Overview

The Palantir frontend is a **vanilla ES6 JavaScript** application with no build step and no npm bundling. It uses **Cesium JS v1.104** (loaded from CDN) for 3D WGS-84 geospatial visualization.

| Property | Detail |
|----------|--------|
| Language | ES6 JavaScript (modules) |
| 3D Engine | Cesium JS v1.104 (CDN) |
| Build step | None |
| Bundler | None |
| Dev server | `serve.py` (custom Python, no-cache) |
| Entry point | `app.js` |
| Module system | ES6 `import` / `export` |

Each feature lives in its own `.js` file. The entry point (`app.js`) initializes all modules and wires the WebSocket state stream to every UI subsystem.

### File Structure

```
src/frontend/
  index.html          HTML shell
  app.js              Entry point — init and wiring
  state.js            Shared mutable state object
  map.js              Cesium viewer setup, zones, camera
  drones.js           UAV 3D entities and lock indicators
  dronelist.js        Drone card sidebar (ASSETS tab)
  dronecam.js         Synthetic drone camera PIP
  enemies.js          Enemy card list (ENEMIES tab)
  strikeboard.js      HITL strike board overlay
  sidebar.js          Tab navigation
  theater.js          Theater selector dropdown
  websocket.js        WebSocket client and event dispatch
  rangerings.js       Sensor range ring overlays
  mapclicks.js        Map click handlers (waypoints, spikes)
  detailmap.js        Detail waypoint modal
  style.css           Stylesheet (dark theme)
  serve.py            No-cache dev HTTP server
```

---

## Module Reference

### state.js — Shared Application State

Exports a single mutable `state` object that acts as the application-wide store. All modules import and read/write from this object directly.

| Property | Type | Description |
|----------|------|-------------|
| `viewer` | `Cesium.Viewer` | The Cesium viewer instance |
| `ws` | `WebSocket` | Active WebSocket connection |
| `selectedDroneId` | `number \| null` | Currently selected UAV ID |
| `selectedTargetId` | `number \| null` | Currently selected target ID |
| `trackedDroneEntity` | `Cesium.Entity \| null` | Cesium entity the camera is tracking |
| `macroTrackedId` | `number \| null` | ID for macro (overhead) tracking |
| `isMacroTrackingReady` | `boolean` | Whether macro tracking state is ready |
| `lastDronePosition` | `Cartesian3 \| null` | Last known position of tracked drone |
| `isSettingWaypoint` | `boolean` | Whether waypoint placement mode is active |
| `showAllWaypoints` | `boolean` | Toggle for waypoint visibility on the map |
| `gridVisState` | `number (0-2)` | Zone grid visibility state (off / borders / filled) |
| `zonesPrimitive` | `Cesium.Primitive \| null` | Cesium primitive for zone fill rendering |
| `zoneBordersPrimitive` | `Cesium.Primitive \| null` | Cesium primitive for zone border rendering |
| `droneWaypoints` | `Map<number, Cartesian3>` | Map of drone ID to waypoint positions |
| `droneCamVisible` | `boolean` | Whether the drone camera PIP is visible |
| `theaterBounds` | `object \| null` | Current theater bounds (used by global view button) |

### app.js — Entry Point

Runs on `DOMContentLoaded`. Initialization sequence:

1. **`initMap()`** — creates the Cesium viewer
2. **`initCompass()`**, **`initMouseTracking()`**, **`initMacroTracking()`** — map utility overlays
3. **Initialize UI modules** — sidebar, assistant feed, detail map, strike board, theater selector, drone cam
4. **Wire `ws:state` event handler** — the main render loop that fires on every backend tick:
   - Update zone grid primitives
   - Update flow lines
   - Update drone entities and drone card list
   - Update target entities and enemy card list
   - Update lock indicator lines
   - Update drone camera feed
   - Detect theater change and call `flyToTheater(bounds)` when the theater switches
   - Show/hide demo banner based on `demo_mode` flag in the state payload
5. **`initMapClickHandlers()`**, **`connectWebSocket()`** — final wiring

The module tracks a `currentTheater` variable internally to detect when the backend switches theaters, triggering an automatic camera fly-to.

### map.js — Cesium Viewer

Responsible for all Cesium viewer setup and camera operations.

| Function | Description |
|----------|-------------|
| `initMap()` | Creates a dark-themed Cesium viewer with `requestRenderMode` enabled for performance. Disables default UI widgets where appropriate. |
| `initOrUpdateZonesPrimitive(zones)` | Renders the zone grid as Cesium geometry primitives. Handles creation and update of both fill and border primitives stored in `state`. |
| `flyToTheater(bounds)` | Calculates the center lat/lon and appropriate altitude from the theater bounds object, then smoothly flies the camera to that position. |
| `initCompass()` | Displays a compass heading indicator that updates with camera orientation. |
| `initMouseTracking()` | Shows cursor lat/lon coordinates as the mouse moves over the globe. |
| `initMacroTracking()` | Enables an overhead (macro) drone tracking camera mode — follows a UAV from above at a fixed altitude offset. |

### drones.js — UAV 3D Entities

Manages Cesium point entities representing UAVs on the 3D map.

**`updateDrones(uavs)`** — Creates or updates a Cesium point entity for each UAV in the state payload. Each entity is color-coded by the UAV's current mode (see [UAV Mode Reference](#uav-mode-reference)).

**`updateLockIndicators(uavs, targetEntities)`** — Draws polyline lock lines from a UAV to its assigned target when the UAV is in `PAINT` or `INTERCEPT` mode. Lines are removed when the UAV exits those modes.

**`triggerDroneSelection(entity, cameraMode)`** — Dispatches a `drone:selected` CustomEvent, manages camera tracking state, and transitions the camera to follow the selected entity.

### dronelist.js — Drone Card Sidebar

Renders interactive drone cards in the **ASSETS** tab.

**`updateDroneList(uavs)`** — Builds a card for each UAV. Card contents depend on selection state:

**Collapsed card** (not selected):
- UAV ID label
- Mode badge (color-coded)
- Target association (if any)

**Expanded card** (selected/tracked):
- All collapsed info, plus:
- **Stats block:** altitude, sensor type, tracking target, lat/lon coordinates
- **Mode command buttons:** SEARCH, FOLLOW, PAINT, INTERCEPT
- **Utility buttons:** Set Waypoint, Range Rings, Detail Waypoint

**Interaction model:**

| Action | Result |
|--------|--------|
| Single click | Macro (overhead) camera view of the UAV |
| Double click | Third-person camera view following the UAV |

**Mode button behavior:**

| Button | Target required? | Notes |
|--------|-----------------|-------|
| SEARCH | No | Releases any current target, enters circular loiter |
| FOLLOW | Yes | If no target selected, button shows "Pick target" with pulse animation |
| PAINT | Yes | Same "Pick target" prompt if no target |
| INTERCEPT | Yes | Same "Pick target" prompt if no target |

**MODE_STYLES map** (used for badge colors throughout the UI):

```javascript
IDLE:          { color: '#3b82f6', label: 'IDLE' }
SEARCH:        { color: '#22c55e', label: 'SEARCH' }
FOLLOW:        { color: '#a78bfa', label: 'FOLLOW' }
PAINT:         { color: '#ef4444', label: 'PAINT' }
INTERCEPT:     { color: '#ff6400', label: 'INTERCEPT' }
REPOSITIONING: { color: '#eab308', label: 'TRANSIT' }
RTB:           { color: '#64748b', label: 'RTB' }
```

### dronecam.js — Drone Camera PIP

A canvas-based 400x300 synthetic sensor feed displayed as a Picture-in-Picture overlay in the bottom-left corner of the screen.

**Visibility:** Appears when a drone is selected (listens for `drone:selected` event). Has a close button to hide.

**Rendering pipeline** (runs via `requestAnimationFrame`):

1. **Grid background** — dark sensor-style grid overlay
2. **Target projection** — uses haversine distance and bearing calculations to project target positions from 3D world space into 2D screen coordinates relative to the drone's heading
3. **Target shapes** — 10 unique shape/color combinations, one per target type (see [Target Type Reference](#target-type-reference))
4. **Corner brackets** — tactical bracket overlay framing the viewport
5. **HUD telemetry** — text overlay showing drone and target information

**Sensor parameters:**

| Parameter | Value |
|-----------|-------|
| Canvas size | 400 x 300 pixels |
| Horizontal FOV | 60 degrees |
| Sensor range | 15 km |

**Tracking overlays:**

| Overlay | When shown | Description |
|---------|-----------|-------------|
| Reticle crosshair | FOLLOW, PAINT, or INTERCEPT mode | Centered targeting crosshair |
| Lock box | PAINT mode only | Pulsing red box around the tracked target |

**HUD information:**

- UAV ID, altitude, heading
- Mode (color-coded to match MODE_STYLES)
- Lat/lon coordinates
- Tracked target info and lock status
- **Target info panel** (bottom-left of PIP): target type/ID, state, range/bearing, confidence percentage

**TARGET_STYLES** (shape and color per target type):

| Target Type | Shape | Color |
|-------------|-------|-------|
| SAM | Diamond | Red |
| TEL | Triangle | Orange |
| TRUCK | Rectangle | White |
| CP | Square | Orange |
| MANPADS | Circle | Purple |
| RADAR | Hexagon | Cyan |
| C2_NODE | Diamond | Yellow |
| LOGISTICS | Rectangle | Gray |
| ARTILLERY | Triangle | Red |
| APC | Square | Green |

### strikeboard.js — HITL Strike Board

The two-gate Human-in-the-Loop approval UI, rendered as an overlay panel when nominations are pending.

**Gate 1 — Nomination Approval:**
- Displays target information (type, ID, location, state)
- Shows recommending agent and priority score
- **Approve** / **Reject** buttons

**Gate 2 — COA Authorization:**
- Displays the engagement plan (Course of Action)
- Shows recommended UAV for the engagement
- Risk assessment summary
- **Authorize** / **Reject** buttons

Both gates send WebSocket actions back to the backend (`approve_nomination`, `reject_nomination`, `authorize_coa`).

### sidebar.js — Tab Navigation

Manages the three-tab navigation in the left sidebar:

| Tab | Content |
|-----|---------|
| **MISSION** | Mission overview, tactical assistant messages |
| **ASSETS** | Drone card list (rendered by `dronelist.js`) |
| **ENEMIES** | Enemy target list (rendered by `enemies.js`) |

Also provides a **Global View** button that uses `state.theaterBounds` to fly the camera to a position that shows the entire theater.

### theater.js — Theater Selector

Dropdown UI for switching between operational theaters.

**Initialization:** Populates the dropdown by calling `GET /api/theaters` on the backend.

**On change:** Sends `POST /api/theater` with the selected theater name. This triggers a full simulation reset on the backend. The backend's next state payload includes updated theater bounds, which `app.js` detects as a theater change, triggering `flyToTheater(bounds)` to recenter the camera.

Available theaters (configured via YAML files in `theaters/`):
- Romania
- South China Sea
- Baltic

### websocket.js — WebSocket Client

Manages the WebSocket connection to the backend.

**Connection:** Connects to `ws://localhost:8000/ws`. On open, sends a registration message:

```json
{ "client_type": "DASHBOARD" }
```

**Inbound events** (dispatched as `CustomEvent` on `window`):

| Event name | Payload | Description |
|------------|---------|-------------|
| `ws:state` | Full simulation state | Fired every tick (~10Hz). Contains drones, targets, zones, theater bounds, demo mode flag |
| `ws:assistant` | Assistant message | Tactical AIP Assistant messages |
| `ws:hitl` | HITL payload | Strike board nominations and COA requests |
| `ws:sitrep` | Situation report | Periodic situation summaries |

**Outbound actions** (sent as JSON via `ws.send()`):

| Action | Fields | Description |
|--------|--------|-------------|
| `scan_area` | `drone_id` | Send drone to search mode |
| `follow_target` | `drone_id`, `target_id` | Assign drone to follow a target |
| `paint_target` | `drone_id`, `target_id` | Assign drone to paint (laser lock) a target |
| `intercept_target` | `drone_id`, `target_id` | Assign drone to intercept a target |
| `cancel_track` | `drone_id` | Release drone from target tracking |
| `move_drone` | `drone_id`, `lat`, `lon` | Set a waypoint for a drone |
| `spike` | `lat`, `lon` | Mark a location for investigation |
| `approve_nomination` | `target_id` | Gate 1 approval |
| `reject_nomination` | `target_id` | Gate 1 rejection |
| `authorize_coa` | `coa_id` | Gate 2 authorization |

### rangerings.js — Sensor Range Rings

Provides toggle-able per-drone sensor range ring overlays on the Cesium map. Activated via a button in the expanded drone card. Renders as translucent circle primitives centered on the UAV's current position.

### mapclicks.js — Map Click Handlers

Handles two types of map click interactions:

1. **Waypoint placement** — when `state.isSettingWaypoint` is true, clicking the map sets a waypoint for the selected drone and sends a `move_drone` action via WebSocket.
2. **Spike placement** — marks a target location for investigation, sends a `spike` action.

### detailmap.js — Detail Waypoint Modal

A modal dialog for precise waypoint placement. Provides text input fields for lat/lon coordinates as an alternative to clicking on the map. Useful when exact coordinates are known.

### serve.py — Dev HTTP Server

A custom Python HTTP server that replaces `python3 -m http.server`. Adds `Cache-Control: no-store` headers to all responses to prevent stale browser cache issues during development.

```bash
cd src/frontend && python3 serve.py 3000
```

---

## UI Layout

```
+---------------------------------------------------------------+
|  [Theater Selector]   [Env Controls]   [Demo Banner]          |
+----------+----------------------------------------------------+
|          |                                                    |
|  LEFT    |              CESIUM 3D MAP                         |
| SIDEBAR  |              (main area)                           |
|          |                                                    |
| MISSION  |                                                    |
| ASSETS   |                              +------------------+  |
| ENEMIES  |                              | Tactical AIP     |  |
|          |                              | Assistant Feed   |  |
|          |  +------------------+        | (bottom-right)   |  |
|          |  | Drone Camera PIP |        +------------------+  |
|          |  | (bottom-left)    |                              |
+----------+--+------------------+------------------------------+
|                  [Strike Board Overlay — when active]         |
+---------------------------------------------------------------+
```

| Region | Position | Content |
|--------|----------|---------|
| Left sidebar | Left edge, full height | Tab navigation (MISSION / ASSETS / ENEMIES) with scrollable content |
| Main area | Center | Cesium 3D globe with UAV and target entities |
| Assistant feed | Bottom-right | Tactical AIP Assistant messages (scrolling) |
| Drone Camera PIP | Bottom-left | 400x300 synthetic sensor feed (when drone selected) |
| Top bar | Top | Theater selector dropdown, environment controls, demo mode banner |
| Strike board | Overlay | HITL two-gate approval panel (when nominations pending) |

---

## Color Scheme

The frontend uses a consistent dark theme across all modules.

### UAV Mode Colors

These colors are used consistently in drone entities on the map, drone cards in the sidebar, drone camera HUD, and lock indicator lines.

| Mode | Hex | Visual |
|------|-----|--------|
| IDLE | `#3b82f6` | Blue |
| SEARCH | `#22c55e` | Green |
| FOLLOW | `#a78bfa` | Purple |
| PAINT | `#ef4444` | Red |
| INTERCEPT | `#ff6400` | Orange |
| REPOSITIONING | `#eab308` | Yellow |
| RTB | `#64748b` | Slate gray |

### Target Type Colors

Used in drone camera PIP target rendering and enemy card type badges.

| Type | Color |
|------|-------|
| SAM | Red |
| TEL | Orange |
| TRUCK | White |
| CP | Orange |
| MANPADS | Purple |
| RADAR | Cyan |
| C2_NODE | Yellow |
| LOGISTICS | Gray |
| ARTILLERY | Red |
| APC | Green |

### Kill Chain State Colors

Used in enemy card state badges to show progression through the F2T2EA kill chain.

| State | Color | Hex |
|-------|-------|-----|
| DETECTED | Yellow | — |
| IDENTIFIED | Amber | — |
| TRACKED | Orange | — |
| NOMINATED | Red | — |
| ENGAGED | Dark red | — |
| NEUTRALIZED | Gray | — |

---

## WebSocket Protocol

The frontend communicates with the FastAPI backend over a single WebSocket connection at `ws://localhost:8000/ws`.

### Connection Lifecycle

1. Frontend opens WebSocket connection
2. Sends registration: `{ "client_type": "DASHBOARD" }`
3. Backend begins streaming state at ~10Hz
4. Frontend dispatches inbound messages as `CustomEvent` on `window`
5. Frontend sends user actions as JSON

### State Payload Structure

Each `ws:state` event contains the full simulation snapshot:

- **Drone positions** — array of UAV objects (id, lat, lon, alt, heading, mode, target_id, fuel, sensor)
- **Target positions** — array of target objects (id, type, lat, lon, state, concealed, confidence)
- **Grid zone states** — zone grid data for primitive rendering
- **Theater bounds** — bounding box for the active theater
- **Demo mode flag** — `demo_mode: true` when backend is in auto-pilot mode
- **Flow lines** — tactical flow line data
- **Tactical assistant messages** — AI agent recommendations

---

## UAV Mode Reference

| Mode | Behavior | Turn Rate | Target Required | Sim Details |
|------|----------|-----------|-----------------|-------------|
| IDLE | Hold position | Normal | No | Stationary loiter |
| SEARCH | Circular loiter over zone | MAX_TURN_RATE | No | Circular pattern at zone center |
| FOLLOW | Loose orbit tracking target | Normal | Yes | ~2km orbit distance |
| PAINT | Tight orbit with laser lock | Normal | Yes | ~1km orbit, target state becomes LOCKED |
| INTERCEPT | Direct approach at 1.5x speed | Normal | Yes | ~300m danger-close orbit, target state becomes LOCKED |
| REPOSITIONING | Zone rebalance | 3x turn rate | No | Auto-assigned by zone imbalance logic |
| RTB | Return to base | Normal | No | Triggered by low fuel |

All tracking modes use the `_turn_toward()` function for smooth heading changes via gradual arcs (fixed-wing physics).

---

## Target Type Reference

The simulation supports 10 target types, each with a unique visual representation in the drone camera PIP:

| Type | Shape | Color | Description |
|------|-------|-------|-------------|
| SAM | Diamond | Red | Surface-to-Air Missile system |
| TEL | Triangle | Orange | Transporter Erector Launcher |
| TRUCK | Rectangle | White | Supply/transport vehicle |
| CP | Square | Orange | Command Post |
| MANPADS | Circle | Purple | Man-Portable Air-Defense System |
| RADAR | Hexagon | Cyan | Radar installation |
| C2_NODE | Diamond | Yellow | Command and Control node |
| LOGISTICS | Rectangle | Gray | Logistics vehicle/depot |
| ARTILLERY | Triangle | Red | Artillery emplacement |
| APC | Square | Green | Armored Personnel Carrier |

---

## Kill Chain State Progression

Targets progress through the F2T2EA kill chain. Each state corresponds to a visual color in the ENEMIES tab:

```
DETECTED (yellow)
    |
IDENTIFIED (amber)
    |
TRACKED (orange)
    |
NOMINATED (red)        <-- Gate 1: HITL approval required
    |
ENGAGED (dark red)     <-- Gate 2: COA authorization required
    |
NEUTRALIZED (gray)     <-- Terminal state
```

In **demo mode** (`--demo` flag), the backend auto-pilot advances targets through this chain automatically, approving nominations and authorizing COAs without human input.
