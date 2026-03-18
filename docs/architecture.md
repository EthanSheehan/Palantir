# AMS Architecture

## 1. System Overview

The Advanced Macro Systems (AMS) platform is an event-driven mission operations system for multi-UAV assets. It manages assets, missions, scheduling, command lifecycle, replay, and operator workflows through a layered architecture with clear separation of concerns.

The core operational loop:

```
observe → understand state → plan → approve → dispatch → monitor → replay
```

---

## 2. System Layers

```
┌─────────────────────────────────────────────────────────┐
│                  UI / Workspace Layer                    │
│  Cesium Map View │ Asset Panel │ Mission Panel           │
│  Timeline Panel  │ Inspector   │ Alerts Panel            │
├─────────────────────────────────────────────────────────┤
│              Frontend Application State                  │
│  View state │ Selection │ Filters │ Time cursor          │
│  WebSocket subscription state │ Camera mode              │
├─────────────────────────────────────────────────────────┤
│              API / Realtime Interface                    │
│  REST (CRUD & queries) │ WebSocket (event stream)       │
├─────────────────────────────────────────────────────────┤
│                Core Backend Domain                       │
│  Asset Service │ Mission Service │ Command Service       │
│  Timeline Service │ Alert Service │ Macro-Grid Service   │
├─────────────────────────────────────────────────────────┤
│              Persistence / Event Store                   │
│  Relational DB │ Append-only event log │ Snapshot store  │
├─────────────────────────────────────────────────────────┤
│                Execution Adapters                        │
│  Simulator Adapter │ Playback Adapter │ MAVLink (future) │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Architectural Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Backend is source of truth** | Frontend renders state and emits intent; backend validates, persists, transitions state, and emits authoritative updates. |
| 2 | **Missions above raw commands** | Missions express operator intent in domain terms, not low-level vehicle instructions. |
| 3 | **Time is first-class** | The platform models time explicitly via timeline reservations and scheduling, not ad hoc timers. |
| 4 | **Cesium is a view, not the core** | The map/globe is one UI surface among several in a multi-pane workspace. |
| 5 | **Commands are explicit objects** | Every operator action becomes a command with a full lifecycle — no direct UI-to-vehicle mutation. |
| 6 | **Execution is adapter-based** | Core logic depends on an abstract adapter interface, not specific simulators or MAVLink. |
| 7 | **Everything important is replayable** | Commands, mission transitions, alerts, and asset state changes are persisted as events. |

---

## 4. Backend / Frontend Responsibilities

### Backend Responsibilities

- Validate all incoming operator intents and commands
- Persist canonical state (assets, missions, tasks, commands, timeline, alerts)
- Enforce state machine transitions (reject invalid transitions)
- Emit authoritative domain events via WebSocket
- Dispatch approved commands to execution adapters
- Run background services (alert generation, conflict detection, macro-grid recommendations)
- Maintain append-only event log for replay/audit

### Frontend Responsibilities

- Subscribe to backend state and events via WebSocket
- Render multiple coordinated views (map, panels, inspector, timeline)
- Maintain only local view state (selection, filters, camera, panel expansion)
- Emit operator intents through REST API calls
- Never own command, mission, or asset truth
- Never bypass backend validation
- Never directly mutate live asset state

---

## 5. Service Boundaries

### 5.1 Asset Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Canonical asset state |
| **Responsibilities** | Maintain asset registry, ingest telemetry, track health/link/battery, expose asset queries |
| **Emits** | `asset.created`, `asset.updated`, `asset.status_changed`, `asset.telemetry_received` |
| **Depends on** | Execution adapters (for telemetry ingestion) |

### 5.2 Mission Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Mission and Task entities |
| **Responsibilities** | Create/edit/archive missions, manage task decomposition, transition mission/task state, validate capability matching |
| **Emits** | `mission.created`, `mission.updated`, `mission.state_changed`, `task.created`, `task.updated`, `task.state_changed` |
| **Depends on** | Asset Service (capability queries), Timeline Service (reservation requests) |

### 5.3 Command Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Command lifecycle |
| **Responsibilities** | Receive operator intent, validate commands, enforce approvals, dispatch to execution adapters, track acknowledgements and completion |
| **Emits** | `command.created`, `command.validated`, `command.approved`, `command.sent`, `command.acknowledged`, `command.completed`, `command.failed` |
| **Depends on** | Execution adapters (for dispatch), Asset Service (for validation) |

### 5.4 Timeline Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Timeline reservations, scheduling |
| **Responsibilities** | Maintain future reservations, estimate ETAs, detect resource conflicts, power timeline/replay UI, support what-if planning |
| **Emits** | `timeline.reservation_created`, `timeline.reservation_updated`, `timeline.conflict_detected` |
| **Depends on** | Asset Service (positions, speeds), Mission Service (task definitions) |

### 5.5 Alert Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Alert lifecycle |
| **Responsibilities** | Generate alerts from state/rules, aggregate and de-duplicate, track acknowledgement/clearance |
| **Emits** | `alert.created`, `alert.acknowledged`, `alert.cleared` |
| **Depends on** | All other services (monitors state for alert conditions) |

### 5.6 Macro-Grid Integration Service

| Aspect | Detail |
|--------|--------|
| **Owns** | Macro-grid recommendation pipeline |
| **Responsibilities** | Keep macro-grid code isolated, ingest rebalance recommendations, convert to operator-visible planning objects |
| **Emits** | `macrogrid.recommendation_emitted` |
| **Constraints** | Must NOT directly assign missions, control individual UAVs, or bypass approval/command workflow |
| **Output treated as** | Suggestion / background planner recommendation / strategic rebalancing input |

---

## 6. Execution Adapter Layer

The core system must not depend on one execution backend. All adapters implement a common interface:

```python
class ExecutionAdapter:
    def send_command(command) -> AdapterResult: ...
    def fetch_asset_updates() -> list[TelemetryUpdate]: ...
    def get_connection_status() -> AdapterStatus: ...
