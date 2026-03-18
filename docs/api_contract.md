# AMS API Contract

This document defines the REST and WebSocket interfaces between frontend and backend.

---

## 1. API Design Principles

- **REST** for CRUD operations and queries
- **WebSocket** for real-time event and state updates
- Backend is the source of truth — frontend emits intent, backend validates and transitions state
- All mutating operations return the updated entity and emit a domain event

---

## 2. REST Endpoints

Base URL: `http://localhost:8012/api/v1`

### 2.1 Assets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/assets` | List all assets |
| `GET` | `/assets/{id}` | Get asset by ID |
| `POST` | `/assets` | Register a new asset |
| `PATCH` | `/assets/{id}` | Update asset fields |
| `DELETE` | `/assets/{id}` | Deregister an asset |

#### `GET /assets`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by AssetStatus |
| `mode` | string | Filter by AssetMode |
| `health` | string | Filter by AssetHealth |
| `mission_id` | string | Filter by assigned mission |
| `capability` | string | Filter by capability tag |

Response:
```json
{
  "assets": [ { /* Asset object */ } ],
  "count": 20
}
```

#### `GET /assets/{id}`

Response: `Asset` object (see [domain_model.md](domain_model.md))

---

### 2.2 Missions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/missions` | List missions |
| `GET` | `/missions/{id}` | Get mission by ID |
| `POST` | `/missions` | Create a new mission |
| `PATCH` | `/missions/{id}` | Update mission fields |
| `POST` | `/missions/{id}/propose` | Submit mission for review |
| `POST` | `/missions/{id}/approve` | Approve a proposed mission |
| `POST` | `/missions/{id}/pause` | Pause an active mission |
| `POST` | `/missions/{id}/resume` | Resume a paused mission |
| `POST` | `/missions/{id}/abort` | Abort a mission |
| `POST` | `/missions/{id}/archive` | Archive a terminal mission |

#### `GET /missions`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `state` | string | Filter by MissionState |
| `priority` | string | Filter by Priority |
| `type` | string | Filter by MissionType |
| `asset_id` | string | Filter by assigned asset |

Response:
```json
{
  "missions": [ { /* Mission object */ } ],
  "count": 5
}
```

#### `POST /missions`

Request body:
```json
{
  "name": "Surveillance Alpha",
  "type": "surveillance",
  "priority": "normal",
  "objective": "Monitor zone 12-8 for activity",
  "constraints": {
    "start_time": "2026-03-16T10:00:00Z",
    "end_time": "2026-03-16T12:00:00Z",
    "geofences": ["gf_romania_border"],
    "max_assets": 3,
    "required_capabilities": ["camera_ir"]
  },
  "tags": ["routine", "zone-12"]
}
```

Response: Created `Mission` object (state = `draft`)

#### `POST /missions/{id}/approve`

Request body:
```json
{
  "approved_by": "operator_456"
}
```

Response: Updated `Mission` object (state = `approved`)

---

### 2.3 Tasks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/missions/{mission_id}/tasks` | List tasks for a mission |
| `GET` | `/tasks/{id}` | Get task by ID |
| `POST` | `/missions/{mission_id}/tasks` | Add task to a mission |
| `PATCH` | `/tasks/{id}` | Update task fields |
| `DELETE` | `/tasks/{id}` | Remove task from mission |

#### `POST /missions/{mission_id}/tasks`

Request body:
```json
{
  "type": "survey",
  "priority": "normal",
  "target": {
    "kind": "area",
    "data": {
      "polygon": [
        [25.0, 45.0], [25.5, 45.0],
        [25.5, 45.3], [25.0, 45.3]
      ]
    }
  },
  "service_time_sec": 600,
  "dependencies": [],
  "constraints": {
    "required_capabilities": ["camera_ir"],
    "min_battery_pct": 30.0
  }
}
```

Response: Created `Task` object (state = `waiting`)

---

### 2.4 Commands

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/commands` | List commands |
| `GET` | `/commands/{id}` | Get command by ID |
| `POST` | `/commands` | Create a new command |
| `POST` | `/commands/{id}/approve` | Approve a command |
| `POST` | `/commands/{id}/cancel` | Cancel a command |

#### `GET /commands`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `state` | string | Filter by CommandState |
| `type` | string | Filter by CommandType |
| `target_type` | string | Filter by CommandTargetType |
| `target_id` | string | Filter by target entity ID |

#### `POST /commands`

Request body:
```json
{
  "type": "move_to",
  "target_type": "asset",
  "target_id": "uav_07",
  "payload": {
    "destination": { "lon": 25.5, "lat": 45.3, "alt_m": 100.0 },
    "speed_mps": 15.0
  },
  "created_by": "operator_123"
}
```

Response: Created `Command` object (state = `proposed`)

#### `POST /commands/{id}/approve`

Request body:
```json
{
  "approved_by": "operator_456"
}
```

Response: Updated `Command` object (state = `approved`)

---

### 2.5 Timeline

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/timeline` | List timeline reservations |
| `GET` | `/timeline/{id}` | Get reservation by ID |
| `GET` | `/timeline/conflicts` | List detected conflicts |

