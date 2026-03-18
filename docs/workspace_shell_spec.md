# Workspace Shell Specification

> Defines the layout region model, docking rules, splitter behavior, tab groups, and default layout for the AMS workspace shell.

---

## 1. Overview

The Workspace Shell is the top-level layout manager that owns where panes live, how they resize, and how the user reconfigures the workspace. It sits between the Desktop Host (process lifecycle) and the Panel Runtime (pane content). It does not own any business logic or operational state.

The shell implements a **constrained dockable layout**: users can resize, collapse, reorder, and re-dock panels, but only within predefined regions. This is not a freeform floating-window desktop.

---

## 2. Region Model

### 2.1 Region Definitions

The workspace defines five layout regions:

```
┌──────────────────────────────────────────────────────┐
│                      TOP (toolbar)                    │
├─────────┬────────────────────────────┬───────────────┤
│         │                            │               │
│  LEFT   │          CENTER            │    RIGHT      │
│  (ops   │          (globe)           │  (optional)   │
│  rail)  │                            │               │
│         │                            │               │
├─────────┴────────────────────────────┴───────────────┤
│                    BOTTOM (timeline)                  │
└──────────────────────────────────────────────────────┘
```

| Region | Purpose | Default Visible | Resizable | Collapsible | Min Size | Default Size |
|--------|---------|----------------|-----------|-------------|----------|-------------|
| `top` | Toolbar, mode selector, connection status | Yes | No (fixed height) | No | 48px height | 48px |
| `left` | Operations rail (assets, missions, inspector) | Yes | Width via splitter | Yes (collapse to icon rail) | 240px width | 380px |
| `center` | Globe / Map | Yes | Fills remaining space | No | — | Flex |
| `right` | Secondary detail (inspector, alerts, macrogrid) | No (hidden by default v1) | Width via splitter | Yes | 240px width | 340px |
| `bottom` | Timeline, alerts, command history | Yes | Height via splitter | Yes (collapse to tab bar) | 120px height | 240px |

### 2.2 Region Invariants

- `center` always exists and always contains the map. It cannot be replaced, hidden, or occupied by another pane.
- `top` always exists and always contains the toolbar. It is a fixed-height strip.
- `left`, `right`, and `bottom` are dock regions. They contain tab groups.
- Only `left`, `right`, and `bottom` support pane docking and reordering.
- The `center` region absorbs all remaining space after other regions are sized.

---

## 3. Splitter Behavior

### 3.1 Splitter Types

| Splitter | Orientation | Between | Draggable |
|----------|-------------|---------|-----------|
| Left splitter | Vertical (left-right) | `left` and `center` | Yes |
| Right splitter | Vertical (left-right) | `center` and `right` | Yes |
| Bottom splitter | Horizontal (top-bottom) | `center+left+right` and `bottom` | Yes |

### 3.2 Drag Behavior

- Splitters are 4px wide/tall hit targets with a `col-resize` or `row-resize` cursor.
- During drag: the adjacent regions resize live. The `center` region absorbs the delta.
- Splitter position is clamped to the minimum size of each adjacent region.
- Splitter position is persisted in layout state on `mouseup`.

### 3.3 Double-Click Behavior

- Double-clicking a splitter collapses the adjacent non-center region.
- Double-clicking the splitter of a collapsed region restores it to its last persisted size.

---

## 4. Tab Group Behavior

### 4.1 Tab Group Structure

Each dock region (`left`, `right`, `bottom`) contains one or more **tab groups**. A tab group is an ordered list of panes with one active (visible) pane.

```
TabGroup:
  id: string (auto-generated)
  tabs: PaneId[]         // ordered list of pane IDs
  activeTab: PaneId      // currently visible pane
```

### 4.2 Tab Bar Rendering

