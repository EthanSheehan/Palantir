# Pane Registry Specification

> Defines all pane IDs, metadata, allowed regions, mount contracts, and lifecycle for the AMS workspace.

---

## 1. Overview

The Pane Registry is a central declaration of every pane available in the workspace. It decouples pane content from pane placement — a pane declares what it is and where it can live, but not where it currently lives (that is layout state).

Each pane is registered once with immutable metadata. The Workspace Shell reads the registry to validate docking rules, render tab titles, and enforce size constraints.

---

## 2. PaneDefinition Schema

```typescript
interface PaneDefinition {
  id: string;                          // Unique identifier (kebab-case)
  title: string;                       // Display name in tab bar
  icon: string;                        // Icon identifier for collapsed rail
  component: string;                   // Reference to the module that provides this pane
  defaultRegion: RegionId;             // Where this pane lives on first launch
  allowedRegions: RegionId[];          // Which regions this pane may be moved to
  closable: boolean;                   // Can the user close/hide this pane?
  collapsible: boolean;                // Does this pane support collapsed rendering?
  defaultVisible: boolean;             // Visible on first launch?
  minWidth: number | null;             // Minimum width in px (null = no constraint)
  minHeight: number | null;            // Minimum height in px (null = no constraint)
  preferredSize: {
    width: number | null;              // Preferred width hint (null = flexible)
    height: number | null;             // Preferred height hint (null = flexible)
  };
  persistenceKey: string;              // Key for pane-local state persistence
}

type RegionId = 'top' | 'left' | 'center' | 'right' | 'bottom';
```

---

## 3. Registered Panes

### 3.1 Toolbar

| Field | Value |
|-------|-------|
| `id` | `toolbar` |
| `title` | `Toolbar` |
| `icon` | `settings` |
| `component` | `Toolbar` |
| `defaultRegion` | `top` |
| `allowedRegions` | `[top]` |
| `closable` | `false` |
| `collapsible` | `false` |
| `defaultVisible` | `true` |
| `minWidth` | `null` |
| `minHeight` | `48` |
| `preferredSize` | `{ width: null, height: 48 }` |
| `persistenceKey` | `pane.toolbar` |

**Notes**: The toolbar is locked to the top region. It is always visible and cannot be closed, moved, or collapsed.

---

### 3.2 Map (Globe)

| Field | Value |
|-------|-------|
| `id` | `map` |
| `title` | `Globe` |
| `icon` | `globe` |
| `component` | `CesiumMap` |
| `defaultRegion` | `center` |
| `allowedRegions` | `[center]` |
| `closable` | `false` |
| `collapsible` | `false` |
| `defaultVisible` | `true` |
| `minWidth` | `null` |
| `minHeight` | `null` |
| `preferredSize` | `{ width: null, height: null }` |
| `persistenceKey` | `pane.map` |

**Notes**: The map is locked to center. It fills all remaining space. It is never closed or moved.

---

### 3.3 Assets

| Field | Value |
|-------|-------|
| `id` | `assets` |
| `title` | `Assets` |
| `icon` | `drone` |
| `component` | `AssetsPane` |
| `defaultRegion` | `left` |
| `allowedRegions` | `[left, right]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `280` |
| `minHeight` | `200` |
| `preferredSize` | `{ width: 380, height: null }` |
| `persistenceKey` | `pane.assets` |

**Notes**: Renders the drone card list with status badges, tracking controls, waypoint/range buttons. Currently the ASSETS tab content in the sidebar. Must be refactored to render into any provided container.

**Current DOM dependencies to remove**:
- `document.getElementById('droneListContainer')` — must accept container from mount()
- `document.getElementById('uavCount')` / `document.getElementById('zoneCount')` — stats display should be part of the pane's own DOM

---

### 3.4 Missions

| Field | Value |
|-------|-------|
| `id` | `missions` |
| `title` | `Missions` |
| `icon` | `mission` |
| `component` | `MissionPanel` |
| `defaultRegion` | `left` |
| `allowedRegions` | `[left, right]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `280` |
| `minHeight` | `200` |
| `preferredSize` | `{ width: 380, height: null }` |
| `persistenceKey` | `pane.missions` |

**Notes**: Mission creation form + mission card list. Currently the MISSION tab. The `MissionPanel` module already has `init()` / `render()` — needs `mount(container)` / `unmount()` wrapper.

