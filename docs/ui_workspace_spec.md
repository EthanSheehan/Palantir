# AMS UI Workspace Specification

The UI is a multi-pane workspace, not just a globe with overlays. This document defines the required panes, selection model, interaction rules, and view synchronization.

---

## 1. Workspace Layout

```
┌────────────────────────────────────────────────────────────────┐
│  Toolbar: Mode selector │ Time controls │ Connection status    │
├──────────┬─────────────────────────────────┬───────────────────┤
│          │                                 │                   │
│  Asset   │                                 │    Inspector      │
│  Panel   │       Map / Globe View          │    Panel          │
│          │       (Cesium)                  │                   │
│          │                                 │                   │
├──────────┤                                 ├───────────────────┤
│          │                                 │                   │
│ Mission  │                                 │    Alerts         │
│  Panel   │                                 │    Panel          │
│          │                                 │                   │
├──────────┴─────────────────────────────────┴───────────────────┤
│                      Timeline Panel                            │
└────────────────────────────────────────────────────────────────┘
```

Panels are resizable, collapsible, and can be rearranged. The map always fills remaining space.

---

## 2. Required Panes

### A. Map / Globe View

**Purpose:** Spatial awareness and geographic context

**Displays:**
- Asset positions with status-colored markers
- Asset tracks / trails
- Mission areas and geofences
- Route previews and active trajectories
- Macro-grid zone overlays (imbalance heatmap)
- Flow lines (rebalancing dispatches)
- Waypoint markers

**Interactions:**
- Click asset on map → selects asset (updates all panels)
- Click terrain (waypoint mode) → creates move_to command draft
- Double-click terrain → trigger demand spike (simulation)
- Scroll / drag → navigate camera
- Camera modes: global overview, macro tracking (2km), third-person (150m)

**View modes:**
- 3D globe (default)
- 2D map (optional)

### B. Asset Panel

**Purpose:** Fleet overview at a glance

**Displays per asset:**
- ID and name
- Status badge (color-coded by AssetStatus)
- Mode indicator
- Battery level (progress bar)
- Link quality indicator
- Health status
- Assigned mission (if any)
- Current task (if any)

**Features:**
- Filter by status, mode, health, capability
- Sort by name, status, battery, distance
- Search by name or ID
- Click asset row → selects asset
- Inline expandable cards with quick actions:
  - Set Waypoint (creates command draft)
  - Show Range (3D visualization)
  - View Details (opens in Inspector)

### C. Mission Panel

**Purpose:** Mission queue and lifecycle management

**Displays per mission:**
- Name and type
- State badge (color-coded by MissionState)
- Priority indicator
- Assigned asset count
- Task progress (completed / total)
- Time constraints (start, end)
- Readiness indicator

**Features:**
- Filter by state, priority, type
- Sort by priority, creation time, deadline
- Create new mission (opens draft form)
- Mission actions: propose, approve, pause, resume, abort
- Click mission → selects mission (highlights assets and tasks on map)
- Expand to show task list

### D. Timeline Panel

**Purpose:** Temporal view of asset reservations and scheduling

**Displays:**
- Horizontal swimlanes (one per asset)
- Colored blocks for each reservation (by ReservationPhase)
- Current time cursor (vertical line)
- Conflict indicators (overlapping blocks highlighted)
- Mission boundaries
- ETA markers

**Features:**
- Zoom in/out on time axis
- Scroll through time
- Click reservation → selects associated mission/task
- Drag time cursor for replay scrubbing
- Toggle between: live mode, historical replay, future plan preview

**Color key (ReservationPhase):**

| Phase | Color |
|-------|-------|
| `idle` | Gray |
| `launch` | Orange |
| `transit` | Blue |
| `hold` | Yellow |
| `task_execution` | Green |
| `return` | Cyan |
| `recovery` | Purple |
| `charging` | Amber |
| `maintenance` | Red |

See [timeline_model.md](timeline_model.md) for reservation model details.

### E. Inspector Panel

**Purpose:** Context-sensitive detail view for the currently selected entity

**Displays (varies by selection type):**

**When asset selected:**
- Full telemetry: position, velocity, heading, altitude
- Battery, link quality, health detail
- Assigned mission and task details
- Command history for this asset
- Recent alerts for this asset

**When mission selected:**
- Mission details and objective
- Full task list with states
- Assigned assets with current status
- Approval history
- Timeline reservations for this mission

**When task selected:**
- Task details: type, target, service time
- Dependencies and their states
- Assigned asset status
- Command history for this task

**When command selected:**
- Full command lifecycle: created → validated → approved → sent → acknowledged → completed/failed
- Timestamps for each state transition
- Payload details
- Failure reason (if applicable)

**When alert selected:**
- Alert details: type, severity, message
- Source entity details
- Acknowledgement / clearance history

### F. Alerts Panel

