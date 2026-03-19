# Report 2 — UI Overhaul: Workspace Shell, Timeline, & Controls
**Date:** 2026-03-17
**Scope:** Frontend UI restructuring — layout system, timeline drawer, camera controls, toolbar cleanup
**Files Modified:** 8 files across `frontend/`

---

## 1. Executive Summary

This update transforms the dashboard UI from a rigid sidebar+bottom-panel layout into a modern floating-overlay architecture. The left sidebar now hovers over the full-width Cesium map with visible gaps. The bottom timeline panel has been replaced with a minimizable pill/drawer system. Camera controls are permanently accessible in a top-right pill. The top toolbar has been decluttered by removing the LIVE/REPLAY dropdown and moving scrub controls into the timeline drawer.

---

## 2. Changes Made

### 2.1 Left Sidebar — Floating Overlay with Gaps

**Files:** `workspace-shell.js`, `workspace-shell.css`

**Before:** The left sidebar was a flex child of `#ws-body`, pushing the center (map) region to the right. The map only occupied the remaining space.

**After:** The left sidebar uses `position: absolute` and floats over the map with 8px gaps on all sides (top, left, bottom). The map now renders at full viewport width underneath.

```css
#ws-region-left {
    position: absolute;
    top: 8px;
    left: 8px;
    bottom: 8px;
    width: var(--ws-left-width, 380px);
    background: rgba(10, 15, 25, 0.85);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(100, 116, 139, 0.3);
    border-radius: 6px;
    z-index: 80;
}
```

The left splitter is also absolutely positioned to track the sidebar edge:
```css
#ws-splitter-left {
    position: absolute;
    top: 8px;
    bottom: 8px;
    left: calc(var(--ws-left-width, 380px) + 8px);
}
```

### 2.2 Left Sidebar Tab Bar — Compact Square Icons

**Files:** `workspace-shell.js`, `workspace-shell.css`

**Before:** Tabs used full text labels, taking significant horizontal space.

**After:** Each tab is a 32x32px square button showing only an icon letter. The active tab expands to show its full label. Tabs are horizontally scrollable if they overflow.

**Tab definitions in `workspace-shell.js`:**
```javascript
const leftTabs = [
    { id: 'missions',  label: 'MISSION', icon: 'M', contentId: 'tab-mission' },
    { id: 'assets',    label: 'ASSETS',  icon: 'A', contentId: 'tab-drones' },
    { id: 'inspector', label: 'OPS',     icon: 'O', contentId: 'tab-ops' },
    { id: 'alerts',    label: 'ALERTS',  icon: '!', contentId: 'tab-alerts' },
    { id: 'macrogrid', label: 'GRID',    icon: 'G', contentId: 'tab-grid' },
    { id: 'commands',  label: 'CMDS',    icon: 'C', contentId: 'tab-commands' },
];
```

**CSS behavior:**
```css
.ws-tab-btn { width: 32px; height: 32px; }
.ws-tab-btn.ws-active { width: auto; }  /* expands for label */
.ws-tab-btn .ws-tab-label { display: none; }
.ws-tab-btn.ws-active .ws-tab-label { display: inline; }
```

### 2.3 ALERTS & COMMANDS Tabs — Moved Back to Left Sidebar

**Files:** `workspace-shell.js`

**Before:** ALERTS and COMMANDS were in the bottom panel as separate tabs alongside the timeline.

**After:** Both tabs are now in the left sidebar tab bar (icons `!` and `C`), alongside Mission, Assets, Ops, and Grid. The bottom region is exclusively used for the timeline drawer.

### 2.4 Timeline — Pill/Drawer System

**Files:** `workspace-shell.js`, `workspace-shell.css`

**Before:** The timeline was a permanent bottom panel with a splitter, always visible and taking up space.

**After:** The timeline is a two-part floating system:

#### Timeline Pill (always visible)
- Small rectangular pill at the bottom-right of the screen
- Displays live date and time: `17 MARCH 2026 | 05:35:10`
- Updates every second via `setInterval`
- Clicking toggles the timeline drawer open/closed
- When drawer is open, pill slides up to sit above the drawer

