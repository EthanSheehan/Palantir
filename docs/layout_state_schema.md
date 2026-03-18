# Layout State Schema Specification

> Defines the workspace layout state structure, persistence rules, schema versioning, and reset behavior.

---

## 1. Overview

The WorkspaceLayoutState is a dedicated state object that tracks where panes live, how regions are sized, which tabs are active, and whether regions are collapsed. It is completely separate from AppState (operational/business state).

Layout state is persisted to `localStorage` (browser mode) or a local JSON file (desktop mode) and restored on startup.

---

## 2. Schema Definition

### 2.1 Top-Level Structure

```typescript
interface WorkspaceLayoutState {
  version: number;                    // Schema version (currently 1)
  activePreset: string;               // Name of active layout preset (default: "default")
  regions: {
    top: TopRegionState;
    left: DockRegionState;
    center: CenterRegionState;
    right: DockRegionState;
    bottom: DockRegionState;
  };
  floating: FloatingPaneState[];      // Future: floating/detached panes
}
```

### 2.2 Region State Types

```typescript
interface TopRegionState {
  visible: true;                      // Always visible
  height: number;                     // Fixed: 48
  pane: 'toolbar';                    // Always toolbar
}

interface CenterRegionState {
  visible: true;                      // Always visible
  pane: 'map';                        // Always map
}

interface DockRegionState {
  visible: boolean;                   // Whether region is shown at all
  collapsed: boolean;                 // Whether region is in collapsed (icon rail / tab bar) state
  size: number;                       // Width (left/right) or height (bottom) in pixels
  groups: TabGroupState[];            // Tab groups in this region
}

interface TabGroupState {
  id: string;                         // Auto-generated group ID
  tabs: string[];                     // Ordered list of pane IDs
  activeTab: string;                  // Currently visible pane ID
}

interface FloatingPaneState {         // Future use
  paneId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}
```

---

## 3. Default Layout State

This is the state used on first launch or after "Reset Layout":

```json
{
  "version": 1,
  "activePreset": "default",
  "regions": {
    "top": {
      "visible": true,
      "height": 48,
      "pane": "toolbar"
    },
    "left": {
      "visible": true,
      "collapsed": false,
      "size": 380,
      "groups": [
        {
          "id": "left-main",
          "tabs": ["assets", "missions", "inspector"],
          "activeTab": "assets"
        }
      ]
    },
    "center": {
      "visible": true,
      "pane": "map"
    },
    "right": {
      "visible": false,
      "collapsed": true,
      "size": 340,
      "groups": [
        {
          "id": "right-main",
          "tabs": ["macrogrid", "event_log"],
          "activeTab": "macrogrid"
        }
      ]
    },
    "bottom": {
      "visible": true,
      "collapsed": false,
      "size": 240,
      "groups": [
        {
          "id": "bottom-main",
          "tabs": ["timeline", "alerts", "command_history"],
          "activeTab": "timeline"
        }
      ]
    }
  },
  "floating": []
}
```

---

## 4. Persistence Rules

### 4.1 When to Save

Layout state is saved on every user-initiated layout change:
- Splitter drag ends (region resize)
- Tab clicked (active tab change)
- Region collapsed/expanded
- Pane moved between regions (v2)
- Tab reordered (v2)

Layout is **not** saved on:
- Window resize (the layout is responsive; only explicit splitter drags persist)
- Programmatic state changes from the application

### 4.2 Where to Save

| Mode | Storage Location | Key |
|------|-----------------|-----|
| Browser | `localStorage` | `ams.workspace.layout` |
| Desktop (PyQt5) | `~/.ams/layout.json` (or equivalent via QSettings) | — |

### 4.3 Save Format

The layout state is serialized as JSON. The `version` field allows future migrations.

```javascript
function saveLayoutState(state) {
  localStorage.setItem('ams.workspace.layout', JSON.stringify(state));
}

function loadLayoutState() {
  const raw = localStorage.getItem('ams.workspace.layout');
  if (!raw) return DEFAULT_LAYOUT_STATE;

  const state = JSON.parse(raw);
  return migrateLayoutState(state);
}
```

