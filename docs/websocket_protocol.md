# AMC-Grid WebSocket Protocol

## Overview

AMC-Grid exposes a single WebSocket endpoint at `/ws`. All real-time communication —
simulation state broadcasts, drone commands, HITL approvals, and feed subscriptions —
flows through this endpoint. The server runs at 10 Hz and pushes full simulation state
to every connected DASHBOARD client each tick.

For machine-readable schema definitions see [`asyncapi.yaml`](asyncapi.yaml).

---

## Connection

```
ws://localhost:8000/ws      # development (no TLS)
wss://<host>:<port>/ws      # production (TLS)
```

### Limits

| Parameter | Value |
|-----------|-------|
| Max simultaneous connections | 20 |
| Max message size | 64 KB |
| Rate limit | 30 messages/second per client |
| Identification timeout | 2 seconds |

---

## Authentication

Authentication is optional. It is controlled by the `AUTH_ENABLED` environment variable.

When enabled, every client must send an `IDENTIFY` message within 2 seconds of connecting,
including a valid JWT token. Three token tiers are supported:

| Tier | Access |
|------|--------|
| `DASHBOARD` | Full operator access — send all commands |
| `SIMULATOR` | Simulator-only — forward drone feeds, no operator commands |
| `ADMIN` | Unrestricted access |

### Identification handshake

```json
{ "type": "IDENTIFY", "client_type": "DASHBOARD", "token": "tok_dashboard_abc123" }
```

If auth is disabled or the client does not send an `IDENTIFY` message, the first message
is treated as a command and the client is assigned DASHBOARD tier automatically.

**Close codes:**
- `4001` — Authentication failed (invalid/missing token when auth is enabled)
- `4003` — Origin not allowed
- `1013` — Maximum connections reached

---

## Message Format

### Client → Server (commands)

All command messages are JSON objects with an `action` field identifying the operation:

```json
{ "action": "<action_name>", ...parameters }
```

Some legacy messages use `type` instead of `action` (e.g. `SET_SCENARIO`, `SITREP_QUERY`).

### Server → Client (broadcasts and responses)

Server messages are JSON objects with a `type` field:

```json
{ "type": "<message_type>", ...payload }
```

The main broadcast uses `"type": "state"` and wraps the simulation data under a `data` key:

```json
{ "type": "state", "data": { ...simulation_state } }
```

---

## Server Broadcasts

### Simulation State (`type: state`)

Broadcast at 10 Hz to all DASHBOARD clients. Top-level fields in `data`:

| Field | Type | Description |
|-------|------|-------------|
| `autonomy_level` | string | Global autonomy: `MANUAL`, `SUPERVISED`, `AUTONOMOUS` |
| `coverage_mode` | string | Swarm coverage: `balanced`, `threat_adaptive` |
| `demo_mode` | boolean | Whether demo auto-pilot is active |
| `uavs` | array | Friendly drone states (see UAV Object below) |
| `targets` | array | Ground target states (see Target Object below) |
| `enemy_uavs` | array | Hostile UAV states |
| `zones` | array | Grid zone states (demand queue, UAV count, imbalance) |
| `flows` | array | Active demand flow lines between zones |
| `strike_board` | array | HITL nomination queue entries |
| `assessment` | object | Battlespace assessment (updated every 5 s) |
| `isr_queue` | array | Top-10 ISR priority targets |
| `swarm_tasks` | array | Active drone swarm assignments |
| `kill_chain` | object | F2T2EA phase counts across all targets |
| `environment` | object | Time of day, cloud cover, precipitation |
| `theater` | object | Active theater name and bounds |

#### UAV Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique drone ID |
| `lon`, `lat` | float | Current position (decimal degrees) |
| `mode` | string | `IDLE`, `SEARCH`, `FOLLOW`, `PAINT`, `INTERCEPT`, `SUPPORT`, `VERIFY`, `OVERWATCH`, `BDA`, `REPOSITIONING`, `RTB` |
| `altitude_m` | float | Altitude in meters |
| `sensor_type` | string | Primary sensor type |
| `sensors` | string[] | All equipped sensors |
| `heading_deg` | float | Current heading |
| `tracked_target_id` | int\|null | Primary tracked target |
| `tracked_target_ids` | int[] | All tracked target IDs |
| `fuel_hours` | float | Remaining fuel in hours |
| `autonomy_override` | string\|null | Per-drone autonomy override level |
| `pending_transition` | object\|null | Awaiting operator approval (SUPERVISED mode) |
| `fov_targets` | int[] | Target IDs in field of view |
| `sensor_quality` | float | Sensor effectiveness 0.0–1.0 |