```javascript
function _updatePillClock() {
    const now = new Date();
    const day = now.getDate();
    const monthName = now.toLocaleString('en-US', { month: 'long' });
    const year = now.getFullYear();
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    timelinePill.innerHTML = `<span class="ws-date-day">${day}</span> ...`;
}
_updatePillClock();
setInterval(_updatePillClock, 1000);
```

#### Timeline Drawer (expandable)
- Slides up from the bottom with 8px gaps on all sides
- Respects left sidebar: `left: calc(var(--ws-left-width, 380px) + 8px + 4px + 8px)`
- Default height stored in `_timelineHeight` (percentage of viewport)
- Vertically resizable via drag handle at top of drawer
- Height persists across minimize/expand cycles and page reloads (via `LayoutPersistence`)
- Collapsed state: `height: 0; background: transparent; border: none; pointer-events: none;` (no visible sliver)
- Open state adds `.ws-timeline-drawer-open` class with glass-morphism background

```css
.ws-timeline-drawer {
    position: absolute;
    z-index: 90;
    bottom: 8px;
    right: 8px;
    left: calc(var(--ws-left-width, 380px) + 8px + 4px + 8px);
    height: 0;
    background: transparent;
    border: none;
    pointer-events: none;
}

.ws-timeline-drawer.ws-timeline-drawer-open {
    background: rgba(10, 15, 25, 0.95);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(100, 116, 139, 0.3);
    pointer-events: auto;
}
```

### 2.5 Timeline Content — Selected UAV Only

**Files:** `panels/timeline-panel.js`

**Before:** The timeline rendered swim lanes for all assets simultaneously.

**After:** Only the currently selected UAV is shown. If no UAV is selected, a centered message reads "Select a UAV to view its timeline."

```javascript
const selectedAssetId = AppState.state.selection.assetId;
const allAssets = Array.from(AppState.state.assets.values());
const assets = selectedAssetId
    ? allAssets.filter(a => a.id === selectedAssetId)
    : [];
if (assets.length === 0) {
    ctx.fillText('Select a UAV to view its timeline', W / 2, H / 2);
    return;
}
```

The timeline re-renders whenever `selection.changed` fires:
```javascript
AppState.subscribe('selection.changed', render);
```

### 2.6 Drone Selection — AppState Bridge

**Files:** `map-tool-controller.js`

**Before:** Clicking a drone only triggered Cesium camera tracking. No other panels knew which drone was selected.

**After:** Drone selection is bridged to `AppState` so the timeline, inspector, and other panels can react:

```javascript
function _triggerDroneSelection(entity, viewMode) {
    _trackedDroneEntity = entity;
    if (entity && entity.id && typeof AppState !== 'undefined') {
        const assetId = entity.id.replace('uav_', 'ast_');
        AppState.select('asset', assetId);
    }
    // ... camera logic
}
```

On deselect:
```javascript
function _deselectDrone() {
    // ...
    AppState.select('asset', null);
}
```

**Asset ID mapping:** Cesium entities use `uav_0` format, AppState uses `ast_0` format. The bridge performs `entity.id.replace('uav_', 'ast_')`.

### 2.7 Camera Controls — Permanent Top-Right Pill

**Files:** `index.html`, `style.css`, `map-tool-controller.js`

**Before:** Camera controls (global view, disconnect) were inside `#cesiumContainer` and toggled visible only when tracking a drone.

**After:** Camera controls are permanently visible in a floating pill at the top-right corner, always accessible regardless of tracking state. Three buttons:

| Button | Symbol | Function |
|--------|--------|----------|
| Global View | `🌐` | Flies camera back to default overview position |
| Disconnect | `✖` | Stops tracking the selected drone |
| Zoom Lock | `⊡` / `⊞` | Toggles whether selecting a drone zooms the camera to it |

```css
.camera-controls {
    position: absolute;
    top: 56px;
    right: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    z-index: 100;
    background: rgba(10, 15, 25, 0.85);
    border: 1px solid rgba(100, 116, 139, 0.3);
    border-radius: 6px;
    padding: 4px;
}
```