### 4.4 Debouncing

Save operations are debounced with a 500ms delay to avoid excessive writes during rapid splitter dragging.

---

## 5. Schema Versioning

### 5.1 Version Field

The `version` field is an integer that increments when the schema changes in a backward-incompatible way.

### 5.2 Migration Strategy

```javascript
function migrateLayoutState(state) {
  if (!state.version) {
    // Pre-versioned state: discard and use default
    return DEFAULT_LAYOUT_STATE;
  }

  let current = state;

  // Migration chain
  if (current.version === 1) {
    // current version, no migration needed
  }

  // Future: if (current.version === 1) { current = migrateV1toV2(current); }

  return current;
}
```

### 5.3 Incompatible State

If the persisted state references pane IDs that no longer exist in the PaneRegistry, those panes are silently removed from the layout. If a required pane (toolbar, map, timeline) is missing, it is re-added in its default position.

---

## 6. Reset Behavior

### 6.1 Reset to Default

The "Reset Layout" action:
1. Replaces the current layout state with `DEFAULT_LAYOUT_STATE`
2. Persists the default state
3. Triggers a full shell re-mount (unmounts all panes, rebuilds DOM, mounts panes in default positions)
4. Does NOT affect AppState (operational state is unchanged)

### 6.2 Reset Trigger Points

- Menu action: "Reset Layout" in the application menu (desktop mode)
- Keyboard shortcut: `Ctrl+Shift+R` (tentative)
- Toolbar button: Optional "reset layout" icon in the toolbar overflow menu

---

## 7. Validation Rules

When loading persisted layout state, validate:

1. **Schema version**: Must be a known version. Unknown → reset to default.
2. **Required panes**: `toolbar` in `top`, `map` in `center`, `timeline` in `bottom` (or in its allowed regions). Missing → re-add in default position.
3. **Pane existence**: Every pane ID in tab groups must exist in PaneRegistry. Unknown IDs → remove from layout.
4. **Region constraints**: Every pane must be in one of its `allowedRegions`. Violations → move to `defaultRegion`.
5. **No duplicates**: A pane ID may appear in at most one tab group. Duplicates → keep first occurrence, remove others.
6. **Active tab validity**: `activeTab` must be one of the group's `tabs`. Invalid → set to first tab.
7. **Size bounds**: Region sizes must respect `minWidth`/`minHeight` from PaneRegistry. Too small → clamp to minimum.

---

## 8. Layout Presets (Future)

### 8.1 Concept

Named layout presets allow users to save and switch between workspace configurations:
- "Default" — standard operations layout
- "Mission Planning" — expanded left rail with missions + inspector, collapsed bottom
- "Monitoring" — full timeline bottom, alerts visible, minimal left rail
- "Analysis" — right region open with event log + macrogrid

### 8.2 Storage

```json
{
  "ams.workspace.presets": {
    "default": { /* layout state */ },
    "mission_planning": { /* layout state */ },
    "monitoring": { /* layout state */ }
  },
  "ams.workspace.activePreset": "default"
}
```

### 8.3 Implementation Priority

Presets are a v2 feature. v1 supports only a single persisted layout.

---

## 9. Interaction with AppState

Layout state and AppState are completely independent:

| Concern | Owner | Example |
|---------|-------|---------|
| Which tab is active in the left region | Layout state | `left.groups[0].activeTab = "missions"` |
| Which asset is selected | AppState | `selection.assetId = "ast_abc123"` |
| Bottom region height | Layout state | `bottom.size = 260` |
| Time cursor position | AppState | `timeCursor = 1710000000000` |
| Whether right region is visible | Layout state | `right.visible = true` |
| Connection status | AppState | `connected = true` |

No cross-contamination. The shell reads layout state. Panels read AppState. Neither reads the other's store.
