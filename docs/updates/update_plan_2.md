Below is a focused implementation plan for the workspace/app-shell refactor, aimed at your end goal:

desktop .exe

central globe as the primary surface

persistent bottom timeline

persistent left operations rail

dockable/reconfigurable panes within controlled regions

map interactions routed through tool modes

no panel owning operational truth

This plan is based on what is already in your current docs and implementation: a multi-pane workspace concept, centralized AppState, event-driven backend, timeline panel, and clear backend/frontend separation. The main missing piece is a real workspace shell and layout system; right now the UI is still effectively a fixed Cesium page with a tabbed sidebar and a dedicated timeline panel.

# AMS Workspace Shell Refactor Plan
## Desktop-Style Dockable UI / App Shell Implementation Plan
### Status: Frontend Architecture Refactor Plan

---

# 1. Purpose

This document defines the implementation plan for evolving the current AMS frontend from a fixed dashboard layout into a desktop-style mission operations workspace.

Target UX:

- central globe/map as the primary visual surface
- persistent left-side operations rail
- persistent bottom timeline region
- dockable/reconfigurable panels within constrained regions
- layout persistence across restarts
- map interactions handled through explicit tool modes
- panel content decoupled from panel placement
- suitable for packaging as a larger desktop `.exe`

This plan is intentionally focused on the **workspace/application shell**, not on new mission logic, macro-grid logic, or low-level execution behavior.

---

# 2. Current State Summary

## 2.1 What already exists and should be preserved

The current system already has strong foundations:

- a multi-pane workspace concept rather than a map-only mindset
- centralized frontend state (`AppState`)
- a dedicated timeline concept with live/scrub behavior
- explicit backend/frontend responsibility split
- command flow intended to go through backend validation and execution adapters
- discrete frontend modules for toolbar, mission panel, alerts panel, inspector, timeline, and macrogrid

These are the correct foundations for a dockable desktop-style UI.

## 2.2 What is structurally missing

The current frontend still lacks:

- a first-class workspace shell
- a panel registry
- a real layout manager
- layout persistence state
- a region-based docking model
- a formal map tool controller
- decoupling between panel content and panel placement
- a robust desktop host model beyond the current browser-like wrapper

The current tabbed sidebar and fixed DOM composition are not sufficient for the target UX.

---

# 3. Design Goals

## 3.1 Non-negotiable layout goals

The target workspace must preserve these spatial anchors:

- **Center** = Globe / Map view
- **Bottom** = Timeline region (default active pane = Timeline)
- **Left** = Operations rail
- **Top** = Toolbar / mode / connection / time controls

This is a **constrained dockable layout**, not a fully freeform floating-window desktop.

## 3.2 Reconfigurability goals

Within those constraints, the user should be able to:

- resize panels with splitters
- collapse / expand panels
- reorder panels within a region
- tab-stack compatible panels in the same region
- move eligible panels between allowed regions
- save/restore workspace layouts
- use multiple named workspace presets later

## 3.3 Architectural goals

- panel placement must not be hardcoded into panel logic
- workspace layout state must be separate from operational state
- map interactions must use explicit tools/modes
- the frontend must remain a projection over backend truth
- no new UI feature should bypass command lifecycle rules

---

# 4. Target Frontend Architecture

## 4.1 New top-level frontend layers