The zoom-lock toggle:
```javascript
lockBtn.addEventListener('click', () => {
    _zoomOnSelect = !_zoomOnSelect;
    lockBtn.textContent = _zoomOnSelect ? '⊡' : '⊞';
    lockBtn.style.opacity = _zoomOnSelect ? '0.5' : '1';
});
```

When `_zoomOnSelect` is false, `_triggerDroneSelection()` skips all `flyTo()` calls:
```javascript
if (!_zoomOnSelect) return;
```

### 2.8 Top Toolbar — Decluttered

**Files:** `index.html`, `workspace-shell.js`, `panels/toolbar.js`

**Before:** The top toolbar contained: LIVE/REPLAY dropdown, "Events: Connected/Disconnected" status, scrub label, and "RETURN TO LIVE" button.

**After:**
- **Removed:** LIVE/REPLAY dropdown (`#timeModeSelect`)
- **Removed:** Events connection status (`#eventConnStatus`)
- **Moved:** Scrub label and "RETURN TO LIVE" button into the timeline drawer header
- **Remaining in top bar:** "SYSTEM DASHBOARD" title + tool palette (SELECT / WAYPOINT)

`toolbar.js` now exposes `getControlsElement()` which returns a container with the scrub controls. This is appended to `.ws-timeline-drawer-header` during initialization in `app.js`:

```javascript
if (typeof Toolbar !== 'undefined') {
    Toolbar.init();
    const drawerHeader = document.querySelector('.ws-timeline-drawer-header');
    const controls = Toolbar.getControlsElement();
    if (drawerHeader && controls) drawerHeader.appendChild(controls);
}
```

### 2.9 Timeline "TIMELINE" Title — Removed

**Files:** `index.html`

The `<h3>Timeline</h3>` element inside `#timelinePanel` was removed. The drawer now shows only the controls header and the canvas — no redundant title.

### 2.10 Grid Layout — Simplified to 2 Rows

**Files:** `workspace-shell.js`, `workspace-shell.css`

**Before:** CSS Grid with 4 rows: `48px 1fr 4px ${bottomHeight}px` (top, body, bottom-splitter, bottom-panel).

**After:** CSS Grid with 2 rows: `48px 1fr` (top toolbar, body). The timeline is a floating overlay, not a grid row.

```css
#workspace-shell {
    display: grid;
    grid-template-rows: 48px 1fr;
    width: 100vw;
    height: 100vh;
    position: relative;
}
```

---

## 3. File Change Summary

| File | Changes |
|------|---------|
| `frontend/index.html` | Removed LIVE/REPLAY dropdown, events status, Timeline h3 title. Added zoom-lock button. Cache-bust all scripts to `?v=11` |
| `frontend/workspace-shell.js` | Left pane absolute positioning, compact tab bar, timeline pill with live clock, timeline drawer with resize handle and header, removed bottom grid row, removed toolbar container from top bar |
| `frontend/workspace-shell.css` | Left pane floating styles, tab icon styles, timeline pill/drawer styles, drawer header styles, date typography with separator and time |
| `frontend/style.css` | Camera controls repositioned to top-right, 32px square buttons |
| `frontend/map-tool-controller.js` | AppState bridge for drone selection, zoom-lock toggle (`⊡`/`⊞`), removed camera controls display toggling |
| `frontend/panels/timeline-panel.js` | Filtered to selected UAV only, subscribed to `selection.changed` |
| `frontend/panels/toolbar.js` | Rewritten — scrub controls now returned via `getControlsElement()` for placement in timeline drawer |
| `frontend/app.js` | Wires toolbar controls into timeline drawer header after init |

---

## 4. Layout Persistence Schema

The `LayoutPersistence` module saves to `localStorage` key `ams.workspace.layout`:

```json
{
    "version": 1,
    "left": {
        "width": 380,
        "collapsed": false,
        "activeTab": "missions"
    },
    "right": {
        "width": 340,
        "visible": false
    },
    "bottom": {
        "timelineExpanded": false,
        "timelineHeight": 30
    }
}
```

