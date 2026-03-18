# AMS Timeline Model

This document defines the timeline reservation model, ETA estimation rules, conflict detection, scheduling primitives, and replay model.

---

## 1. Purpose

Without time reasoning, the system remains a reactive map. The timeline model enables:

- Planned future asset occupancy
- Estimated mission phase durations
- Resource conflict detection
- Operator scheduling decisions
- Historical replay and audit

---

## 2. Reservation Model

Each reservation represents a time block allocated to an asset for a specific activity.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique reservation identifier |
| `asset_id` | string | Reserved asset |
| `mission_id` | string \| null | Associated mission |
| `task_id` | string \| null | Associated task |
| `phase` | ReservationPhase | Type of activity |
| `start_time` | timestamp | Reservation start |
| `end_time` | timestamp | Reservation end |
| `status` | ReservationStatus | Current status |
| `source` | ReservationSource | How this reservation was created |

See [domain_model.md](domain_model.md) for full enum definitions.

### Scheduling Primitives (ReservationPhase)

Each asset's timeline is composed of these phase blocks:

| Phase | Description | Typical Duration |
|-------|-------------|------------------|
| `idle` | Standby, available | Variable |
| `launch` | Launch sequence | 30s – 2min |
| `transit` | En route to destination | Distance / speed |
| `hold` | Position hold awaiting further instruction | Variable |
| `task_execution` | On-site task activity | Task-defined (service_time_sec) |
| `return` | Return transit to base | Distance / speed |
| `recovery` | Post-mission recovery procedures | 1 – 5 min |
| `charging` | Battery charging | Battery-dependent |
| `maintenance` | Scheduled maintenance | Variable |

### Reservation Lifecycle

```
planned → active → completed
planned → cancelled
active  → completed
```

Reservations in `conflict` status require operator resolution.

---

## 3. ETA Estimation Rules

### 3.1 Transit Time

```
transit_time_sec = distance_m / speed_mps
```

Where:
- `distance_m` = great-circle distance from current position to target
- `speed_mps` = asset cruise speed (default: ~500 m/s based on SPEED_DEG_PER_SEC ≈ 0.005 deg/s)

### 3.2 Mission Duration Estimate

```
total_estimate = launch_time
               + transit_to_first_task
               + sum(task.service_time_sec for task in mission.tasks)
               + sum(inter_task_transit_times)
               + return_transit
               + recovery_time
```

### 3.3 Phase Start/End Estimation

When a mission is queued, the Timeline Service generates predicted reservations:

1. **Launch** — starts at mission start time, duration from launch estimate
2. **Transit** — starts at launch end, duration from distance/speed calculation
3. **Task execution** — starts at transit arrival, duration from `task.service_time_sec`
4. **Inter-task transit** — between consecutive tasks
5. **Return** — starts at last task end, duration from distance/speed to home
6. **Recovery** — starts at landing, fixed or configurable duration
7. **Charging** — starts at recovery end, duration estimated from battery drain

### 3.4 ETA Updates

- ETAs are recalculated whenever:
  - Asset telemetry updates position/speed
  - Task is added, removed, or reordered
  - Mission is paused or resumed
  - A conflict is detected
- The `source` field distinguishes `planned`, `predicted`, and `actual` reservations

---

## 4. Conflict Detection Rules

The Timeline Service continuously checks for conflicts:

### 4.1 Double Booking

**Rule:** An asset cannot have overlapping reservations (except `idle` blocks).

```
conflict if:
  reservation_a.asset_id == reservation_b.asset_id
  AND reservation_a.phase != "idle"
  AND reservation_b.phase != "idle"
  AND reservation_a.start_time < reservation_b.end_time
  AND reservation_b.start_time < reservation_a.end_time
```

**Alert:** `timeline.conflict_detected` event with `conflict_type: "double_booking"`

### 4.2 Deadline Violation

**Rule:** A task's predicted completion must not exceed its `latest_finish` constraint.

```
conflict if:
  task.latest_finish IS NOT NULL
  AND predicted_completion_time > task.latest_finish
```

