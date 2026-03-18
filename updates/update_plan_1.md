# AMS Architecture Restructuring Plan
## Mission Operations Platform Refactor
### Status: Pre-Implementation Design Document

---

# 1. Purpose

This document defines the target architecture for evolving the current UAV mission planner / swarm asset manager prototype into a more industry-grade mission operations platform.

The goal is **not** to replace low-level GCS/autopilot software such as QGroundControl, and **not** to compete with high-fidelity simulation tools such as STK.

The goal is to build a system that sits above execution and visualization layers:

- manages assets
- manages missions
- schedules actions over time
- tracks command lifecycle
- supports replay and operator workflows
- provides a flexible UI over shared operational state

The existing macro-grid rebalancing logic will be kept as-is for now and treated as an isolated background planning/recommendation service.

---

# 2. Product Definition

The system should be defined as:

> An event-driven mission operations platform for multi-UAV assets.

It is **not** just:
- a map application
- a drone visualizer
- a waypoint-click demo
- a swarm simulator in the narrow controls sense

The core operational loop is:

```text
observe → understand state → plan → approve → dispatch → monitor → replay

Everything in the architecture should support that loop.

3. Current Prototype Constraints

The current system already has useful pieces, but they are prototype-shaped:

backend/frontend split exists

Cesium-style visualization exists conceptually

inline per-drone control UI exists

desktop launcher exists

macro-grid imbalance and dispatch logic exists

However, the system currently lacks the following first-class concepts:

canonical asset state

mission objects

task scheduling

command lifecycle

timeline / temporal reasoning

event sourcing / replay

role-safe workflows

flexible multi-pane UI architecture

execution adapter abstraction

persistence model

The next implementation phase should fix structure first, then features.

4. Architectural Principles
4.1 Backend is the source of truth

The frontend must not own operational truth.

Frontend should:

render state

emit operator intent

subscribe to backend events

Backend should:

validate

persist

transition state

emit authoritative updates

4.2 Missions are higher-level than raw commands

A mission is not just "set waypoint".

Missions should express operator intent in domain terms.

4.3 Time is a first-class dimension

The platform must move from snapshot-based behavior to time-aware planning and execution.

4.4 Cesium is a view, not the system core

The map/globe must be one UI surface among several.

4.5 Commands must be explicit objects

Never let UI button clicks directly mutate live asset state without a command object and lifecycle.

4.6 Execution must be adapter-based

Core logic must not depend directly on the current simulator or a future MAVLink bridge.

4.7 Everything important must be replayable

This includes commands, mission transitions, alerts, and asset state changes.

5. Target System Layers
[ UI / Workspace Layer ]
    Cesium Map View
    Asset Panel
    Mission Panel
    Timeline Panel
    Inspector Panel
    Alerts Panel

[ Frontend Application State ]
    View state
    Selection state
    Filters
    Local interaction state
    WebSocket subscription state

[ API / Realtime Interface ]
    REST / WebSocket / Event stream

[ Core Backend Domain ]
    Asset Service
    Mission Service
    Command Service
    Timeline Service
    Alert Service
    Macro-Grid Integration Service

[ Persistence / Event Store ]
    Database
    Event log
    Snapshot store

[ Execution Adapters ]
    Simulator Adapter
    Telemetry Playback Adapter
    MAVLink / PX4 / ArduPilot Adapter (future)
6. Core Domain Model
6.1 Asset

Each UAV must have a canonical backend entity.

Required fields
Asset:
  id: string
  name: string
  type: string
  status: enum
  mode: enum
  position:
    lon: float
    lat: float
    alt_m: float
  velocity:
    vx_mps: float
    vy_mps: float
    vz_mps: float
  heading_deg: float
  battery_pct: float
  link_quality: float
  health: enum
  payload_state: string
  home_location:
    lon: float
    lat: float
    alt_m: float
  assigned_mission_id: string | null
  assigned_task_id: string | null
  last_telemetry_time: timestamp
  capabilities:
    - string
Status enum
idle
reserved
launching
transiting
on_task
returning
landing
charging
offline
degraded
lost
maintenance
Mode enum
manual
guided
auto
rtl
hold
simulated
6.2 Mission

A mission represents operator-level intent and should contain one or more tasks/phases.

Mission:
  id: string
  name: string
  type: enum
  priority: enum
  objective: string
  state: enum
  created_at: timestamp
  created_by: string
  approved_by: string | null
  constraints:
    start_time: timestamp | null
    end_time: timestamp | null
    geofences: [string]
    max_assets: int | null
    required_capabilities: [string]
  assigned_asset_ids: [string]
  task_ids: [string]
  tags: [string]
Mission state enum
draft
proposed
approved
queued
active
paused
completed
aborted
failed
archived
6.3 Task

Tasks are the executable units within a mission.

Task:
  id: string
  mission_id: string
  type: enum
  priority: enum
  state: enum
  target:
    kind: point | area | route | asset
    data: object
  service_time_sec: float | null
  earliest_start: timestamp | null
  latest_finish: timestamp | null
  assigned_asset_ids: [string]
  dependencies: [string]
  constraints:
    required_capabilities: [string]
    min_battery_pct: float | null
    geofence_ids: [string]
Task state enum
waiting
ready
assigned
transit
active
blocked
completed
failed
cancelled
6.4 Command

Every operator action becomes a first-class command.

Command:
  id: string
  type: enum
  target_type: enum
  target_id: string
  payload: object
  state: enum
  created_at: timestamp
  created_by: string
  approved_at: timestamp | null
  approved_by: string | null
  dispatched_at: timestamp | null
  acknowledged_at: timestamp | null
  completed_at: timestamp | null
  failure_reason: string | null
  correlation_id: string | null
Command state enum
proposed
validated
rejected
approved
queued
sent
acknowledged
active
completed
failed
cancelled
expired
6.5 Timeline Reservation

This is the scheduling backbone.

TimelineReservation:
  id: string
  asset_id: string
  mission_id: string | null
  task_id: string | null
  phase: enum
  start_time: timestamp
  end_time: timestamp
  status: enum
  source: planned | predicted | actual
Reservation phase enum
idle
launch
transit
hold
task_execution
return
recovery
charging
maintenance
6.6 Alert
Alert:
  id: string
  type: enum
  severity: info | warning | critical
  state: open | acknowledged | cleared
  created_at: timestamp
  source_type: asset | mission | task | command | system
  source_id: string
  message: string
  metadata: object
7. State Transition Rules

The agent should define and enforce valid state machines.

7.1 Asset transition examples
idle -> reserved
reserved -> launching
launching -> transiting
transiting -> on_task
on_task -> returning
returning -> landing
landing -> charging
charging -> idle
any -> degraded
any -> lost

Invalid transitions should be rejected at the backend service level.

7.2 Mission transition examples
draft -> proposed
proposed -> approved
approved -> queued
queued -> active
active -> paused
paused -> active
active -> completed
active -> aborted
7.3 Command transition examples
proposed -> validated
validated -> approved
approved -> queued
queued -> sent
sent -> acknowledged
acknowledged -> active
active -> completed
active -> failed
8. Event Model

The entire system should be event-driven internally.

8.1 Core event categories
asset.created
asset.updated
asset.status_changed
asset.telemetry_received

mission.created
mission.updated
mission.state_changed

task.created
task.updated
task.state_changed

command.created
command.validated
command.approved
command.sent
command.acknowledged
command.completed
command.failed

timeline.reservation_created
timeline.reservation_updated
timeline.conflict_detected

alert.created
alert.acknowledged
alert.cleared

macrogrid.recommendation_emitted
8.2 Event payload principles

Each event should include:

Event:
  id: string
  type: string
  timestamp: timestamp
  source_service: string
  entity_type: string
  entity_id: string
  version: int
  payload: object
8.3 Why this matters

This enables:

replay

audit

time-travel debugging

UI synchronization

multi-view consistency

future analytics

9. Backend Services
9.1 Asset Service

Responsibilities:

maintain canonical asset state

ingest telemetry

track health/link/battery

expose asset queries

emit asset events

9.2 Mission Service

Responsibilities:

create/edit/archive missions

manage task decomposition

transition mission/task state

validate capability matching

9.3 Command Service

Responsibilities:

receive operator intent

validate commands

enforce approvals

dispatch to execution adapters

track acknowledgements and completion

9.4 Timeline Service

Responsibilities:

maintain future reservations

estimate ETAs

detect resource conflicts

power timeline/replay UI

support simple what-if planning

9.5 Alert Service

Responsibilities:

generate alerts from state/rules

aggregate and de-duplicate

track alert acknowledgement/clearance

9.6 Macro-Grid Integration Service

Responsibilities:

keep the current macro-grid code isolated

ingest its rebalance recommendations

convert recommendations into optional operator-visible planning objects

never let macro-grid directly mutate execution state

This service should treat macro-grid output as:

suggestion

background planner recommendation

strategic rebalancing input

Not as direct command authority.

10. Execution Adapter Layer

The core system must not depend on one execution backend.

10.1 Required adapters
Simulator Adapter

connects to current fake/simulated asset layer

supports position update injection

supports command acknowledgement emulation

Playback Adapter

replays recorded telemetry/events

enables demo/replay/testing workflows

MAVLink Adapter (future)

translates approved commands into vehicle control messages

maps telemetry into canonical asset state

should remain behind adapter boundary

10.2 Adapter interface shape
class ExecutionAdapter:
    def send_command(command) -> AdapterResult: ...
    def fetch_asset_updates() -> list[TelemetryUpdate]: ...
    def get_connection_status() -> AdapterStatus: ...

The backend domain services must only know this interface, not implementation specifics.

11. Persistence Strategy
11.1 Minimum persistence components

relational database for current state

append-only event log for replay/audit

optional snapshots for faster restore

11.2 Store separately

current canonical asset state

missions/tasks/commands

timeline reservations

alerts

domain events

11.3 Do not rely on frontend memory

Operational state must survive refresh, reconnect, and desktop app restart.

12. API Design
12.1 API split

Use:

REST for CRUD and queries

WebSocket for realtime event/state updates

12.2 Example REST endpoints
GET    /assets
GET    /assets/{id}
GET    /missions
POST   /missions
GET    /missions/{id}
POST   /commands
GET    /timeline
GET    /alerts
POST   /missions/{id}/approve
POST   /commands/{id}/approve
12.3 Example WebSocket message types
{
  "type": "asset.updated",
  "entity_id": "uav_12",
  "payload": { ... }
}
{
  "type": "mission.state_changed",
  "entity_id": "mission_4",
  "payload": {
    "old_state": "approved",
    "new_state": "active"
  }
}
13. Frontend Architecture
13.1 Frontend role

Frontend should:

subscribe to backend state/events

render multiple coordinated views

maintain only local view state

emit operator intents through APIs

Frontend should not:

own command truth

own mission lifecycle truth

bypass backend validation

directly mutate live asset state

13.2 Frontend state separation
Global app state

selected asset

selected mission

visible layers

filters

time cursor

active workspace panel

current camera mode

Local component state

panel expansion

input drafts

form modals

hover state

Do not mix backend truth with local UI convenience state.

14. UI Composition Plan

The UI should become a workspace, not just a globe with overlays.

14.1 Required panes
A. Map / Globe View

Purpose:

spatial awareness

tracks

mission areas

geofences

route previews

macro-grid overlays

B. Asset Panel

Purpose:

list all assets

health/battery/link/status at a glance

filter/sort/search

jump to asset on map

C. Mission Panel

Purpose:

mission queue

mission states

priorities

readiness

approvals

D. Timeline Panel

Purpose:

reservations

ETAs

conflicts

planned future occupancy

replay scrubbing

E. Inspector Panel

Purpose:

context-sensitive details for selected asset/mission/task/command/alert

F. Alerts Panel

Purpose:

link loss

low battery

stale telemetry

mission delays

geofence violations

failed commands

15. UI Interaction Rules
15.1 Selection and context

Selection must be centralized:

one selected asset

one selected mission

one selected alert

one timeline cursor

The map, panels, and inspector must all react consistently to that selection.

15.2 Command creation

No button should directly perform vehicle action.

Button flow should be:

operator click
→ draft command
→ validate
→ optional approval
→ dispatch
→ show command state in UI
15.3 Inline card controls

Inline controls inside asset cards are fine, but they must only create commands or command drafts.

They must not own execution behavior.

15.4 Time navigation

The UI should support:

live mode

historical replay mode

future plan preview mode

16. Timeline / Scheduling Design
16.1 Why this is critical

Without time reasoning, the system remains a reactive map.

16.2 Initial timeline scope

Phase 1 timeline must support:

planned reservations per asset

estimated mission phase durations

future occupancy visualization

task overlap/conflict detection

playback over historical events

16.3 Scheduling primitives

Each asset can have reservations such as:

idle
launch
transit
task_execution
return
recovery
charging

These should be visualized in the timeline panel and linked to mission/task state.

16.4 Conflict detection examples

same asset double-booked

task scheduled after deadline

battery reserve below threshold

transit window impossible given current position/speed

17. Macro-Grid Treatment

The macro-grid logic is to remain frozen for now.

17.1 Position in system

Treat it as a background recommendation engine.

17.2 Inputs

current asset distribution

coarse demand signal

strategic imbalance info

17.3 Outputs

rebalance suggestions

recommended repositioning candidates

zone-level pressure indicators

17.4 Non-goals

Macro-grid must not:

directly assign missions

directly control individual UAVs

bypass approval/command workflow

18. Recommended Project Structure
ams/
  backend/
    app/
      api/
      domain/
        assets/
        missions/
        commands/
        timeline/
        alerts/
        macrogrid/
      services/
      adapters/
        simulator/
        playback/
        mavlink/
      persistence/
      events/
      schemas/
      main.py

  frontend/
    src/
      app/
      features/
        assets/
        missions/
        timeline/
        alerts/
        map/
        inspector/
      state/
      services/
      components/
      pages/
    public/

  docs/
    architecture.md
    domain_model.md
    api_contract.md
    event_catalog.md
    state_machines.md
    timeline_model.md
19. Documentation Deliverables the Agent Should Produce First

Before writing major new code, the agent should generate the following docs:

19.1 architecture.md

Describe:

system layers

service boundaries

backend/frontend responsibilities

adapter boundary

event flow

19.2 domain_model.md

Define:

Asset

Mission

Task

Command

Alert

TimelineReservation

With field definitions and enums.

19.3 state_machines.md

Define valid transitions for:

assets

missions

tasks

commands

alerts

19.4 event_catalog.md

Enumerate every event type and payload shape.

19.5 api_contract.md

Define:

REST endpoints

WebSocket message types

request/response schemas

19.6 timeline_model.md

Define:

reservation model

ETA rules

conflict detection rules

replay model

19.7 ui_workspace_spec.md

Define:

required panes

selection model

interactions

view synchronization rules

20. Implementation Phasing
Phase 0 — Structure First

Do not add flashy features yet.

Deliver:

architecture docs

domain model

state machines

API contracts

Phase 1 — Canonical Backend State

Deliver:

Asset Service

Mission Service skeleton

Command Service skeleton

persistence model

event emission basics

Phase 2 — Realtime Sync

Deliver:

WebSocket event stream

frontend app store

synchronized map + asset panel + inspector

Phase 3 — Mission Workflow

Deliver:

mission CRUD

task entities

approval flow

command lifecycle UI

Phase 4 — Timeline

Deliver:

timeline reservations

ETA estimates

conflict detection

replay mode

Phase 5 — Adapter Maturity

Deliver:

simulator adapter cleanup

playback adapter

future MAVLink adapter boundary

Phase 6 — Macro-Grid Reintegration

Deliver:

macro-grid recommendation panel

operator-visible rebalance suggestions

optional convert-to-mission workflow

21. Hard Rules for the Agent

Do not build more Cesium-specific logic until the domain model and event model exist.

Do not let frontend components directly own mission or command truth.

Do not add more direct-control UI shortcuts that bypass backend command objects.

Do not tightly couple simulator assumptions into core services.

Do not make the map the only operational interface.

Do not let macro-grid directly control individual assets.

Every major action must be replayable and auditable.

Time must be modeled explicitly, not implied by ad hoc timers.

22. Definition of Success

This refactor is successful when the platform can answer, cleanly and consistently:

What assets exist right now?

What is each asset doing right now?

What missions exist and what state are they in?

What is planned next over time?

What command was issued, by whom, and what happened?

What changed over time?

What should the operator look at next?

If the platform cannot answer those, it is still a demo.

23. Immediate Next Action for the Agent

The agent should now produce, in order:

architecture.md

domain_model.md

state_machines.md

event_catalog.md

api_contract.md

ui_workspace_spec.md

timeline_model.md

Only after those are complete should the agent begin code restructuring.