# AMS Domain Model

This document defines all core domain entities, their fields, enumerations, and relationships.

---

## 1. Asset

Each UAV is represented as a canonical backend entity.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique asset identifier |
| `name` | string | Human-readable name |
| `type` | string | Asset type (e.g., "quadrotor", "fixed_wing") |
| `status` | AssetStatus | Current operational status |
| `mode` | AssetMode | Current control mode |
| `position.lon` | float | Longitude (degrees) |
| `position.lat` | float | Latitude (degrees) |
| `position.alt_m` | float | Altitude (meters above ground) |
| `velocity.vx_mps` | float | Velocity X component (m/s) |
| `velocity.vy_mps` | float | Velocity Y component (m/s) |
| `velocity.vz_mps` | float | Velocity Z component (m/s) |
| `heading_deg` | float | Heading (degrees, 0 = North) |
| `battery_pct` | float | Battery level (0.0–100.0) |
| `link_quality` | float | Communication link quality (0.0–1.0) |
| `health` | AssetHealth | Overall health assessment |
| `payload_state` | string | Current payload status description |
| `home_location.lon` | float | Home longitude |
| `home_location.lat` | float | Home latitude |
| `home_location.alt_m` | float | Home altitude |
| `assigned_mission_id` | string \| null | Currently assigned mission |
| `assigned_task_id` | string \| null | Currently assigned task |
| `last_telemetry_time` | timestamp | Last telemetry receipt time |
| `capabilities` | string[] | List of capability tags |

### AssetStatus Enum

| Value | Description |
|-------|-------------|
| `idle` | Available, no assignment |
| `reserved` | Allocated to a mission but not yet launched |
| `launching` | In launch sequence |
| `transiting` | En route to task location |
| `on_task` | Executing assigned task |
| `returning` | Returning to base/home |
| `landing` | In landing sequence |
| `charging` | Battery charging |
| `offline` | Not communicating |
| `degraded` | Operational but with reduced capability |
| `lost` | Communication lost, status unknown |
| `maintenance` | Under maintenance, not available |

### AssetMode Enum

| Value | Description |
|-------|-------------|
| `manual` | Direct operator control |
| `guided` | Operator-guided waypoint following |
| `auto` | Autonomous mission execution |
| `rtl` | Return to launch |
| `hold` | Position hold |
| `simulated` | Running in simulation |

### AssetHealth Enum

| Value | Description |
|-------|-------------|
| `nominal` | All systems normal |
| `warning` | Minor issues detected |
| `critical` | Major issues, reduced capability |
| `failed` | Non-operational |

---

## 2. Mission

A mission represents operator-level intent containing one or more tasks/phases.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique mission identifier |
| `name` | string | Human-readable name |
| `type` | MissionType | Category of mission |
| `priority` | Priority | Mission priority level |
| `objective` | string | Free-text mission objective |
| `state` | MissionState | Current lifecycle state |
| `created_at` | timestamp | Creation time |
| `created_by` | string | Creator identifier |
| `approved_by` | string \| null | Approver identifier |
| `constraints.start_time` | timestamp \| null | Earliest allowed start |
| `constraints.end_time` | timestamp \| null | Latest allowed completion |
| `constraints.geofences` | string[] | Applicable geofence IDs |
| `constraints.max_assets` | int \| null | Maximum assets to assign |
| `constraints.required_capabilities` | string[] | Required asset capabilities |
| `assigned_asset_ids` | string[] | Assets assigned to this mission |
| `task_ids` | string[] | Ordered list of task IDs |
| `tags` | string[] | Arbitrary classification tags |

### MissionType Enum

| Value | Description |
|-------|-------------|
| `surveillance` | Area surveillance / monitoring |
| `delivery` | Payload delivery |
| `inspection` | Infrastructure inspection |
| `search_rescue` | Search and rescue operations |
| `rebalance` | Macro-grid rebalancing |
| `custom` | User-defined mission type |

### MissionState Enum

| Value | Description |
|-------|-------------|
| `draft` | Being composed, not yet submitted |
| `proposed` | Submitted for review |
| `approved` | Reviewed and approved |
| `queued` | Waiting for resource availability |
| `active` | Currently executing |
| `paused` | Temporarily suspended |
| `completed` | Successfully finished |
| `aborted` | Manually terminated |
| `failed` | Terminated due to error |
| `archived` | Moved to historical archive |