- Each tab group renders a tab bar at the top of its container.
- Tabs show the pane's `title` (from PaneRegistry metadata).
- The active tab is highlighted with the primary accent color (#38bdf8).
- Inactive tabs use muted text (#94a3b8).
- Clicking a tab switches the active pane within the group.

### 4.3 Tab Reordering

- Tabs within a group can be reordered by drag-and-drop along the tab bar.
- This is a v1 stretch goal — initial implementation can use fixed order.

### 4.4 Tab Moving Between Regions

- A tab can be dragged from one region's tab group to another region's tab group, if the pane's `allowedRegions` includes the target region.
- This is a v2 feature. v1 uses fixed region assignments.

### 4.5 Multiple Tab Groups Per Region

- v1: Each region has exactly one tab group.
- v2: Regions can be split vertically (left/right) or horizontally (bottom) into multiple tab groups.

---

## 5. Collapse / Expand Behavior

### 5.1 Left Region Collapse

- Collapsed state: the left region shrinks to a narrow icon rail (~48px wide) showing pane icons.
- Clicking an icon in the collapsed rail expands the region and activates that pane's tab.
- Collapse toggle: click the collapse chevron at the top of the left region, or double-click the left splitter.

### 5.2 Right Region Collapse

- Same behavior as left, but mirrored.
- Since right is hidden by default in v1, collapse/expand is the mechanism for showing it.

### 5.3 Bottom Region Collapse

- Collapsed state: the bottom region shrinks to just the tab bar (~32px height).
- Tabs remain visible and clickable. Clicking a tab expands the region.
- Collapse toggle: click the collapse chevron, or double-click the bottom splitter.

---

## 6. Default Layout

### 6.1 v1 Default (on first launch or reset)

```yaml
regions:
  top:
    visible: true
    height: 48
    pane: toolbar
  left:
    visible: true
    width: 380
    collapsed: false
    groups:
      - tabs: [assets, missions, inspector]
        activeTab: assets
  center:
    visible: true
    pane: map
  right:
    visible: false
    width: 340
    collapsed: true
    groups:
      - tabs: [macrogrid, event_log]
        activeTab: macrogrid
  bottom:
    visible: true
    height: 240
    collapsed: false
    groups:
      - tabs: [timeline, alerts, command_history]
        activeTab: timeline
```

### 6.2 Reset Behavior

- "Reset Layout" action restores the v1 default layout above.
- All splitter positions, tab orders, and visibility states return to defaults.
- Operational state (AppState) is not affected.

---

## 7. Shell DOM Structure

The shell generates the following DOM hierarchy:

```html
<div id="workspace-shell">
  <div id="ws-region-top" class="ws-region ws-region-top">
    <!-- toolbar pane mounts here -->
  </div>
  <div id="ws-body" class="ws-body">
    <div id="ws-region-left" class="ws-region ws-region-left">
      <div class="ws-collapse-toggle"></div>
      <div class="ws-tab-group">
        <div class="ws-tab-bar">...</div>
        <div class="ws-tab-content"><!-- active pane mounts here --></div>
      </div>
    </div>
    <div id="ws-splitter-left" class="ws-splitter ws-splitter-v"></div>
    <div id="ws-region-center" class="ws-region ws-region-center">
      <!-- Cesium container mounts here -->
    </div>
    <div id="ws-splitter-right" class="ws-splitter ws-splitter-v"></div>
    <div id="ws-region-right" class="ws-region ws-region-right">
      <div class="ws-collapse-toggle"></div>
      <div class="ws-tab-group">...</div>
    </div>
  </div>
  <div id="ws-splitter-bottom" class="ws-splitter ws-splitter-h"></div>
  <div id="ws-region-bottom" class="ws-region ws-region-bottom">
    <div class="ws-collapse-toggle"></div>
    <div class="ws-tab-group">...</div>
  </div>
</div>
```

---

## 8. Shell API

The WorkspaceShell exposes the following API to the rest of the application:

```javascript
WorkspaceShell = {
  init(layoutState)           // Bootstrap shell DOM and mount panes
  getRegion(regionId)         // Get region container element
  mountPane(paneId, regionId) // Mount a pane into a region's tab group
  unmountPane(paneId)         // Remove a pane from its current region
  movePane(paneId, targetRegionId) // Move pane between regions
  setActiveTab(regionId, paneId)   // Switch active tab in a region
  collapseRegion(regionId)   // Collapse a dock region
  expandRegion(regionId)     // Expand a collapsed region
  toggleRegion(regionId)     // Toggle collapse state
  getLayoutState()           // Serialize current layout for persistence
  resetLayout()              // Restore default layout
  onLayoutChange(callback)   // Subscribe to layout changes (for persistence)
}
```

---

## 9. CSS Strategy

- All shell styles use the `ws-` prefix to avoid conflicts with existing panel styles.
- Shell uses CSS Grid for the overall layout (`grid-template-rows`, `grid-template-columns`).
- Region sizes are set via CSS custom properties (`--ws-left-width`, `--ws-bottom-height`, etc.) updated by splitter drag.
- Collapse transitions use CSS `transition: width 0.2s` / `transition: height 0.2s`.
- The dark theme (#0a0f19 background, #1e293b borders) is consistent with existing styles.
- Splitter hover state: lighter border color + cursor change.

---

## 10. Integration with Existing Code

### 10.1 Cesium Container

The existing `<div id="cesiumContainer">` is moved inside `ws-region-center`. The Cesium viewer initializes against this container as before. No changes to Cesium setup code.

### 10.2 Existing Panel Modules

Existing panels (MissionPanel, AlertsPanel, etc.) are wrapped in pane adapters that implement `mount(container)` / `unmount()`. Their internal rendering logic is unchanged. The shell calls `mount()` when a pane becomes active and `unmount()` when it is removed or its region collapses.

### 10.3 AppState

The shell does not read or write AppState. It has its own `WorkspaceLayoutState` (see layout_state_schema.md). Panels continue to subscribe to AppState as before.