```

### Adapter Implementations

| Adapter | Purpose |
|---------|---------|
| **Simulator Adapter** | Connects to current simulated asset layer. Supports position update injection and command acknowledgement emulation. |
| **Playback Adapter** | Replays recorded telemetry/events. Enables demo, replay, and testing workflows. |
| **MAVLink Adapter** (future) | Translates approved commands into vehicle control messages. Maps telemetry into canonical asset state. |

Backend domain services interact only with the `ExecutionAdapter` interface, never implementation specifics.

---

## 7. Event Flow

```
Operator Action (frontend)
    │
    ▼
REST API call (POST /commands)
    │
    ▼
Command Service
    ├── validate → emit command.validated
    ├── approve  → emit command.approved
    └── dispatch → Execution Adapter
                      │
                      ▼
                  Adapter Result
                      │
                      ▼
              Command Service
                  ├── emit command.acknowledged
                  └── emit command.completed / command.failed
                          │
                          ▼
                  WebSocket broadcast
                          │
                          ▼
                  Frontend updates views
```

All events are:
1. Persisted to the append-only event log
2. Broadcast to connected WebSocket clients
3. Available for replay and audit

See [event_catalog.md](event_catalog.md) for the full event type enumeration.

---

## 8. Persistence Strategy

### Components

| Store | Purpose |
|-------|---------|
| **Relational database** | Current canonical state (assets, missions, tasks, commands, timeline reservations, alerts) |
| **Append-only event log** | Full history for replay, audit, and time-travel debugging |
| **Snapshot store** (optional) | Faster state restoration from known checkpoints |

### Separation Rules

- Current canonical state is stored in the relational DB
- All domain events are appended to the event log
- Frontend memory is NOT a persistence layer — operational state must survive refresh, reconnect, and desktop app restart

---

## 9. Cross-References

- Domain entities: [domain_model.md](domain_model.md)
- State transitions: [state_machines.md](state_machines.md)
- Event types and payloads: [event_catalog.md](event_catalog.md)
- REST and WebSocket API: [api_contract.md](api_contract.md)
- UI workspace layout: [ui_workspace_spec.md](ui_workspace_spec.md)
- Timeline and scheduling: [timeline_model.md](timeline_model.md)