**Current DOM dependencies to remove**:
- `document.getElementById('missionList')` — hardcoded container lookup
- `document.getElementById('createMissionForm')` — form element lookup
- These should be created inside the pane's own mount container

---

### 3.5 Inspector

| Field | Value |
|-------|-------|
| `id` | `inspector` |
| `title` | `Inspector` |
| `icon` | `inspect` |
| `component` | `InspectorPanel` |
| `defaultRegion` | `left` |
| `allowedRegions` | `[left, right]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `280` |
| `minHeight` | `150` |
| `preferredSize` | `{ width: 380, height: null }` |
| `persistenceKey` | `pane.inspector` |

**Notes**: Context-sensitive detail view for the currently selected entity (asset, mission, alert). Subscribes to `selection.changed`. Currently the OPS tab → Inspector section.

**Current DOM dependencies to remove**:
- `document.getElementById('inspectorContent')` — must render into mount container

---

### 3.6 Alerts

| Field | Value |
|-------|-------|
| `id` | `alerts` |
| `title` | `Alerts` |
| `icon` | `alert` |
| `component` | `AlertsPanel` |
| `defaultRegion` | `bottom` |
| `allowedRegions` | `[left, right, bottom]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `240` |
| `minHeight` | `120` |
| `preferredSize` | `{ width: 340, height: 200 }` |
| `persistenceKey` | `pane.alerts` |

**Notes**: Alert card list with severity sorting, acknowledge button. Currently the ALERTS tab.

**Current DOM dependencies to remove**:
- `document.getElementById('alertList')` — hardcoded container

---

### 3.7 Timeline

| Field | Value |
|-------|-------|
| `id` | `timeline` |
| `title` | `Timeline` |
| `icon` | `timeline` |
| `component` | `TimelinePanel` |
| `defaultRegion` | `bottom` |
| `allowedRegions` | `[bottom]` |
| `closable` | `false` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `null` |
| `minHeight` | `120` |
| `preferredSize` | `{ width: null, height: 240 }` |
| `persistenceKey` | `pane.timeline` |

**Notes**: Canvas-based timeline with playhead scrubbing, swimlanes, pan/zoom. Locked to bottom region because it needs full width. Not closable — it is the temporal anchor of the workspace.

**Current DOM dependencies to remove**:
- `document.getElementById('timelinePanel')` — container lookup
- `document.getElementById('timelineCanvas')` — canvas element lookup
- Must create its own canvas element inside the mount container and handle resize via ResizeObserver

**Critical**: Time state (`timeCursor`, `timeMode`, `playbackSpeed`) stays in AppState, not pane-local state.

---

### 3.8 Macrogrid

| Field | Value |
|-------|-------|
| `id` | `macrogrid` |
| `title` | `Grid Ops` |
| `icon` | `grid` |
| `component` | `MacrogridPanel` |
| `defaultRegion` | `right` |
| `allowedRegions` | `[left, right, bottom]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `false` |
| `minWidth` | `240` |
| `minHeight` | `150` |
| `preferredSize` | `{ width: 340, height: 200 }` |
| `persistenceKey` | `pane.macrogrid` |

**Notes**: Grid recommendation cards with convert-to-mission button. Currently the GRID tab. Default hidden (right region is hidden in v1).

---

### 3.9 Command History (New)

| Field | Value |
|-------|-------|
| `id` | `command_history` |
| `title` | `Commands` |
| `icon` | `command` |
| `component` | `CommandHistoryPane` |
| `defaultRegion` | `bottom` |
| `allowedRegions` | `[bottom, right]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `true` |
| `minWidth` | `240` |
| `minHeight` | `120` |
| `preferredSize` | `{ width: null, height: 200 }` |
| `persistenceKey` | `pane.command_history` |

**Notes**: New pane. Displays a reverse-chronological list of commands with their current state (proposed → sent → completed/failed). Subscribes to `commands.*` events. Clicking a command selects it in AppState for inspector display.

---

### 3.10 Event Log (New — Placeholder)

