# Map Tool Controller Specification

> Defines tool modes, transitions, map event routing, preview overlays, and how tool outputs become command drafts.

---

## 1. Overview

The Map Tool Controller centralizes all map interaction behavior into explicit, named tool modes. In the current codebase, map clicks do different things depending on hidden state flags (`isSettingWaypoint`, `trackedDroneEntity`, etc.) — this is fragile and unpredictable at scale.

The controller replaces ad hoc click handlers with a formal state machine: at any moment, exactly one tool is active, and that tool exclusively defines what clicks, drags, and hovers mean on the map surface.

**Core rule**: Map interactions create drafts or selections. Map interactions do NOT directly mutate live asset state or bypass backend command validation.

---

## 2. Tool Mode Definitions

### 2.1 Initial Tool Modes (v1)

| Tool ID | Display Name | Cursor | Description |
|---------|-------------|--------|-------------|
| `select` | Select | `default` | Click entities to select them. Default tool. |
| `track_asset` | Track Asset | `pointer` | Click an asset to enter camera tracking mode. |
| `set_waypoint` | Set Waypoint | `crosshair` | Click terrain to create a move command draft for the selected asset. |
| `draw_route` | Draw Route | `crosshair` | Click multiple points to define a route. Double-click to finish. |
| `draw_area` | Draw Area | `crosshair` | Click vertices to define a polygon area. Double-click to close. |
| `measure` | Measure | `crosshair` | Click two points to measure distance. |
| `macrogrid_inspect` | Grid Inspect | `help` | Click a grid zone to show zone details in the inspector. |

### 2.2 Future Tool Modes (v2+)

| Tool ID | Description |
|---------|-------------|
| `geofence_edit` | Draw/edit geofence boundaries |
| `mission_area_edit` | Define mission operational area |
| `annotation` | Place text/marker annotations on the map |
| `demand_spike` | Click to inject a demand spike (replaces current double-click behavior) |

---

## 3. Tool Mode Schema

```typescript
interface ToolMode {
  id: string;                          // Unique tool identifier
  name: string;                        // Display name for toolbar
  icon: string;                        // Icon identifier
  cursor: string;                      // CSS cursor for the Cesium canvas
  requiresSelection: string | null;    // Entity type that must be selected (e.g., 'asset'), or null
  persistent: boolean;                 // true = stays active after action; false = reverts to 'select' after one action

  // Event handlers — return true if the event was consumed
  onLeftClick?(position: Cartographic, pickedEntity?: Entity): boolean;
  onDoubleClick?(position: Cartographic, pickedEntity?: Entity): boolean;
  onRightClick?(position: Cartographic, pickedEntity?: Entity): boolean;
  onMouseMove?(position: Cartographic): void;
  onDragStart?(position: Cartographic): void;
  onDrag?(position: Cartographic): void;
  onDragEnd?(position: Cartographic): void;

  // Lifecycle
  onActivate?(): void;                 // Called when tool becomes active
  onDeactivate?(): void;               // Called when tool is replaced

  // Preview overlay
  getOverlayEntities?(): Entity[];     // Cesium entities to show while tool is active
  clearOverlay?(): void;               // Remove preview entities
}
```

---

## 4. Tool Behavior Specifications

### 4.1 Select Tool (`select`)

**Purpose**: Default tool. Click entities to select them for inspection.

| Event | Behavior |
|-------|----------|
| Left click on entity | Select the entity in AppState (`AppState.select('asset', id)`) |
| Left click on terrain | Clear selection (`AppState.clearSelection()`) |
| Double click on entity | Enter `track_asset` mode for that entity |
| Right click | No action (reserved for future context menu) |
| Mouse move | No action |

**Persistent**: Yes (stays active).
**Requires selection**: No.

### 4.2 Track Asset Tool (`track_asset`)

**Purpose**: Camera follows a specific asset. This replaces the current single-click/double-click drone tracking.

| Event | Behavior |
|-------|----------|
| Left click on different entity | Switch tracking to that entity |
| Left click on terrain | Exit tracking, return to `select` tool, restore global camera |
| Double click on entity | Enter third-person view (close lock behind asset) |
| Escape key | Exit tracking, return to `select` tool |

**Persistent**: Yes.
**Requires selection**: Asset must be selected.
**Overlay**: Camera control buttons (Global View, Decouple Camera) appear — these are children of the map region, not separate panes.

### 4.3 Set Waypoint Tool (`set_waypoint`)

**Purpose**: Click terrain to create a move command for the selected asset.