`timelineHeight` is stored as a percentage of viewport height (vh).

---

## 5. Z-Index Stack

| Z-Index | Element |
|---------|---------|
| 100 | Top toolbar (`#ws-region-top`), Camera controls (`.camera-controls`) |
| 95 | Timeline pill (`.ws-timeline-pill`) |
| 90 | Timeline drawer (`.ws-timeline-drawer`) |
| 85 | Splitters (`.ws-splitter`) |
| 80 | Left sidebar (`#ws-region-left`) |

---

## 6. Known Behaviors & Edge Cases

1. **Browser caching:** All modified scripts use `?v=11` query params. When making further changes, increment this version number.
2. **Asset ID mismatch:** Cesium entities are `uav_N`, AppState assets are `ast_N`. The bridge in `map-tool-controller.js` handles conversion.
3. **Timeline drawer collapsed state:** Uses `background: transparent; border: none; pointer-events: none;` to prevent any visible sliver at height 0.
4. **Pill position sync:** `_updatePillPosition()` is called on expand, collapse, and during resize drag to keep the pill 8px above the drawer top edge.
5. **Zoom-lock default:** `_zoomOnSelect = true` by default (symbol `⊡`). When disabled (symbol `⊞`), clicking a drone in the list or on the map selects it without flying the camera.

---

## 7. Architecture Diagram (Post-Update)

