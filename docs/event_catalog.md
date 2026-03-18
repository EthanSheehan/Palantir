# AMS Event Catalog

The system is event-driven internally. Every significant state change produces a domain event that is persisted to the event log and broadcast to WebSocket subscribers.

---

## 1. Event Envelope

All events share a common envelope structure:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique event identifier (UUID) |
| `type` | string | Event type (e.g., `asset.status_changed`) |
| `timestamp` | timestamp | When the event occurred (ISO 8601) |
| `source_service` | string | Service that emitted the event |
| `entity_type` | string | Type of entity (`asset`, `mission`, `task`, `command`, `timeline_reservation`, `alert`) |
| `entity_id` | string | ID of the affected entity |
| `version` | int | Monotonically increasing version per entity |
| `payload` | object | Event-type-specific data |

---

## 2. Asset Events

Source service: `asset_service`

### `asset.created`

Emitted when a new asset is registered.

```json
{
  "asset": { /* full Asset object */ }
}
```

### `asset.updated`

Emitted when asset fields change (excluding status and telemetry-only updates).

```json
{
  "changes": {
    "field_name": { "old": "...", "new": "..." }
  }
}
```

### `asset.status_changed`

Emitted when the asset status transitions. See [state_machines.md](state_machines.md) for valid transitions.

```json
{
  "old_status": "idle",
  "new_status": "reserved",
  "reason": "Assigned to mission_42"
}
```

### `asset.telemetry_received`

Emitted on each telemetry update ingestion.

```json
{
  "position": { "lon": 25.0, "lat": 45.0, "alt_m": 120.0 },
  "velocity": { "vx_mps": 5.0, "vy_mps": 3.0, "vz_mps": 0.0 },
  "heading_deg": 45.0,
  "battery_pct": 82.5,
  "link_quality": 0.95
}
```

---

## 3. Mission Events

Source service: `mission_service`

### `mission.created`

```json
{
  "mission": { /* full Mission object */ }
}
```

### `mission.updated`

```json
{
  "changes": {
    "field_name": { "old": "...", "new": "..." }
  }
}
```

### `mission.state_changed`

```json
{
  "old_state": "approved",
  "new_state": "active",
  "triggered_by": "operator_123",
  "reason": "Resources available, execution started"
}
```

---

## 4. Task Events

Source service: `mission_service`

### `task.created`

```json
{
  "task": { /* full Task object */ }
}
```

### `task.updated`

```json
{
  "changes": {
    "field_name": { "old": "...", "new": "..." }
  }
}
```

### `task.state_changed`

```json
{
  "old_state": "transit",
  "new_state": "active",
  "asset_id": "uav_07",
  "reason": "Asset arrived at task target"
}
```

---

## 5. Command Events

Source service: `command_service`

### `command.created`

```json
{
  "command": { /* full Command object */ }
}
```

### `command.validated`

```json
{
  "command_id": "cmd_123",
  "validation_result": "pass",
  "checks_performed": ["target_exists", "asset_available", "within_geofence"]
}
```

### `command.approved`

```json
{
  "command_id": "cmd_123",
  "approved_by": "operator_456",
  "approval_type": "manual"
}
```

### `command.sent`

```json
{
  "command_id": "cmd_123",
  "adapter": "simulator",
  "dispatched_at": "2026-03-16T10:30:00Z"
}
```

### `command.acknowledged`

```json
{
  "command_id": "cmd_123",
  "adapter": "simulator",
  "acknowledged_at": "2026-03-16T10:30:01Z"
}
```

### `command.completed`

```json
{
  "command_id": "cmd_123",
  "completed_at": "2026-03-16T10:35:00Z",
  "result": { /* command-specific result data */ }
}
```

### `command.failed`

```json
{
  "command_id": "cmd_123",
  "failed_at": "2026-03-16T10:31:00Z",
  "failure_reason": "Adapter timeout: no acknowledgement within 30s",
  "recoverable": false
}
```