#### `GET /timeline`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `asset_id` | string | Filter by asset |
| `mission_id` | string | Filter by mission |
| `start_after` | timestamp | Reservations starting after this time |
| `end_before` | timestamp | Reservations ending before this time |
| `status` | string | Filter by ReservationStatus |
| `source` | string | Filter by ReservationSource |

Response:
```json
{
  "reservations": [ { /* TimelineReservation object */ } ],
  "count": 15
}
```

---

### 2.6 Alerts

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/alerts` | List alerts |
| `GET` | `/alerts/{id}` | Get alert by ID |
| `POST` | `/alerts/{id}/acknowledge` | Acknowledge an alert |
| `POST` | `/alerts/{id}/clear` | Clear an alert |

#### `GET /alerts`

Query parameters:

| Param | Type | Description |
|-------|------|-------------|
| `state` | string | Filter by AlertState |
| `severity` | string | Filter by AlertSeverity |
| `type` | string | Filter by AlertType |
| `source_type` | string | Filter by AlertSourceType |
| `source_id` | string | Filter by source entity ID |

Response:
```json
{
  "alerts": [ { /* Alert object */ } ],
  "count": 3
}
```

---

### 2.7 Macro-Grid

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/macrogrid/zones` | Get current zone states |
| `GET` | `/macrogrid/recommendations` | Get active rebalance recommendations |
| `POST` | `/macrogrid/recommendations/{id}/convert` | Convert recommendation to draft mission |

---

## 3. Common Response Patterns

### Success

```json
{
  "status": "ok",
  "data": { /* entity or list */ }
}
```

### Validation Error (400)

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_TRANSITION",
    "message": "Cannot transition mission from 'draft' to 'active'",
    "details": {
      "current_state": "draft",
      "requested_state": "active",
      "valid_transitions": ["proposed"]
    }
  }
}
```

### Not Found (404)

```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Asset uav_99 not found"
  }
}
```

---

## 4. WebSocket Interface

Endpoint: `ws://localhost:8012/ws/stream`

### 4.1 Server → Client Messages

All domain events are broadcast as WebSocket messages:

```json
{
  "type": "asset.status_changed",
  "entity_id": "uav_12",
  "timestamp": "2026-03-16T10:30:00Z",
  "version": 42,
  "payload": {
    "old_status": "transiting",
    "new_status": "on_task",
    "reason": "Arrived at task target"
  }
}
```

See [event_catalog.md](event_catalog.md) for all event types and payload shapes.

### 4.2 Client → Server Messages

The WebSocket also accepts operator actions (for backwards compatibility with the existing prototype):

#### Demand Spike

```json
{
  "action": "spike",
  "lon": 25.5,
  "lat": 45.3
}
```

#### Move Drone (Legacy)

```json
{
  "action": "move_drone",
  "drone_id": "uav_07",
  "target_lon": 25.5,
  "target_lat": 45.3
}
```

#### Reset Queues

```json
{
  "action": "reset"
}
```

> **Note:** In the target architecture, mutating actions should be sent via REST `POST /commands` instead of WebSocket messages. The WebSocket client→server channel is retained for low-latency telemetry and simulation control only.

### 4.3 Connection Management

| Message Type | Direction | Purpose |
|-------------|-----------|---------|
| `connection.established` | server → client | Confirms WebSocket connected |
| `connection.heartbeat` | bidirectional | Keep-alive ping/pong |
| `connection.error` | server → client | Reports connection-level errors |

### 4.4 Subscription Model (Future)

Clients may subscribe to specific event categories:

```json
{
  "action": "subscribe",
  "channels": ["asset.*", "mission.state_changed", "alert.*"]
}
```

```json
{
  "action": "unsubscribe",
  "channels": ["asset.telemetry_received"]
}
```

---

## 5. Authentication (Placeholder)

Authentication and authorization are not implemented in the current prototype. Future phases will add:

- API key or JWT-based authentication
- Role-based access control (observer, operator, approver, admin)
- Per-endpoint authorization rules
- WebSocket authentication on connection

---

## 6. Cross-References

- Entity schemas: [domain_model.md](domain_model.md)
- State transitions triggered by API calls: [state_machines.md](state_machines.md)
- Event payloads delivered via WebSocket: [event_catalog.md](event_catalog.md)
- Timeline query details: [timeline_model.md](timeline_model.md)