#### Target Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique target ID |
| `lon`, `lat` | float | Current position |
| `type` | string | `SAM`, `TEL`, `TRUCK`, `CP`, `MANPADS`, `RADAR`, `C2_NODE`, `LOGISTICS`, `ARTILLERY`, `APC` |
| `detected` | bool | Whether target has been detected |
| `state` | string | `UNDETECTED` → `DETECTED` → `CLASSIFIED` → `VERIFIED` → `NOMINATED` |
| `fused_confidence` | float | Multi-sensor fused confidence 0.0–1.0 |
| `sensor_contributions` | array | Top-10 per-sensor confidence contributions |
| `time_in_state_sec` | float | Time elapsed in current state |
| `next_threshold` | float\|null | Confidence required to advance to next state |
| `threat_range_km` | float | Engagement threat radius |

---

## Quick Reference: All Client Actions

### Drone Control

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `scan_area` | `drone_id` | Release drone to autonomous SEARCH mode |
| `follow_target` | `drone_id`, `target_id` | Track a ground target |
| `paint_target` | `drone_id`, `target_id` | Laser-designate a target |
| `intercept_target` | `drone_id`, `target_id` | Intercept/engage a ground target |
| `intercept_enemy` | `uav_id`, `enemy_uav_id` | Intercept a hostile UAV |
| `cancel_track` | `drone_id` | Release drone from tracking, return to idle |
| `move_drone` | `drone_id`, `target_lon`, `target_lat` | Fly to waypoint |
| `spike` | `lon`, `lat` | Trigger demand spike at location |

### HITL Approvals

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `approve_nomination` | `entry_id` | Approve a strike board nomination |
| `reject_nomination` | `entry_id` | Reject a nomination (logged as override) |
| `retask_nomination` | `entry_id` | Return nomination for more ISR |
| `authorize_coa` | `entry_id`, `coa_id` | Authorize a specific COA |
| `reject_coa` | `entry_id` | Reject all proposed COAs |
| `verify_target` | `target_id` | Manually advance target to VERIFIED |

### Swarm

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `request_swarm` | `target_id` | Assign coordinated swarm to target |
| `release_swarm` | `target_id` | Release swarm, return drones to idle |

### Autonomy Control

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `set_autonomy_level` | `level` | Set global level: MANUAL/SUPERVISED/AUTONOMOUS |
| `set_action_autonomy` | `action`, `level` | Override level for specific action type |
| `force_manual` | — | Immediately force all autonomy to MANUAL |
| `set_drone_autonomy` | `drone_id` | Set per-drone override (omit `level` to clear) |
| `approve_transition` | `drone_id` | Approve pending mode transition (SUPERVISED) |
| `reject_transition` | `drone_id` | Reject pending mode transition |

### Configuration

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `set_coverage_mode` | `mode` | Set coverage: `balanced` or `threat_adaptive` |
| `set_roe` | `path` | Load ROE YAML from `roe/` directory |
| `get_roe` | — | Request current ROE rules (returns ROE_RULES) |
| `SET_SCENARIO` | — | Load theater on simulator (forwarded to SIMULATOR clients) |

### Intel Feeds

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `subscribe` | `feeds` | Subscribe to INTEL_FEED / COMMAND_FEED |
| `subscribe_sensor_feed` | `uav_ids` | Subscribe to 2Hz SENSOR_FEED for specific UAVs |

### Queries

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `sitrep_query` | — | Request AI situation report (returns SITREP_RESPONSE) |
| `generate_sitrep` | — | Alias for sitrep_query |
| `retask_sensors` | — | Request AI sensor retasking (returns RETASK_RESPONSE) |

### Persistence

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `save_checkpoint` | `mission_id` | Save simulation state checkpoint |
| `load_mission` | `mission_id` | Load checkpoint (returns MISSION_LOADED) |

### Simulation Control

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `reset` | — | Reset grid demand queues |

---

## Server → Client Message Types