### Priority Enum

| Value | Description |
|-------|-------------|
| `critical` | Immediate, overrides normal scheduling |
| `high` | Elevated priority |
| `normal` | Standard priority |
| `low` | Background / non-urgent |

---

## 3. Task

Tasks are the executable units within a mission.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique task identifier |
| `mission_id` | string | Parent mission ID |
| `type` | TaskType | Kind of task |
| `priority` | Priority | Task priority level |
| `state` | TaskState | Current lifecycle state |
| `target.kind` | TargetKind | Target geometry type |
| `target.data` | object | Target-specific data (coordinates, polygon, route, asset ID) |
| `service_time_sec` | float \| null | Expected time to complete task on-site |
| `earliest_start` | timestamp \| null | Earliest allowed start |
| `latest_finish` | timestamp \| null | Deadline |
| `assigned_asset_ids` | string[] | Assets executing this task |
| `dependencies` | string[] | Task IDs that must complete first |
| `constraints.required_capabilities` | string[] | Required asset capabilities |
| `constraints.min_battery_pct` | float \| null | Minimum battery to begin |
| `constraints.geofence_ids` | string[] | Applicable geofences |

### TaskType Enum

| Value | Description |
|-------|-------------|
| `goto` | Navigate to a point |
| `loiter` | Hold position for a duration |
| `survey` | Area survey pattern |
| `deliver` | Payload drop-off |
| `inspect` | Point inspection |
| `return_home` | Return to home location |
| `reposition` | Macro-grid rebalancing move |
| `custom` | User-defined task type |

### TaskState Enum

| Value | Description |
|-------|-------------|
| `waiting` | Dependencies not yet met |
| `ready` | Dependencies met, awaiting assignment |
| `assigned` | Asset allocated |
| `transit` | Asset en route to task target |
| `active` | Task being executed on-site |
| `blocked` | Blocked by external condition |
| `completed` | Successfully finished |
| `failed` | Terminated due to error |
| `cancelled` | Manually cancelled |

### TargetKind Enum

| Value | Description |
|-------|-------------|
| `point` | Single coordinate (lon, lat, alt) |
| `area` | Polygon boundary |
| `route` | Ordered list of waypoints |
| `asset` | Another asset (for formation, escort, etc.) |

---

## 4. Command

Every operator action becomes a first-class command with full lifecycle tracking.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique command identifier |
| `type` | CommandType | Kind of command |
| `target_type` | CommandTargetType | What the command targets |
| `target_id` | string | ID of the target entity |
| `payload` | object | Command-specific parameters |
| `state` | CommandState | Current lifecycle state |
| `created_at` | timestamp | Creation time |
| `created_by` | string | Creator identifier |
| `approved_at` | timestamp \| null | Approval time |
| `approved_by` | string \| null | Approver identifier |
| `dispatched_at` | timestamp \| null | Dispatch time to adapter |
| `acknowledged_at` | timestamp \| null | Adapter acknowledgement time |
| `completed_at` | timestamp \| null | Completion time |
| `failure_reason` | string \| null | Reason for failure (if failed) |
| `correlation_id` | string \| null | Links related commands |

### CommandType Enum

| Value | Description |
|-------|-------------|
| `move_to` | Navigate asset to waypoint |
| `hold_position` | Stop and hold current position |
| `return_home` | Return to home location |
| `launch` | Initiate launch sequence |
| `land` | Initiate landing sequence |
| `start_task` | Begin task execution |
| `abort_task` | Abort current task |
| `set_mode` | Change asset control mode |
| `start_mission` | Activate a mission |
| `pause_mission` | Pause a mission |
| `abort_mission` | Abort a mission |

### CommandTargetType Enum

| Value | Description |
|-------|-------------|
| `asset` | Targets a specific asset |
| `mission` | Targets a mission |
| `task` | Targets a task |

### CommandState Enum

| Value | Description |
|-------|-------------|
| `proposed` | Created, awaiting validation |
| `validated` | Passed validation checks |
| `rejected` | Failed validation |
| `approved` | Approved for execution |
| `queued` | In execution queue |
| `sent` | Dispatched to execution adapter |
| `acknowledged` | Adapter confirmed receipt |
| `active` | Currently executing |
| `completed` | Successfully finished |
| `failed` | Execution failed |
| `cancelled` | Manually cancelled |
| `expired` | Timed out without completion |