| Field | Value |
|-------|-------|
| `id` | `event_log` |
| `title` | `Events` |
| `icon` | `log` |
| `component` | `EventLogPane` |
| `defaultRegion` | `right` |
| `allowedRegions` | `[right, bottom]` |
| `closable` | `true` |
| `collapsible` | `true` |
| `defaultVisible` | `false` |
| `minWidth` | `240` |
| `minHeight` | `120` |
| `preferredSize` | `{ width: 340, height: 200 }` |
| `persistenceKey` | `pane.event_log` |

**Notes**: Placeholder for a raw domain event stream viewer. Will query `/api/v1/events` and display a scrolling log. Default hidden.

---

## 4. Mount Contract

Every pane component must implement the following interface:

```javascript
interface MountablePane {
  /**
   * Mount the pane's DOM into the provided container element.
   * Called when the pane becomes the active tab or when the shell initializes.
   * @param container - The DOM element to render into (owned by the shell)
   * @param context - Shared context object { appState, apiClient, wsClient }
   */
  mount(container: HTMLElement, context: PaneContext): void;

  /**
   * Remove the pane's DOM and clean up event listeners.
   * Called when the pane is hidden, moved, or the region collapses.
   */
  unmount(): void;

  /**
   * Re-render the pane's content. Called by AppState subscriptions.
   */
  render(): void;

  /**
   * Called when this pane's tab becomes the active tab in its group.
   * Use for lazy loading or focus management.
   */
  onFocus(): void;

  /**
   * Called when this pane's tab loses focus (another tab selected).
   */
  onBlur(): void;

  /**
   * Optional: Return a dynamic title (e.g., "Alerts (3)" for badge count).
   * If not provided, the static title from PaneDefinition is used.
   */
  getTitle?(): string;

  /**
   * Optional: Return a badge count for the tab (e.g., unread alerts).
   */
  getBadgeCount?(): number;
}
```

### 4.1 PaneContext

```javascript
interface PaneContext {
  appState: AppState;      // Centralized state store
  apiClient: ApiClient;    // REST API client
  wsClient: WsClient;      // Event WebSocket client
  shell: WorkspaceShell;   // Shell API (for requesting focus, etc.)
}
```

### 4.2 Migration Strategy for Existing Panels

Existing panels (MissionPanel, AlertsPanel, etc.) will be wrapped in adapter classes:

```javascript
// Example: wrapping MissionPanel
const MissionPaneAdapter = {
  _container: null,

  mount(container, context) {
    this._container = container;
    // Create the DOM structure that MissionPanel expects
    container.innerHTML = `
      <div id="missionList"></div>
      <div class="create-form" id="createMissionForm">...</div>
    `;
    MissionPanel.init();  // Existing init, now scoped to this container
  },

  unmount() {
    if (this._container) {
      this._container.innerHTML = '';
      this._container = null;
    }
  },

  render() { MissionPanel.render(); },
  onFocus() {},
  onBlur() {},
};
```

The key migration change: existing panels must stop using `document.getElementById()` for their containers and instead use the container provided by `mount()`. This can be done incrementally — the adapter pattern allows the existing code to work initially with minimal changes.

---

## 5. Registry API

```javascript
const PaneRegistry = {
  /**
   * Register a pane definition. Called once during app initialization.
   */
  register(definition: PaneDefinition): void;

  /**
   * Get a pane definition by ID.
   */
  get(paneId: string): PaneDefinition | null;

  /**
   * Get all registered pane definitions.
   */
  getAll(): PaneDefinition[];

  /**
   * Get pane definitions allowed in a specific region.
   */
  getForRegion(regionId: RegionId): PaneDefinition[];

  /**
   * Get the component instance for a pane (implements MountablePane).
   */
  getComponent(paneId: string): MountablePane;
};
```

---

## 6. Registration Order

Panes are registered during app initialization, before the shell mounts:

```javascript
// In app.js or a dedicated init module
PaneRegistry.register({ id: 'toolbar', ... });
PaneRegistry.register({ id: 'map', ... });
PaneRegistry.register({ id: 'assets', ... });
PaneRegistry.register({ id: 'missions', ... });
PaneRegistry.register({ id: 'inspector', ... });
PaneRegistry.register({ id: 'alerts', ... });
PaneRegistry.register({ id: 'timeline', ... });
PaneRegistry.register({ id: 'macrogrid', ... });
PaneRegistry.register({ id: 'command_history', ... });
PaneRegistry.register({ id: 'event_log', ... });

WorkspaceShell.init(loadLayoutState());
```