---

## 6. Timeline Events

Source service: `timeline_service`

### `timeline.reservation_created`

```json
{
  "reservation": { /* full TimelineReservation object */ }
}
```

### `timeline.reservation_updated`

```json
{
  "reservation_id": "res_789",
  "changes": {
    "end_time": {
      "old": "2026-03-16T11:00:00Z",
      "new": "2026-03-16T11:15:00Z"
    }
  }
}
```

### `timeline.conflict_detected`

```json
{
  "conflict_type": "double_booking",
  "asset_id": "uav_03",
  "reservation_a_id": "res_100",
  "reservation_b_id": "res_101",
  "overlap_start": "2026-03-16T10:30:00Z",
  "overlap_end": "2026-03-16T10:45:00Z",
  "message": "Asset uav_03 double-booked between 10:30 and 10:45"
}
```

---

## 7. Alert Events

Source service: `alert_service`

### `alert.created`

```json
{
  "alert": { /* full Alert object */ }
}
```

### `alert.acknowledged`

```json
{
  "alert_id": "alert_456",
  "acknowledged_by": "operator_123",
  "acknowledged_at": "2026-03-16T10:32:00Z"
}
```

### `alert.cleared`

```json
{
  "alert_id": "alert_456",
  "cleared_at": "2026-03-16T10:40:00Z",
  "cleared_by": "system",
  "reason": "Condition resolved: battery above threshold"
}
```

---

## 8. Macro-Grid Events

Source service: `macrogrid_service`

### `macrogrid.recommendation_emitted`

```json
{
  "recommendation_id": "rec_001",
  "type": "rebalance",
  "source_zone": { "x_idx": 12, "y_idx": 8, "lon": 25.5, "lat": 45.2 },
  "target_zone": { "x_idx": 14, "y_idx": 9, "lon": 25.9, "lat": 45.4 },
  "suggested_asset_count": 2,
  "pressure_delta": 3.5,
  "confidence": 0.85,
  "expires_at": "2026-03-16T11:00:00Z"
}
```

---

## 9. Event Type Summary

| Event Type | Source Service | Entity Type |
|------------|---------------|-------------|
| `asset.created` | asset_service | asset |
| `asset.updated` | asset_service | asset |
| `asset.status_changed` | asset_service | asset |
| `asset.telemetry_received` | asset_service | asset |
| `mission.created` | mission_service | mission |
| `mission.updated` | mission_service | mission |
| `mission.state_changed` | mission_service | mission |
| `task.created` | mission_service | task |
| `task.updated` | mission_service | task |
| `task.state_changed` | mission_service | task |
| `command.created` | command_service | command |
| `command.validated` | command_service | command |
| `command.approved` | command_service | command |
| `command.sent` | command_service | command |
| `command.acknowledged` | command_service | command |
| `command.completed` | command_service | command |
| `command.failed` | command_service | command |
| `timeline.reservation_created` | timeline_service | timeline_reservation |
| `timeline.reservation_updated` | timeline_service | timeline_reservation |
| `timeline.conflict_detected` | timeline_service | timeline_reservation |
| `alert.created` | alert_service | alert |
| `alert.acknowledged` | alert_service | alert |
| `alert.cleared` | alert_service | alert |
| `macrogrid.recommendation_emitted` | macrogrid_service | macrogrid |

---

## 10. Usage

All events enable:

- **Replay** — reconstruct system state at any point in time
- **Audit** — trace who did what and when
- **Time-travel debugging** — step through historical event sequences
- **UI synchronization** — keep all frontend views consistent
- **Multi-view consistency** — multiple operators see the same state
- **Future analytics** — derive metrics and patterns from event history

---

## 11. Cross-References

- Entity definitions and enums: [domain_model.md](domain_model.md)
- Valid state transitions triggering events: [state_machines.md](state_machines.md)
- WebSocket delivery of events: [api_contract.md](api_contract.md)