```
┌─────────────────────────────────────────────────────────┐
│  TOP TOOLBAR  [System Dashboard]  [SELECT] [WAYPOINT]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──LEFT PANE──┐                        ┌─CAM CTRL─┐   │
│  │ [M][A][O]   │                        │   🌐     │   │
│  │ [!][G][C]   │     CESIUM 3D MAP      │   ✖      │   │
│  │             │     (full width)        │   ⊡      │   │
│  │  Tab Content│                        └──────────┘   │
│  │             │                                        │
│  │             │                                        │
│  │             │              ┌──DATE PILL──┐           │
│  │             │              │17 MAR | time│           │
│  └─────────────┘              └─────────────┘           │
│                 ┌──TIMELINE DRAWER (when open)──┐       │
│                 │ [scrub controls]               │       │
│                 │ [canvas: selected UAV lanes]   │       │
│                 └────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 8. What Was NOT Changed

- **Backend:** No changes to FastAPI, simulation, services, or database
- **State management:** `state.js` unchanged
- **API client / WS client:** Unchanged
- **Pane registry / definitions:** Unchanged (these are metadata; actual layout is handled by workspace-shell)
- **Inspector, Mission, Alerts, Macrogrid panels:** Content logic unchanged
- **3D rendering logic in `app.js`:** UAV entities, zones, flow lines, waypoints all unchanged
- **Desktop wrapper (`start.py`):** Unchanged

---

## 9. Post-Session Fixes: Backend Errors & Launcher

### 9.1 Backend Bug Fixes

**`_event_clients` UnboundLocalError — `backend/app/api/ws.py`**

The `_broadcast_event` function used `_event_clients -= dead` (an assignment), which made Python treat `_event_clients` as a local variable, causing `UnboundLocalError` on the `if not _event_clients:` check above it. Fixed by adding `global _event_clients`.

**`Set changed size during iteration` — `backend/app/api/ws.py`**

When a WebSocket disconnected, the `finally` block called `_event_clients.discard(ws)` while `_broadcast_event` was iterating over the same set. Fixed by iterating over `list(_event_clients)` (a snapshot copy) instead of the live set.

**`KeyError: 'source_id'` — `backend/app/services/macrogrid_service.py`**

`main.py` was passing `sim.active_flows` to `process_dispatches()`, but `active_flows` contains `{"source": coord, "target": coord}` dicts (for rendering flow lines). The macrogrid service expects `{"source_id": zone_tuple, "target_id": zone_tuple, ...}` dicts from `grid.calculate_macro_flow()`. Fixed by:
- Adding `sim.last_dispatches` to store raw dispatch dicts from `calculate_macro_flow()`
- Passing `sim.last_dispatches` instead of `sim.active_flows` in `main.py`

**`reload=True` removed — `backend/main.py`**

Uvicorn's `reload=True` spawns a file-watcher child process that interfered with the launcher's subprocess management and made cleanup unreliable. Removed for production use.

### 9.2 Launcher Rewrite — `start.py`

**Auto-kill stale processes:** Instead of erroring when a port is busy, uses `netstat` + `taskkill` to free the port automatically. Only errors if cleanup fails.

**Streamed backend output:** Backend stdout now prints in real-time prefixed with `[BACKEND]` / `[FRONTEND]` via background threads, so errors are visible immediately instead of silently swallowed.

**Increased health timeout:** Backend health check timeout raised from 15s to 20s.

**PyQt5 replaced with browser launch:** PyQt5 WebEngine could not reliably render the Cesium globe (WebGL/GPU blocklist issues). Replaced with `webbrowser.open()` which opens the app in the user's default browser. The script stays alive with Ctrl+C to shut down servers.

### 9.3 Files Changed

| File | Changes |
|------|---------|
| `backend/app/api/ws.py` | Added `global _event_clients`, iterate over `list()` copy |
| `backend/main.py` | Removed `reload=True`, pass `sim.last_dispatches` instead of `sim.active_flows` |
| `backend/sim.py` | Added `self.last_dispatches` storing raw dispatch dicts from `calculate_macro_flow()` |
| `start.py` | Auto-kill stale ports, streamed output, replaced PyQt5 with `webbrowser.open()` |

---

## 10. UNFIXED — Globe Rendering vs Performance Trade-off

**Status: UNRESOLVED**

### The Problem

Cesium's `requestRenderMode` creates a conflict between globe detail and simulation performance:

| Setting | Globe | Performance |
|---------|-------|-------------|
| `requestRenderMode = false` | Globe loads and streams tiles correctly at full detail | Slow — continuous 60fps rendering burns CPU/GPU even when idle |
| `requestRenderMode = true` + `maximumRenderTimeChange = Infinity` | Globe tiles do not stream in (no re-renders to trigger tile requests) | Fast — only renders on explicit `requestRender()` calls from data loop |
| `requestRenderMode = true` + `maximumRenderTimeChange = 0.5` | Globe partially loads but detail levels don't update | Moderate performance |
| `requestRenderMode = true` + tile kick (current) | Globe loads initially during 15s kick, but detail stops updating after kick ends | Fast after 15s, but zoom-in shows low-res tiles |

### Current State (`app.js`)

```javascript
viewer.scene.requestRenderMode = true;
viewer.scene.maximumRenderTimeChange = Infinity;

// Kick-start tile streaming for 15s on startup
const _tileKick = setInterval(() => viewer.scene.requestRender(), 100);
setTimeout(() => clearInterval(_tileKick), 15000);
```

Cache version: `app.js?v=14`

### Root Cause

When `requestRenderMode = true` and `maximumRenderTimeChange = Infinity`, Cesium only renders frames when `requestRender()` is explicitly called. The simulation data loop calls `requestRender()` at ~10Hz when receiving WebSocket state updates, which is enough for entity movement but NOT enough for Cesium's tile streaming pipeline — it needs renders triggered by camera movement, zoom changes, and internal tile-ready callbacks to progressively load higher-detail imagery and terrain.

### What Needs Investigation

1. Cesium's `Globe.tileLoadProgressEvent` — could subscribe and call `requestRender()` whenever new tiles are ready
2. Camera `moveEnd` / `changed` events — could trigger `requestRender()` after user pans/zooms
3. A hybrid approach: `maximumRenderTimeChange = 0.1` only while tiles are loading, then switch to `Infinity` when idle
4. Whether the real performance bottleneck is rendering or the data pipeline (Pydantic `model_dump()` serialization at scale)

### Workaround

Users can hard-refresh (`Ctrl+Shift+R`) to clear cached low-res tiles. The 15-second tile kick loads the initial view, but zooming in after that may show blurry tiles until the next data update triggers a render.