**Purpose:** Operational alerts requiring operator attention

**Displays per alert:**
- Severity icon (info / warning / critical)
- Alert type
- Message summary
- Source entity link
- Time since creation
- State (open / acknowledged / cleared)

**Features:**
- Filter by severity, state, type, source
- Sort by severity (critical first), time
- Click alert → selects source entity
- Acknowledge button (per alert or bulk)
- Auto-dismiss cleared alerts after configurable delay
- Critical alerts always pinned to top

**Alert types tracked:**
- Link loss
- Low battery
- Stale telemetry
- Mission delays
- Geofence violations
- Failed commands
- Timeline conflicts
- Health degradation

---

## 3. Selection Model

Selection is centralized and global. All panels react to selection changes.

### Selection State

| Property | Type | Description |
|----------|------|-------------|
| `selectedAssetId` | string \| null | Currently selected asset |
| `selectedMissionId` | string \| null | Currently selected mission |
| `selectedTaskId` | string \| null | Currently selected task |
| `selectedCommandId` | string \| null | Currently selected command |
| `selectedAlertId` | string \| null | Currently selected alert |
| `timeCursor` | timestamp | Current time position (live or replay) |

### Selection Rules

1. Selecting an asset highlights it on the map, scrolls to it in the Asset Panel, and shows its details in the Inspector.
2. Selecting a mission highlights its assigned assets and task areas on the map, and shows its details in the Inspector.
3. Selecting an alert selects its source entity (asset, mission, task, or command).
4. Selection is single-entity per type — selecting a new asset deselects the previous one.
5. Multiple selection types can coexist (e.g., an asset and a mission can both be selected).
6. Clicking empty space on the map clears asset selection.

---

## 4. Command Creation Flow

No button should directly perform a vehicle action. All operator actions follow this flow:

```
Operator click (button or map)
    │
    ▼
Draft command (preview in Inspector)
    │
    ▼
Validate (backend checks feasibility)
    │
    ├── Validation fails → show error, allow edit
    │
    ▼
Optional approval step (for critical commands)
    │
    ▼
Dispatch (sent to execution adapter)
    │
    ▼
Show command state in UI (Inspector + command history)
```

### Inline Card Controls

Inline controls in asset cards (e.g., "Set Waypoint", "Return Home") are permitted but must only create command drafts. They must not own execution behavior.

---

## 5. Time Navigation

The UI supports three temporal modes:

### Live Mode (Default)

- Time cursor tracks real time
- All panels show current state
- Events update in real time via WebSocket

### Historical Replay Mode

- Time cursor set to a past timestamp
- Panels show state as of that timestamp (reconstructed from events)
- Timeline panel allows scrubbing through history
- Playback speed controls: 1x, 2x, 5x, 10x, pause

### Future Plan Preview Mode

- Time cursor set to a future timestamp
- Panels show planned/predicted state
- Timeline panel shows planned reservations
- "What-if" mode: preview effect of proposed missions/commands

### Mode Switching

- Toggle between modes via toolbar
- Transitioning to live mode snaps cursor to current time
- Historical mode requires a date/time picker or timeline scrub

---

## 6. Frontend State Separation

### Global Application State (shared across panels)

| State | Description |
|-------|-------------|
| Selection state | Selected asset, mission, task, command, alert |
| Visible layers | Grid overlay, waypoints, trails, geofences |
| Filters | Active filters per panel |
| Time cursor | Current temporal position |
| Time mode | Live / replay / preview |
| Active workspace panel | Which panels are visible |
| Camera mode | Global / macro / third-person |
| WebSocket subscription | Active event subscriptions |

### Local Component State (per-panel only)

| State | Description |
|-------|-------------|
| Panel expansion | Collapsed / expanded state |
| Input drafts | Form values being composed |
| Form modals | Open/closed modal dialogs |
| Hover state | Element currently hovered |
| Scroll position | Current scroll offset |

**Rule:** Do not mix backend truth with local UI convenience state. The frontend never owns operational truth.

---

## 7. View Synchronization Rules

1. All panels subscribe to the same global selection state.
2. When the backend emits an event, all relevant panels update simultaneously.
3. The map highlights must always match the current selection.
4. The Inspector must always reflect the currently selected entity.
5. The Timeline cursor position must be consistent across all panels.
6. Panel filters are independent — filtering the Asset Panel does not affect the map.
7. Camera tracking (following a selected asset) is a view preference, not operational state.

---

## 8. Cross-References

- Entity definitions displayed in panels: [domain_model.md](domain_model.md)
- State badges and transitions: [state_machines.md](state_machines.md)
- Events that trigger UI updates: [event_catalog.md](event_catalog.md)
- API for operator actions: [api_contract.md](api_contract.md)
- Timeline reservation visualization: [timeline_model.md](timeline_model.md)