```text
[ Desktop Host ]
  window lifecycle
  local config
  process orchestration
  native persistence hooks

[ Workspace Shell ]
  layout regions
  docking rules
  splitters
  visibility
  tab groups
  focus
  workspace presets

[ Panel Runtime ]
  pane registry
  pane mounting/unmounting
  pane metadata
  pane lifecycle

[ Shared App State ]
  assets, missions, tasks, commands, alerts, reservations, recommendations
  selection
  time cursor / time mode
  filters
  connection state

[ Map Tool Controller ]
  tool modes
  map gesture routing
  command drafting hooks
  edit overlays
4.2 Separation of concerns
Workspace Shell owns:

where panes live

how panes resize/collapse

which pane is active in a region

layout persistence

Panel modules own:

what content they render

how they react to selection/state

local UI interaction state only

AppState owns:

shared application truth used by all panes

selection

filters

time cursor

connection state

Map Tool Controller owns:

which map interaction mode is active

what clicks/drags mean at this moment

translating map gestures into drafts/intents

5. Mandatory New Subsystems
5.1 Workspace Shell

Create a first-class WorkspaceShell subsystem.

Responsibilities:

define layout regions

manage docked panels

manage tab groups

manage splitter positions

collapse/expand regions

persist and restore layout

Minimum regions:

top
left
center
bottom
right (optional, but supported)
floating (future / optional)

Initial policy:

map must remain in center

timeline must default to bottom

operations panes default to left

inspector may live in left or right

alerts may live in right or bottom

macrogrid may live in left, right, or bottom

5.2 Pane Registry

Create a central PaneRegistry.

Each pane must be declared in one place with metadata.

Example shape:

PaneDefinition:
  id: string
  title: string
  component: string
  defaultRegion: left | right | bottom | center
  allowedRegions: [left, right, bottom]
  closable: boolean
  collapsible: boolean
  detachable: boolean
  defaultVisible: boolean
  minWidth: number | null
  minHeight: number | null
  preferredSize:
    width: number | null
    height: number | null
  persistenceKey: string

Initial panes:

map

assets

missions

inspector

alerts

timeline

macrogrid

command_history (new)

event_log (new placeholder)

Important rule:

pane modules must not assume where they are mounted

5.3 Layout State Store

Add a dedicated layout state store separate from AppState.

This is not business state.

Example shape:

WorkspaceLayoutState:
  activePreset: string
  regions:
    top:
      visible: true
      height: 48
      tabs: [toolbar]
      activeTab: toolbar
    left:
      visible: true
      width: 420
      groups:
        - tabs: [assets, missions, inspector]
          activeTab: assets
    center:
      visible: true
      pane: map
    right:
      visible: false
      width: 360
      groups: []
    bottom:
      visible: true
      height: 260
      groups:
        - tabs: [timeline, alerts, command_history]
          activeTab: timeline
  floating: []

Persistence requirements:

save on layout change

restore on startup

reset to default layout option

version the layout schema

5.4 Map Tool Controller

Add a centralized map interaction controller.

The current map behavior includes clicking terrain to create move command drafts and double-clicking terrain for demand spikes. That must be refactored into explicit tool modes. Existing map interactions already exist, but they are too ad hoc for a larger workspace app.

Required initial tool modes:

select
track_asset
set_waypoint
draw_route
draw_area
measure
macrogrid_inspect

Future tool modes:

geofence_edit

mission_area_edit

annotation

asset_range_preview

Each tool mode must define:

cursor behavior

allowed click targets

preview overlay behavior

cancel behavior

resulting intent/command draft

Rule:

map interactions create drafts or selections

map interactions do not directly mutate live asset state

6. Region Strategy
6.1 Center Region

Reserved for:

Map / Globe

Rules:

always present

cannot be fully replaced by another pane

receives the largest area

tool overlays and camera overlays are children of the map pane, not separate panes

6.2 Left Region

Purpose:

operations rail

Default contents:

Assets

Missions

Inspector

Recommended default:

stacked/tabbed groups, not a single tab sidebar

allow split vertically into 2 or 3 sections later

Immediate target:

replace current 5-tab sidebar model with a left dock region

6.3 Bottom Region

Purpose:

time/analysis/logging surface

Default contents:

Timeline

Alerts

Command History

Timeline must be the default active pane here.
This aligns with the existing timeline concept and should remain a stable UX anchor.

6.4 Right Region

Purpose:

secondary detail/attention surfaces

Default contents:

Inspector (optional alternative location)

Alerts

Macrogrid

Event Log

This region can be hidden by default in the first pass.

7. Panel Refactor Rules
7.1 Convert current panels into mountable pane components

Current panel modules already exist, but they are still effectively bound to the current fixed layout.

Refactor each into a generic mountable pane:

AssetsPane

MissionsPane

InspectorPane

AlertsPane

TimelinePane

MacrogridPane

Each pane should expose:

mount(container, context)

unmount()

render()

onFocus()

onBlur()

optional getTitle()

7.2 Remove layout assumptions from pane logic

Examples of what must stop:

pane assuming it is “the sidebar tab”

timeline assuming fixed bottom DOM node

inspector assuming it always owns the right-hand detail area

All panes must render correctly no matter which allowed region they occupy.

7.3 Keep panel content and local state intact where possible

The goal is not to rewrite all panel internals.
The goal is to wrap them in a layout-managed shell.

8. Replace Sidebar Tabs with Operations Rail

The current sidebar uses five tabs: MISSION, ASSETS, OPS, ALERTS, GRID.

Replace this with a left-side docked operations rail.

8.1 Default left-rail composition

Recommended v1 default:

top section

Assets

middle section

Missions

lower section

Inspector

Optional:

let one or more sections be tabbed internally

allow drag-to-resize vertical split between sections

8.2 Why this change is necessary

The current tabbed sidebar only allows one operational context at a time.
A real workstation benefits from simultaneous visibility:

assets + missions together

inspector always available

bottom timeline visible continuously

This is a major usability improvement and better matches the target desktop workflow.

9. Bottom Timeline Region Refactor
9.1 Promote timeline from panel to region anchor

The timeline already exists conceptually and operationally.
Now formalize it as the default anchor of the bottom region.

9.2 Bottom region should support tabs

Bottom region should support:

Timeline

Alerts

Command History

Event Log (placeholder/future)

The timeline remains the default active tab.

9.3 Time state must stay global

The timeline pane can move or remount, but:

timeCursor

timeMode

playbackSpeed

must remain in shared application state, not in pane-local state.

This is already aligned with the current approach and should be preserved.

10. Desktop Host / .exe Strategy
10.1 Treat desktop wrapper as a host shell, not just a browser box

The desktop app should eventually own:

backend process launch/stop

frontend startup

layout persistence path

local settings path

window state restore

export/import of workspace layouts

crash-safe startup behavior

10.2 Immediate desktop host requirements

launch backend reliably

detect backend readiness before showing full UI

persist window size/position

persist workspace layout

expose application menu hooks later:

Reset Layout

Export Layout

Import Layout

Toggle Panels

Open Logs

10.3 Keep transport architecture unchanged initially

Do not change the backend/frontend contract just because the app becomes an .exe.
The desktop host wraps the existing local API/WebSocket architecture.

11. Frontend Technology Refactor
11.1 Current state

The current frontend uses IIFE modules, script tags, global singletons, and no build system.

That was acceptable for early speed, but it is becoming a structural limit for:

pane lifecycle

layout shell complexity

typed contracts

large app maintainability

desktop-scale UI behavior

11.2 Required next step

Move to a proper module-based frontend architecture.

Minimum target:

ES modules + bundler

explicit imports/exports

panel registry as code, not globals

workspace shell as a dedicated module

typed layout schemas if possible

This does not require a heavy frontend framework immediately, but the current IIFE pattern should not be the long-term base for the workspace shell.

11.3 Transition rule

Do not rewrite everything at once.

Recommended approach:

wrap existing panels behind a registry-compatible interface

migrate shell/layout first

migrate panel internals gradually

12. Command Workflow Preservation

The workspace refactor must not reintroduce direct map-to-simulator shortcuts.

Current and target docs already require:

commands as explicit objects

backend validation

no direct UI mutation of live assets

Therefore:

inline card actions must create drafts

map tool actions must create drafts

shell-level shortcuts must create drafts or REST calls

no pane may directly call a simulator move function

The workspace shell is a UI refactor, not a license to bypass domain architecture.

13. Implementation Phases
Phase 0 — Freeze Existing Behavior

Goal:

preserve current functional UI while introducing shell scaffolding

Tasks:

document current panel mount points

identify panel-specific DOM assumptions

identify all map interaction entry points

inventory all direct UI mutation paths

Deliverables:

workspace_shell_spec.md

pane_registry_spec.md

layout_state_schema.md

map_tool_controller_spec.md

Phase 1 — Introduce Workspace Shell Skeleton

Goal:

add shell without changing panel internals yet

Tasks:

create top/left/center/bottom/right region containers

add splitter mechanics

add tab group primitive

add shell state bootstrapping

mount existing map and current panels through shell

Deliverables:

WorkspaceShell

region renderer

splitter component

tab group component

shell bootstrap integrated into app startup

Success criteria:

app still runs

map remains center

timeline bottom

sidebar contents render through shell container

Phase 2 — Add Pane Registry + Mountable Pane Interface

Goal:

make panels location-independent

Tasks:

create PaneRegistry

define pane metadata and allowed regions

wrap existing panels in mount/unmount interfaces

remove hardcoded DOM lookups from pane code where necessary

Deliverables:

PaneRegistry

converted pane adapters:

AssetsPane

MissionsPane

InspectorPane

AlertsPane

TimelinePane

MacrogridPane

Success criteria:

any eligible pane can mount in a different region without breaking

Phase 3 — Replace Sidebar Tabs with Left Operations Rail

Goal:

move from tab sidebar to real left dock region

Tasks:

remove current 5-tab sidebar as the primary navigation model

define left-region default layout

expose assets + missions + inspector simultaneously

preserve collapsibility and resizing

Deliverables:

left operations rail layout

updated panel composition rules

optional internal tabs where needed

Success criteria:

assets, missions, and inspector can be visible together

left region width persists

old sidebar is no longer structurally required

Phase 4 — Bottom Region Upgrade

Goal:

turn bottom into a true dock region

Tasks:

mount timeline as default bottom pane

add tab support to bottom region

add placeholder panes:

command history

event log

ensure time controls remain global

Deliverables:

bottom dock region

timeline as default tab

command history placeholder pane

event log placeholder pane

Success criteria:

bottom region supports multiple panes without timeline losing function

Phase 5 — Implement Layout Persistence

Goal:

make the workspace feel like a real desktop tool

Tasks:

add serialized layout save/load

version layout schema

store region sizes, tabs, active panes, visibility

add reset-to-default action

add layout import/export placeholders

Deliverables:

persistent WorkspaceLayoutState

local storage or desktop-config persistence

reset layout action

Success criteria:

app restarts into the same layout

Phase 6 — Map Tool Controller Refactor

Goal:

normalize map interactions into explicit tools

Tasks:

create MapToolController

migrate:

select

track asset

set waypoint

macrogrid inspect

remove ad hoc click behavior from map glue code

add visual tool mode indicator in toolbar

Deliverables:

centralized map tool state

map tool API

tool registration pattern

updated toolbar integration

Success criteria:

all map interactions are mode-driven

map click behavior is deterministic and tool-specific

Phase 7 — Desktop Host Hardening

Goal:

prepare for larger .exe experience

Tasks:

persist window state

persist workspace state

improve startup orchestration

show backend connection/boot status cleanly

add menu hooks for layout actions

Deliverables:

improved desktop shell bootstrap

startup state screen

window state persistence

layout menu commands

Success criteria:

app behaves like a coherent local desktop tool, not just a webview

14. Deliverables the Agent Should Write First

Before major code changes, the agent should produce these docs:

14.1 workspace_shell_spec.md

Defines:

regions

allowed docking rules

splitter behavior

tab group behavior

default layout

14.2 pane_registry_spec.md

Defines:

all pane IDs

pane metadata

allowed regions

preferred sizes

mount contracts

14.3 layout_state_schema.md

Defines:

layout state structure

persistence rules

schema versioning

reset behavior

14.4 map_tool_controller_spec.md

Defines:

tool modes

transitions between tools

map event routing

preview overlays

how tool outputs become command drafts

14.5 desktop_host_spec.md

Defines:

app startup sequence

backend process lifecycle

settings storage

layout persistence location

window state handling

Only after those docs exist should the agent begin the shell refactor.

15. Hard Rules for the Agent

Do not rewrite Cesium rendering just to achieve docking.

Do not move business logic into the workspace shell.

Do not let pane modules assume fixed DOM placement.

Do not store layout data in operational AppState.

Do not let map clicks directly mutate live assets.

Do not keep the current tab sidebar as the long-term primary layout primitive.

Do not break the existing timeline/live/scrub behavior during shell migration.

Do not let the shell refactor bypass backend command validation.

16. Definition of Success

The workspace refactor is successful when:

The globe remains the stable center of the application.

The left operations rail is persistent and useful.

The timeline lives in a persistent bottom region.

Panes can be resized, collapsed, reordered, and re-docked within allowed regions.

The layout survives restart.

The map behaves through explicit tools, not ad hoc click handlers.

The app feels like a desktop mission workstation, not a fixed web dashboard.

17. Immediate Next Action for the Agent

The agent should now produce, in order:

workspace_shell_spec.md

pane_registry_spec.md

layout_state_schema.md

map_tool_controller_spec.md

desktop_host_spec.md

Only after those are complete should the agent begin implementing the workspace shell refactor.