| Event | Behavior |
|-------|----------|
| Left click on terrain | Create a move command draft: `{ type: 'move_to', target_id: selectedAsset, destination: {lon, lat} }` |
| Mouse move | Show preview: dashed line from asset to cursor, target reticle at cursor |
| Right click / Escape | Cancel, return to `select` tool |

**Persistent**: No — reverts to `select` (or `track_asset` if tracking) after placing one waypoint.
**Requires selection**: Asset.

**Command draft flow**:
1. Tool creates draft: `{ action: 'move_drone', drone_id, target_lon, target_lat }`
2. Draft is sent via legacy WS (`ws.send()`) or via `ApiClient.createCommand()`
3. Backend validates and executes
4. Tool does NOT directly set `uav.commanded_target`

**Preview overlay**:
- Dashed cyan polyline from selected asset's current position to mouse cursor
- Green target reticle (circle + crosshair) at mouse position
- Cleared on tool deactivation or after waypoint is placed

### 4.4 Draw Route Tool (`draw_route`)

**Purpose**: Define a multi-point route for mission planning.

| Event | Behavior |
|-------|----------|
| Left click on terrain | Add waypoint to route |
| Double click | Finish route, emit route draft |
| Right click / Escape | Cancel route, clear preview |
| Mouse move | Show preview line from last point to cursor |

**Persistent**: No — reverts to `select` after route is finished.
**Requires selection**: No.

**Output**: Route draft → stored in AppState as a pending route, available for mission/task creation.

**Preview overlay**:
- Connected polyline through placed points (cyan, solid)
- Numbered markers at each point
- Dashed line from last point to cursor

### 4.5 Draw Area Tool (`draw_area`)

**Purpose**: Define a polygon area for mission area, geofence, etc.

| Event | Behavior |
|-------|----------|
| Left click on terrain | Add vertex to polygon |
| Double click | Close polygon, emit area draft |
| Right click / Escape | Cancel, clear preview |
| Mouse move | Show preview: closing line from last vertex to cursor, polygon fill preview |

**Persistent**: No.
**Requires selection**: No.

**Output**: Area draft → `{ vertices: [{lon, lat}, ...] }` stored in AppState.

### 4.6 Measure Tool (`measure`)

**Purpose**: Measure distance between two points.

| Event | Behavior |
|-------|----------|
| Left click (first) | Set start point |
| Left click (second) | Set end point, display distance, stay active for next measurement |
| Mouse move (after first click) | Show preview line + distance label |
| Right click / Escape | Clear measurement, return to `select` |

**Persistent**: Yes.
**Requires selection**: No.

**Preview overlay**:
- Yellow line between points
- Distance label at midpoint (meters/km auto-unit)

### 4.7 Macrogrid Inspect Tool (`macrogrid_inspect`)

**Purpose**: Click a grid zone to show its details in the inspector.

| Event | Behavior |
|-------|----------|
| Left click on zone | Select zone, show details in inspector (queue, UAV count, imbalance, demand rate) |
| Mouse move | Highlight zone under cursor with brighter fill |
| Right click / Escape | Return to `select` |

**Persistent**: Yes.
**Requires selection**: No.

---

## 5. Tool Transitions

### 5.1 Default Tool

The default tool is `select`. The controller reverts to `select` when:
- A non-persistent tool completes its action
- The user presses Escape
- The user clicks the Select tool button in the toolbar

### 5.2 Transition Rules

```
select ──────────→ track_asset       (double-click entity, or explicit toolbar)
select ──────────→ set_waypoint      (toolbar button, requires asset selected)
select ──────────→ draw_route        (toolbar button)
select ──────────→ draw_area         (toolbar button)
select ──────────→ measure           (toolbar button)
select ──────────→ macrogrid_inspect (toolbar button)
track_asset ─────→ select            (click terrain, Escape)
track_asset ─────→ set_waypoint      (toolbar button, tracked asset auto-selected)
set_waypoint ────→ select            (waypoint placed, Escape, right-click)
set_waypoint ────→ track_asset       (waypoint placed while tracking → return to tracking)
draw_route ──────→ select            (route finished, Escape)
draw_area ───────→ select            (area closed, Escape)
measure ─────────→ select            (Escape)
macrogrid_inspect → select           (Escape)
```

### 5.3 Tool Stack

When `set_waypoint` is activated while in `track_asset` mode, the controller remembers the previous tool. After the waypoint is placed, it returns to `track_asset` instead of `select`. This is a one-level stack — not arbitrary depth.

---

## 6. Controller API