---

## 5. TimelineReservation

Reservations form the scheduling backbone, representing planned asset occupancy over time.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique reservation identifier |
| `asset_id` | string | Reserved asset |
| `mission_id` | string \| null | Associated mission |
| `task_id` | string \| null | Associated task |
| `phase` | ReservationPhase | Type of activity reserved |
| `start_time` | timestamp | Reservation start |
| `end_time` | timestamp | Reservation end |
| `status` | ReservationStatus | Current reservation status |
| `source` | ReservationSource | How the reservation was created |

### ReservationPhase Enum

| Value | Description |
|-------|-------------|
| `idle` | Asset idle / standby |
| `launch` | Launch sequence |
| `transit` | En route to destination |
| `hold` | Position hold |
| `task_execution` | On-task activity |
| `return` | Return transit |
| `recovery` | Post-mission recovery |
| `charging` | Battery charging |
| `maintenance` | Scheduled maintenance |

### ReservationStatus Enum

| Value | Description |
|-------|-------------|
| `planned` | Future reservation |
| `active` | Currently in progress |
| `completed` | Finished |
| `cancelled` | Cancelled before execution |
| `conflict` | Overlaps with another reservation |

### ReservationSource Enum

| Value | Description |
|-------|-------------|
| `planned` | Manually or automatically planned |
| `predicted` | Estimated by the system |
| `actual` | Recorded from execution |

See [timeline_model.md](timeline_model.md) for ETA rules, conflict detection, and replay model.

---

## 6. Alert

Alerts notify operators of conditions requiring attention.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique alert identifier |
| `type` | AlertType | Category of alert |
| `severity` | AlertSeverity | Severity level |
| `state` | AlertState | Current alert state |
| `created_at` | timestamp | Creation time |
| `source_type` | AlertSourceType | What generated the alert |
| `source_id` | string | ID of the source entity |
| `message` | string | Human-readable alert message |
| `metadata` | object | Additional context data |

### AlertType Enum

| Value | Description |
|-------|-------------|
| `link_loss` | Communication link lost |
| `low_battery` | Battery below threshold |
| `stale_telemetry` | Telemetry not received within expected interval |
| `mission_delay` | Mission behind schedule |
| `geofence_violation` | Asset outside allowed boundary |
| `command_failed` | Command execution failed |
| `conflict_detected` | Timeline scheduling conflict |
| `health_degraded` | Asset health degraded |
| `system_error` | Internal system error |

### AlertSeverity Enum

| Value | Description |
|-------|-------------|
| `info` | Informational |
| `warning` | Requires attention |
| `critical` | Requires immediate action |

### AlertState Enum

| Value | Description |
|-------|-------------|
| `open` | Active, unacknowledged |
| `acknowledged` | Operator has seen it |
| `cleared` | Resolved / no longer active |

### AlertSourceType Enum

| Value | Description |
|-------|-------------|
| `asset` | Generated by asset state |
| `mission` | Generated by mission state |
| `task` | Generated by task state |
| `command` | Generated by command lifecycle |
| `system` | Generated by system internals |

---

## 7. Entity Relationships

```
Mission 1──* Task
Mission *──* Asset          (assigned_asset_ids)
Task    *──* Asset          (assigned_asset_ids)
Task    *──* Task           (dependencies)
Command  ──1 Asset|Mission|Task  (target_type + target_id)
TimelineReservation ──1 Asset
TimelineReservation ──? Mission
TimelineReservation ──? Task
Alert   ──1 Asset|Mission|Task|Command|System  (source_type + source_id)
```

- A **Mission** contains an ordered list of **Tasks**
- **Assets** can be assigned to missions and individual tasks
- **Tasks** can declare dependencies on other tasks within the same mission
- **Commands** target a single entity (asset, mission, or task)
- **TimelineReservations** always belong to an asset, optionally linked to a mission and task
- **Alerts** reference the entity that triggered them

---

## 8. Cross-References

- State transitions for all entities: [state_machines.md](state_machines.md)
- Events emitted on state changes: [event_catalog.md](event_catalog.md)
- API for CRUD operations: [api_contract.md](api_contract.md)
- Timeline reservation details: [timeline_model.md](timeline_model.md)