| Type | Trigger | Description |
|------|---------|-------------|
| `state` | 10 Hz timer | Full simulation state |
| `HITL_UPDATE` | Nomination change | Strike board updated |
| `SITREP_RESPONSE` | `sitrep_query` | AI situation report |
| `RETASK_RESPONSE` | `retask_sensors` | AI sensor tasking orders |
| `CHECKPOINT_SAVED` | `save_checkpoint` | Checkpoint confirmation |
| `MISSION_LOADED` | `load_mission` | Loaded mission state |
| `ROE_RULES` | `get_roe` | Current ROE rule list |
| `ROE_UPDATED` | `set_roe` | ROE load confirmation |
| `FEED_HISTORY` | `subscribe` | Last 200 feed events on first subscription |
| `FEED_EVENT` | Feed activity | Live event on subscribed feed |
| `TACTICAL_ASSISTANT` | New detection | AI tactical recommendation |
| `ERROR` | Command failure | Validation or processing error |

---

## Intel Feeds

After calling `subscribe`, the server pushes live events as `FEED_EVENT` messages.

### INTEL_FEED — target state transitions

```json
{
  "type": "FEED_EVENT",
  "feed": "INTEL_FEED",
  "event": {
    "event": "VERIFIED",
    "target_id": 5,
    "target_type": "SAM",
    "from": "CLASSIFIED",
    "to": "VERIFIED",
    "summary": "Target 5 (SAM): CLASSIFIED -> VERIFIED"
  }
}
```

### COMMAND_FEED — operator actions

```json
{
  "type": "FEED_EVENT",
  "feed": "COMMAND_FEED",
  "event": {
    "action": "follow_target",
    "drone_id": 2,
    "target_id": 5,
    "source": "operator"
  }
}
```

### SENSOR_FEED — per-UAV detections at 2 Hz

Requires `subscribe_sensor_feed` with specific UAV IDs (max 50).

```json
{
  "type": "FEED_EVENT",
  "feed": "SENSOR_FEED",
  "event": {
    "uav_id": 1,
    "mode": "FOLLOW",
    "sensors": ["EO", "IR"],
    "lat": 44.31,
    "lon": 28.52,
    "detections": [
      { "target_id": 5, "target_type": "SAM", "confidence": 0.82, "sensor_type": "EO" }
    ]
  }
}
```

---

## Examples

### 1. Connect and identify

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'IDENTIFY',
    client_type: 'DASHBOARD',
    token: 'tok_dashboard_abc123'   // omit when auth is disabled
  }));
};
```

### 2. Receive simulation state

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'state') {
    const { uavs, targets, strike_board, kill_chain } = msg.data;
    // update UI...
  }
};
```

### 3. Command a drone to follow a target

```javascript
ws.send(JSON.stringify({
  action: 'follow_target',
  drone_id: 2,
  target_id: 5
}));
```

### 4. Approve a HITL nomination

```javascript
ws.send(JSON.stringify({
  action: 'approve_nomination',
  entry_id: 'nom-001',
  rationale: 'ROE satisfied, target confirmed',
  operator_id: 'op_alpha'
}));
```

The server will immediately broadcast a `HITL_UPDATE` to all DASHBOARD clients.

### 5. Subscribe to intel feeds

```javascript
ws.send(JSON.stringify({
  action: 'subscribe',
  feeds: ['INTEL_FEED', 'COMMAND_FEED']
}));
// Server sends FEED_HISTORY for each feed, then FEED_EVENT messages as events occur
```

### 6. Request a situation report

```javascript
ws.send(JSON.stringify({
  action: 'sitrep_query',
  query: 'What is the current threat posture in the eastern sector?'
}));
// Server sends SITREP_RESPONSE only to this client
```

---

## Error Handling

All errors are returned as `ERROR` messages to the requesting client only:

```json
{ "type": "ERROR", "message": "Missing required field: 'drone_id'", "action": "follow_target" }
```

Common error conditions:

| Condition | Message |
|-----------|---------|
| Missing required field | `Missing required field: '<name>'` |
| Wrong field type | `Field '<name>' must be <type>` |
| Invalid autonomy level | `Invalid autonomy level. Must be MANUAL, SUPERVISED, or AUTONOMOUS.` |
| Invalid coverage mode | `Invalid coverage mode '<mode>'. Must be one of: balanced, threat_adaptive` |
| Drone not found | `UAV <id> not found` |
| Message too large | `Message exceeds 64KB limit` |
| Rate limit exceeded | `Rate limit exceeded, message dropped` |
| Auth failure | `Authentication failed: invalid or missing token` |
| Unauthorized action | `Permission denied for action '<action>'` |