**Alert:** `alert.created` with `type: "mission_delay"`

### 4.3 Battery Threshold Violation

**Rule:** An asset's predicted battery level at task start must meet the task's `min_battery_pct` constraint.

```
conflict if:
  task.constraints.min_battery_pct IS NOT NULL
  AND predicted_battery_at_task_start < task.constraints.min_battery_pct
```

Battery drain estimate:
```
battery_drain_pct = transit_time_sec * drain_rate_per_sec
predicted_battery = current_battery_pct - battery_drain_pct
```

**Alert:** `alert.created` with `type: "low_battery"`

### 4.4 Transit Impossibility

**Rule:** The transit time to reach a task must not exceed the available time window.

```
conflict if:
  transit_time_sec > (task.latest_finish - current_time - task.service_time_sec)
```

This means the asset physically cannot reach the task location and complete it before the deadline.

**Alert:** `timeline.conflict_detected` event with `conflict_type: "transit_impossible"`

### 4.5 Conflict Resolution

Conflicts are surfaced to the operator, not auto-resolved. The operator can:

1. Reassign the task to a different asset
2. Adjust the mission timeline
3. Cancel or defer the conflicting task
4. Override (acknowledge and proceed despite conflict)

---

## 5. Replay Model

The timeline supports historical replay using the persisted event log.

### 5.1 State Reconstruction

To reconstruct state at time T:

1. Load the most recent snapshot before T (if snapshots exist)
2. Replay all events from snapshot time to T in order
3. Present the reconstructed state to the UI

### 5.2 Playback Controls

| Control | Description |
|---------|-------------|
| Play | Advance time cursor at selected speed |
| Pause | Freeze time cursor |
| Speed | 1x, 2x, 5x, 10x playback speed |
| Scrub | Drag timeline cursor to jump to specific time |
| Step | Advance to next event |
| Jump to Live | Return to real-time mode |

### 5.3 Replay Scope

Replayable elements:
- Asset positions and status changes
- Mission and task state transitions
- Command lifecycle events
- Alert creation and resolution
- Timeline reservation changes
- Macro-grid recommendation emissions

### 5.4 Replay vs. Live Data

| Aspect | Live Mode | Replay Mode |
|--------|-----------|-------------|
| Data source | WebSocket stream | Event log |
| Time cursor | Current time (auto-advancing) | User-controlled |
| Mutations allowed | Yes (commands, approvals) | No (read-only) |
| Update frequency | 10 Hz | Event-driven (variable) |

---

## 6. What-If Planning

The Timeline Service supports previewing hypothetical scenarios:

### 6.1 Scenario Creation

1. Operator creates a draft mission with tasks
2. Timeline Service generates predicted reservations without committing them
3. Predicted reservations are overlaid on the timeline in a distinct visual style (dashed borders)
4. Conflicts with existing reservations are highlighted

### 6.2 Scenario Comparison

- Multiple what-if scenarios can be previewed simultaneously
- Each scenario uses a different visual indicator
- The operator selects the preferred scenario and commits it (converting to `planned` reservations)

---

## 7. Timeline Visualization

See [ui_workspace_spec.md](ui_workspace_spec.md) for full UI details. Summary:

- **Swimlanes:** One horizontal lane per asset
- **Blocks:** Colored by ReservationPhase
- **Time axis:** Scrollable, zoomable
- **Current time:** Vertical marker line
- **Conflicts:** Red highlight on overlapping blocks
- **Predictions:** Dashed borders for estimated future blocks
- **What-if:** Semi-transparent overlay for hypothetical scenarios

---

## 8. Cross-References

- Reservation entity definition: [domain_model.md](domain_model.md)
- Reservation status transitions: [state_machines.md](state_machines.md)
- Timeline events: [event_catalog.md](event_catalog.md)
- Timeline API endpoints: [api_contract.md](api_contract.md)
- Timeline panel UI: [ui_workspace_spec.md](ui_workspace_spec.md)