```javascript
const MapToolController = {
  /**
   * Initialize the controller. Binds to the Cesium viewer's input handlers.
   * Replaces all existing ad hoc click handlers on the viewer.
   */
  init(viewer: Cesium.Viewer): void;

  /**
   * Register a tool mode. Called during initialization.
   */
  registerTool(tool: ToolMode): void;

  /**
   * Switch to a named tool. Deactivates the current tool and activates the new one.
   */
  setTool(toolId: string): void;

  /**
   * Get the currently active tool ID.
   */
  getActiveTool(): string;

  /**
   * Subscribe to tool changes.
   */
  onToolChange(callback: (toolId: string) => void): void;

  /**
   * Check if a tool requires a selection that isn't met.
   * Returns the required selection type, or null if the tool can activate.
   */
  canActivate(toolId: string): string | null;
};
```

---

## 7. Toolbar Integration

### 7.1 Tool Palette

The toolbar displays a tool palette showing available tools:

```
[ Select | Track | Waypoint | Route | Area | Measure | Grid ]
```

- Active tool is highlighted with primary accent color
- Tools that require a selection (e.g., `set_waypoint` needs an asset) are disabled/greyed when precondition isn't met
- Keyboard shortcuts: `S` = select, `T` = track, `W` = waypoint, `R` = route, `A` = area, `M` = measure, `G` = grid inspect

### 7.2 Status Indicator

Below the tool palette, a one-line status message shows contextual guidance:

| Tool | Status Text |
|------|------------|
| `select` | "Click an entity to select" |
| `track_asset` | "Tracking UAV-{id} — click terrain to exit" |
| `set_waypoint` | "Click terrain to set waypoint for UAV-{id}" |
| `draw_route` | "Click to add waypoints — double-click to finish" |
| `draw_area` | "Click to add vertices — double-click to close" |
| `measure` | "Click two points to measure distance" |
| `macrogrid_inspect` | "Click a grid zone to inspect" |

---

## 8. Migration from Current Code

### 8.1 Current Map Interactions (in `app.js`)

| Current Code Location | Current Behavior | Migrates To |
|-----------------------|-----------------|-------------|
| `viewer.screenSpaceEventHandler` LEFT_CLICK (line ~1152) | If `isSettingWaypoint` → send move command | `set_waypoint.onLeftClick()` |
| `viewer.screenSpaceEventHandler` LEFT_CLICK (line ~750) | Pick entity → select/track | `select.onLeftClick()` |
| Double-click on entity in drone card | `triggerDroneSelection(entity, 'thirdPerson')` | `track_asset` tool (double-click behavior) |
| Single-click on drone card | `triggerDroneSelection(entity, 'macro')` | `track_asset` tool (single-click behavior) |
| Double-click on terrain | Demand spike (`ws.send({action: "spike"})`) | `demand_spike` tool (v2) or removed |
| `MOUSE_MOVE` handler (line ~780) | Compass + cursor position tracking | Stays as global behavior (not tool-specific) |

### 8.2 State Flags to Remove

The following ad hoc state flags in `app.js` are replaced by the tool controller:

- `isSettingWaypoint` → replaced by `MapToolController.getActiveTool() === 'set_waypoint'`
- `trackedDroneEntity` → replaced by tool state in `track_asset` tool
- `macroTrackedId` / `isMacroTrackingReady` → replaced by `track_asset` tool internal state
- `mapClickTimer` → replaced by proper click/double-click disambiguation in the controller

### 8.3 Migration Strategy

1. Create `MapToolController` module with `select` and `track_asset` tools
2. Move existing click handlers into tool `onLeftClick` / `onDoubleClick` methods
3. Remove `isSettingWaypoint`, `trackedDroneEntity`, etc. from global scope
4. Add `set_waypoint` tool, migrating the waypoint placement logic
5. Wire toolbar tool palette UI
6. Add remaining tools (`draw_route`, `draw_area`, `measure`, `macrogrid_inspect`)

---

## 9. Command Draft Pattern

### 9.1 Draft vs Direct Execution

Current code sends commands directly via WebSocket:
```javascript
ws.send(JSON.stringify({ action: "move_drone", drone_id, target_lon, target_lat }));
```

Target pattern: tools create **command drafts** that go through the backend command lifecycle:
```javascript
// Tool creates intent
const draft = { type: 'move_to', target_id: `uav_${droneId}`, destination: { lon, lat, alt_m: 1000 } };

// Send via API (preferred) or legacy WS (transitional)
ApiClient.createCommand(draft);  // POST /api/v1/commands
// Backend: proposed → validated → approved → queued → sent → acknowledged → completed
```

### 9.2 Transitional Approach

During the migration, tools can still use the legacy WS `move_drone` action. The key change is that the **tool** sends the message, not raw click handlers. This makes the behavior auditable and mode-dependent.

Full command lifecycle integration (POST /api/v1/commands with validation) is a separate backend enhancement that can happen in parallel.
