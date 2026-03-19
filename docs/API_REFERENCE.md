# Palantir C2 API Reference

**Last Updated: 2026-03-19**

Quick reference for all API endpoints and WebSocket messages. For full interactive documentation, run the system and visit `http://localhost:8000/docs`.

## Overview

The Palantir API consists of:
- **HTTP REST endpoints** for static configuration
- **WebSocket stream** for real-time simulation state and bidirectional commands
- **Async agents** for AI-driven reasoning

All endpoints use JSON. WebSocket messages follow the format: `{"type": "...", "payload": {...}}`.

## REST Endpoints

### Health & Status

#### GET `/api/theaters`
List available theater configurations.

**Response:**
```json
{
  "theaters": ["romania", "south_china_sea", "baltic"]
}
```

**Use Case**: Verify backend is responding, load theater selector UI.

**Status Codes**:
- `200 OK` — Backend healthy
- `500 Internal Server Error` — Theater loading failed

---

### Theater Management

#### POST `/api/theater`
Switch active theater (resets simulation state).

**Request:**
```json
{
  "theater": "south_china_sea"
}
```

**Response:**
```json
{
  "status": "switched",
  "theater": "south_china_sea",
  "bounds": {
    "north": 22.5,
    "south": 15.0,
    "east": 120.0,
    "west": 110.0
  }
}
```

**Use Case**: Theater selector dropdown, scenario reset.

**Status Codes**:
- `200 OK` — Theater switched successfully
- `400 Bad Request` — Invalid theater name
- `500 Internal Server Error` — Theater loading failed

---

#### POST `/api/environment`
Set weather/time conditions affecting sensor performance.

**Request:**
```json
{
  "time_of_day": "dawn",  // "dawn", "day", "dusk", "night"
  "cloud_cover": 0.3,      // 0.0 - 1.0 (0=clear, 1=overcast)
  "precipitation": 0.0     // 0.0 - 1.0 (0=none, 1=heavy rain)
}
```

**Response:**
```json
{
  "status": "updated",
  "environment": {
    "time_of_day": "dawn",
    "cloud_cover": 0.3,
    "precipitation": 0.0,
    "visibility_impact": 0.15
  }
}
```

**Use Case**: Mission scenario setup, environmental modeling.

**Status Codes**:
- `200 OK` — Environment updated
- `400 Bad Request` — Invalid parameters
- `422 Unprocessable Entity` — Validation error

---

#### POST `/api/sitrep`
Generate situation report (text summary).

**Request:**
```json
{
  "query": "What is the current tactical situation?",
  "filter": {
    "threat_level_min": "medium",
    "region": "north_sector"
  }
}
```

**Response:**
```json
{
  "sitrep": "Current tactical situation: 3 SAM systems detected in north sector...",
  "timestamp": "2026-03-17T22:45:00Z",
  "threats_summary": {
    "high": 2,
    "medium": 5,
    "low": 8
  }
}
```

**Use Case**: Operator briefings, SITREP panel in UI.

**Status Codes**:
- `200 OK` — SITREP generated
- `400 Bad Request` — Invalid query
- `500 Internal Server Error` — Agent inference failed (uses fallback)

---

## WebSocket API

### Connection

**Endpoint:** `ws://localhost:8000/ws` (or `wss://...` for HTTPS)

**Connection Flow:**
```
1. Client connects to WebSocket
2. Client sends {"client_type": "DASHBOARD"} or {"client_type": "SIMULATOR"}
3. Server broadcasts full state at 10Hz
```

**Client Types**:
- `DASHBOARD` — Frontend (receives full state, sends user actions)
- `SIMULATOR` — Drone simulator (receives state, sends telemetry)

---

### Server → Client Messages

#### `state` (Full State Update)
Broadcasted every 100ms (10Hz).

**Message:**
```json
{
  "type": "state",
  "payload": {
    "simulation_time": 3600.5,
    "tick": 36005,
    "drones": [
      {
        "id": "UAV-1",
        "position": [46.0, 24.5],
        "altitude": 2500,
        "heading": 45,
        "mode": "search",
        "fuel": 0.75,
        "status": "operational"
      }
    ],
    "targets": [
      {
        "id": "SAM-1",
        "position": [45.2, 24.8],
        "type": "SAM",
        "confidence": 0.85,
        "threat_level": "high",
        "last_seen": 3599.8
      }
    ],
    "zones": [
      {
        "id": "north_sector",
        "coverage": 0.95,
        "imbalance": -0.05
      }
    ],
    "strike_board": {
      "pending_nominations": [
        {
          "nomination_id": "nom-1",
          "target_id": "SAM-1",
          "recommended_by": "strategy_analyst",
          "priority": "HIGH",
          "status": "awaiting_approval"
        }
      ],
      "pending_coas": [
        {
          "coa_id": "coa-1",
          "nomination_id": "nom-1",
          "recommended_uav": "UAV-1",
          "engagement_type": "strike",
          "estimated_bda": "target_destroyed",
          "status": "awaiting_authorization"
        }
      ]
    }
  }
}
```

**Frequency**: Every 100ms (10Hz)

**Use Case**: Update 3D map, drone list, enemy list, strike board

---

#### `ASSISTANT_MESSAGE` (AI Agent Notification)
Sent when agents detect significant events.

**Message:**
```json
{
  "type": "ASSISTANT_MESSAGE",
  "payload": {
    "level": "INFO",
    "agent": "isr_observer",
    "message": "New target detected: SAM system at 45.2°N 24.8°E",
    "timestamp": "2026-03-17T22:45:23Z"
  }
}
```

**Levels**: `INFO`, `WARNING`, `CRITICAL`

**Agents**: `isr_observer`, `strategy_analyst`, `tactical_planner`, `effectors_agent`, `pattern_analyzer`, `ai_tasking_manager`, `battlespace_manager`, `synthesis_query_agent`, `performance_auditor`

**Use Case**: Tactical AIP Assistant message feed

---

#### `HITL_UPDATE` (Strike Board Status Change)
Sent when nomination or COA status changes.

**Message:**
```json
{
  "type": "HITL_UPDATE",
  "payload": {
    "event": "nomination_approved",
    "nomination_id": "nom-1",
    "target_id": "SAM-1",
    "operator_action": "approved",
    "timestamp": "2026-03-17T22:45:30Z"
  }
}
```

**Events**:
- `nomination_approved` / `nomination_rejected`
- `coa_authorized` / `coa_rejected`
- `strike_executed`
- `strike_aborted`

**Use Case**: Update strike board UI, operator action audit

---

#### `SITREP_RESPONSE` (Situation Report Result)
Response to `/api/sitrep` or WebSocket SITREP query.

**Message:**
```json
{
  "type": "SITREP_RESPONSE",
  "payload": {
    "query_id": "q-12345",
    "sitrep": "Current tactical situation: 8 threats detected...",
    "timestamp": "2026-03-17T22:45:35Z"
  }
}
```

**Use Case**: Operator SITREP panel, commander briefing

---

### Client → Server Messages (User Actions)

#### `spike`
Mark/unmark target for investigation.

**Message:**
```json
{
  "type": "spike",
  "payload": {
    "target_id": "SAM-1",
    "action": "spike"  // "spike" or "unspike"
  }
}
```

---

#### `move_drone`
Reposition UAV (manual control override).

**Message:**
```json
{
  "type": "move_drone",
  "payload": {
    "drone_id": "UAV-1",
    "destination": [46.5, 25.0],
    "altitude": 3000
  }
}
```

---

#### `scan_area`
Command drone to enter SEARCH mode — constant-rate circular loiter over an area.

**Message:**
```json
{
  "type": "scan_area",
  "payload": {
    "drone_id": "UAV-1",
    "position": [46.0, 24.5]
  }
}
```

---

#### `follow_target`
Enable camera following (drone stays centered).

**Message:**
```json
{
  "type": "follow_target",
  "payload": {
    "drone_id": "UAV-1",
    "target_id": "SAM-1"
  }
}
```

---

#### `paint_target`
Command drone to enter PAINT mode — tight ~1km orbit with laser designation. Sets target state to LOCKED.

**Message:**
```json
{
  "type": "paint_target",
  "payload": {
    "drone_id": "UAV-1",
    "target_id": "SAM-1"
  }
}
```

---

#### `intercept_target`
Command drone to enter INTERCEPT mode — direct approach at 1.5x speed, ~300m danger-close orbit. Sets target state to LOCKED.

**Message:**
```json
{
  "type": "intercept_target",
  "payload": {
    "drone_id": "UAV-1",
    "target_id": "SAM-1"
  }
}
```

---

#### `cancel_track`
Stop tracking a target.

**Message:**
```json
{
  "type": "cancel_track",
  "payload": {
    "target_id": "SAM-1"
  }
}
```

---

#### `approve_nomination`
Operator approves target nomination (HITL Gate 1).

**Message:**
```json
{
  "type": "approve_nomination",
  "payload": {
    "nomination_id": "nom-1",
    "operator_id": "op-john"
  }
}
```

---

#### `reject_nomination`
Operator rejects target nomination.

**Message:**
```json
{
  "type": "reject_nomination",
  "payload": {
    "nomination_id": "nom-1",
    "reason": "Insufficient intel",
    "operator_id": "op-john"
  }
}
```

---

#### `authorize_coa`
Operator authorizes course of action (HITL Gate 2).

**Message:**
```json
{
  "type": "authorize_coa",
  "payload": {
    "coa_id": "coa-1",
    "operator_id": "op-john"
  }
}
```

---

#### `reject_coa`
Operator rejects course of action.

**Message:**
```json
{
  "type": "reject_coa",
  "payload": {
    "coa_id": "coa-1",
    "reason": "Insufficient collateral analysis",
    "operator_id": "op-john"
  }
}
```

---

#### `sitrep_query`
Request a situation report.

**Message:**
```json
{
  "type": "sitrep_query",
  "payload": {
    "query": "Status of north sector",
    "filter": {"threat_level_min": "medium"}
  }
}
```

Response will be sent as `SITREP_RESPONSE` message.

---

#### `verify_target`
Manually fast-track a CLASSIFIED target to VERIFIED (operator override).

**Message:**
```json
{
  "type": "verify_target",
  "payload": {
    "target_id": 5
  }
}
```

**Precondition**: Target must be in `CLASSIFIED` state. If target is not CLASSIFIED, the action is ignored.

---

#### `retask_sensors`
Request sensor retasking optimization.

**Message:**
```json
{
  "type": "retask_sensors",
  "payload": {
    "priority_target": "SAM-1",
    "available_drones": ["UAV-1", "UAV-2"]
  }
}
```

---

## Data Models

### Detection
```json
{
  "detection_id": "det-12345",
  "sensor_source": "uav_radar",
  "threat_id": "threat-1",
  "location": [46.0, 24.5],
  "confidence": 0.85,
  "timestamp": "2026-03-17T22:45:15Z"
}
```

---

### TargetClassification
```json
{
  "target_id": "SAM-1",
  "unit_type": "SAM",
  "confidence": 0.92,
  "threat_level": "high",
  "behavior": "stationary",
  "last_updated": "2026-03-17T22:45:20Z"
}
```

---

### TargetNomination
```json
{
  "nomination_id": "nom-1",
  "target_id": "SAM-1",
  "recommended_by": "strategy_analyst",
  "priority": "HIGH",
  "justification": "Poses immediate threat to friendly forces",
  "status": "awaiting_approval"
}
```

---

### CourseOfAction
```json
{
  "coa_id": "coa-1",
  "nomination_id": "nom-1",
  "recommended_uav": "UAV-1",
  "engagement_type": "strike",
  "estimated_bda": "target_destroyed",
  "collateral_risk": "low",
  "reasoning": "Clear engagement window, minimal civilian presence",
  "status": "awaiting_authorization"
}
```

---

## Error Handling

### Error Response Format
```json
{
  "type": "error",
  "payload": {
    "error_code": "INVALID_THEATER",
    "message": "Theater 'atlantis' not found",
    "timestamp": "2026-03-17T22:45:40Z"
  }
}
```

### Common Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `INVALID_CLIENT_TYPE` | Client type not recognized | Send valid `client_type` |
| `CONNECTION_LIMIT_EXCEEDED` | Too many clients connected | Disconnect older client |
| `RATE_LIMIT_EXCEEDED` | Sending too many messages | Reduce message frequency |
| `INVALID_THEATER` | Theater name not found | Check theater list |
| `TARGET_NOT_FOUND` | Target ID not in simulation | Verify target exists |
| `DRONE_NOT_FOUND` | Drone ID not in simulation | Verify drone exists |
| `INVALID_ACTION` | Message type not recognized | Check message format |
| `INTERNAL_SERVER_ERROR` | Backend error (see logs) | Check backend logs |

---

## Usage Examples

### Python Client
```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Register as dashboard client
        await websocket.send(json.dumps({
            "client_type": "DASHBOARD"
        }))

        # Receive state updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'state':
                print(f"Drones: {len(data['payload']['drones'])}")
                print(f"Targets: {len(data['payload']['targets'])}")
            elif data['type'] == 'ASSISTANT_MESSAGE':
                print(f"AIP: {data['payload']['message']}")

asyncio.run(connect())
```

### JavaScript Client
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({client_type: "DASHBOARD"}));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'state') {
    updateMap(data.payload.drones, data.payload.targets);
  } else if (data.type === 'ASSISTANT_MESSAGE') {
    displayMessage(data.payload);
  } else if (data.type === 'HITL_UPDATE') {
    updateStrikeBoard(data.payload);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

### cURL (Testing)
```bash
# Check backend health
curl http://localhost:8000/api/theaters | jq .

# Get available theaters
curl -s http://localhost:8000/api/theaters | jq '.theaters[]'

# Switch theater
curl -X POST http://localhost:8000/api/theater \
  -H "Content-Type: application/json" \
  -d '{"theater": "south_china_sea"}'

# Request SITREP
curl -X POST http://localhost:8000/api/sitrep \
  -H "Content-Type: application/json" \
  -d '{"query": "Current tactical situation"}'
```

---

## Rate Limiting

- **WebSocket messages**: 30 per second per client
- **REST requests**: No explicit limit (use reasonable intervals)
- **Concurrent connections**: Max 20 WebSocket clients

If limits exceeded, server returns `RATE_LIMIT_EXCEEDED` error.

---

## Authentication

Currently, **no authentication required** (development mode).

For production, add authentication middleware:
```python
# In api_main.py
@app.middleware("http")
async def verify_auth(request, call_next):
    token = request.headers.get("Authorization")
    # Verify token...
    response = await call_next(request)
    return response
```

---

## Support & Documentation

- **Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`
- **Source**: `src/python/api_main.py` (main WebSocket handler)
- **Schemas**: `src/python/schemas/ontology.py` (data models)

---

## WebSocket Testing Tools

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8000/ws

# Send message (type in console)
{"client_type": "DASHBOARD"}

# Receive state updates (JSON output)
```

---

## State Payload Reference

The `state` message broadcast at 10Hz contains the full simulation state. Below is the exact structure of each sub-object within the payload.

### UAV Object

Each entry in the `uavs` array:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique UAV identifier (e.g. `"UAV-1"`) |
| `lon` | float | Longitude in decimal degrees (WGS-84) |
| `lat` | float | Latitude in decimal degrees (WGS-84) |
| `mode` | string | Current flight mode (see below) |
| `altitude_m` | float | Altitude in meters above ground level |
| `sensor_type` | string | Sensor payload type (e.g. `"EO/IR"`, `"RADAR"`, `"SIGINT"`) |
| `heading_deg` | float | Current heading in degrees (0-360, 0=North, clockwise) |
| `tracked_target_id` | string or null | ID of target being tracked, null if none |
| `fuel_hours` | float | Remaining fuel in hours |

**UAV Modes**: `IDLE` (hold position), `SEARCH` (circular loiter over zone), `FOLLOW` (loose ~2km orbit tracking target), `PAINT` (tight ~1km orbit with laser lock), `INTERCEPT` (direct approach at 1.5x speed, ~300m danger-close orbit), `REPOSITIONING` (zone rebalance at 3x turn rate), `RTB` (low fuel return to base)

### Target Object

Each entry in the `targets` array:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique target identifier (e.g. `"SAM-1"`) |
| `lon` | float | Longitude in decimal degrees (WGS-84) |
| `lat` | float | Latitude in decimal degrees (WGS-84) |
| `type` | string | Target classification (see below) |
| `detected` | bool | Whether the target has been detected by any sensor |
| `state` | string | Current kill chain state (see Target State Machine) |
| `detection_confidence` | float | Confidence level 0.0-1.0 |
| `detected_by_sensor` | string or null | Sensor type that detected this target |
| `is_emitting` | bool | Whether target is actively emitting (radar/comms) |
| `heading_deg` | float | Movement heading in degrees (0-360) |
| `tracked_by_uav_id` | string or null | ID of UAV currently tracking this target |
| `fused_confidence` | float | Multi-sensor fused confidence 0.0-1.0 (complementary fusion) |
| `sensor_count` | int | Number of distinct sensor types currently observing this target |
| `sensor_contributions` | array | Per-sensor breakdown: `[{uav_id, sensor_type, confidence}]` |
| `time_in_state_sec` | float | Seconds the target has been in its current verification state |
| `next_threshold` | float or null | Confidence threshold needed for next verification state advance (null if at terminal state) |

**Target Types**: `SAM`, `TEL`, `TRUCK`, `CP`, `MANPADS`, `RADAR`, `C2_NODE`, `LOGISTICS`, `ARTILLERY`, `APC`

### Zone Object

Each entry in the `zones` array:

| Field | Type | Description |
|-------|------|-------------|
| `x_idx` | int | Grid column index |
| `y_idx` | int | Grid row index |
| `lon` | float | Center longitude of zone |
| `lat` | float | Center latitude of zone |
| `width` | float | Zone width in degrees |
| `height` | float | Zone height in degrees |
| `queue` | int | Number of unscanned targets in zone |
| `uav_count` | int | Number of UAVs currently in zone |
| `imbalance` | float | Coverage imbalance score (positive = under-covered, drives repositioning) |

### Flow Object

Each entry in the `flows` array represents a UAV-to-target tracking link:

| Field | Type | Description |
|-------|------|-------------|
| `source` | [float, float] | `[lon, lat]` of the UAV |
| `target` | [float, float] | `[lon, lat]` of the tracked target |

### Environment Object

| Field | Type | Description |
|-------|------|-------------|
| `time_of_day` | float | Simulation time of day, 0-24 (decimal hours) |
| `cloud_cover` | float | Cloud cover fraction, 0.0 (clear) to 1.0 (overcast) |
| `precipitation` | float | Precipitation intensity, 0.0 (none) to 1.0 (heavy rain) |

### Theater Object

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Active theater name (e.g. `"romania"`, `"south_china_sea"`, `"baltic"`) |
| `bounds` | object | Geographic bounding box with `min_lon`, `max_lon`, `min_lat`, `max_lat` (all floats) |

### Full Payload Example

```json
{
  "type": "state",
  "payload": {
    "uavs": [
      {
        "id": "UAV-1",
        "lon": 24.5,
        "lat": 46.0,
        "mode": "SEARCH",
        "altitude_m": 2500,
        "sensor_type": "EO/IR",
        "heading_deg": 135.2,
        "tracked_target_id": null,
        "fuel_hours": 3.4
      }
    ],
    "targets": [
      {
        "id": "SAM-1",
        "lon": 24.8,
        "lat": 45.2,
        "type": "SAM",
        "detected": true,
        "state": "CLASSIFIED",
        "detection_confidence": 0.85,
        "detected_by_sensor": "EO/IR",
        "is_emitting": true,
        "heading_deg": 0.0,
        "tracked_by_uav_id": null,
        "fused_confidence": 0.88,
        "sensor_count": 2,
        "sensor_contributions": [
          {"uav_id": 1, "sensor_type": "EO_IR", "confidence": 0.7},
          {"uav_id": 3, "sensor_type": "SAR", "confidence": 0.6}
        ],
        "time_in_state_sec": 8.3,
        "next_threshold": 0.7
      }
    ],
    "zones": [
      {
        "x_idx": 0,
        "y_idx": 0,
        "lon": 24.0,
        "lat": 45.5,
        "width": 1.0,
        "height": 0.5,
        "queue": 2,
        "uav_count": 1,
        "imbalance": -0.3
      }
    ],
    "flows": [
      {
        "source": [24.5, 46.0],
        "target": [24.8, 45.2]
      }
    ],
    "environment": {
      "time_of_day": 14.5,
      "cloud_cover": 0.2,
      "precipitation": 0.0
    },
    "theater": {
      "name": "romania",
      "bounds": {
        "min_lon": 22.0,
        "max_lon": 30.0,
        "min_lat": 43.5,
        "max_lat": 48.5
      }
    }
  }
}
```

---

## Target State Machine

Targets progress through kill chain states as the F2T2EA pipeline advances. Each target's `state` field reflects its current position in the chain.

### Verification States (automated pipeline)

Targets first pass through the verification pipeline before entering the kill chain:

```
DETECTED → CLASSIFIED → VERIFIED → NOMINATED
```

| State | Advance Condition |
|-------|-------------------|
| `DETECTED` → `CLASSIFIED` | `fused_confidence >= classify_confidence` (per-type threshold) |
| `CLASSIFIED` → `VERIFIED` | `fused_confidence >= verify_confidence` AND (`sensor_count >= 2` OR `time_in_state >= sustained_sec`) |
| `VERIFIED` → `NOMINATED` | ISR pipeline picks up target for nomination |

Targets regress one state if no sensors observe them for `regression_timeout_sec`. Operators can manually fast-track CLASSIFIED → VERIFIED via `verify_target` action.

### Kill Chain States

| State | Description |
|-------|-------------|
| `UNDETECTED` | Target exists in simulation but has not been sensed |
| `DETECTED` | Sensor contact established, position known |
| `CLASSIFIED` | Target type confirmed via fused confidence threshold |
| `VERIFIED` | Multi-source corroboration complete |
| `NOMINATED` | Strategy Analyst has recommended the target for engagement |
| `LOCKED` | UAV in PAINT or INTERCEPT mode, laser designation active |
| `ENGAGED` | Strike authorized and executed |
| `DESTROYED` | BDA confirms target destroyed |
| `DAMAGED` | BDA confirms target damaged but not destroyed |
| `ESCAPED` | Target evaded engagement or tracking was lost post-strike |

### Transitions

```
UNDETECTED ──→ DETECTED          (sensor detection, confidence threshold met)
    DETECTED ──→ CLASSIFIED       (fused_confidence >= classify threshold)
  CLASSIFIED ──→ VERIFIED         (fused_confidence >= verify AND multi-sensor OR sustained time)
  CLASSIFIED ──→ VERIFIED         (operator manual verify_target action)
    VERIFIED ──→ NOMINATED        (ISR pipeline nomination, HITL Gate 1)
   NOMINATED ──→ LOCKED           (UAV enters PAINT or INTERCEPT mode)
      LOCKED ──→ ENGAGED          (strike authorized via HITL Gate 2)
     ENGAGED ──→ DESTROYED        (BDA: target confirmed destroyed)
     ENGAGED ──→ DAMAGED          (BDA: target damaged, not destroyed)
     ENGAGED ──→ ESCAPED          (BDA: target evaded or assessment inconclusive)
```

### Reverse Transitions

| From | To | Trigger |
|------|----|---------|
| `DETECTED` | `UNDETECTED` | Confidence decay — no UAV maintaining sensor contact |
| `TRACKED` | `UNDETECTED` | Confidence decay — tracking UAV lost or reassigned |
| `TRACKED` | `DETECTED` | `cancel_track` WebSocket action sent |
| `LOCKED` | `DETECTED` | `cancel_track` WebSocket action sent |

### State Machine Diagram

```
                    confidence decay
              ┌─────────────────────────┐
              ↓                         │
         UNDETECTED ──→ DETECTED ──→ TRACKED ──→ IDENTIFIED ──→ NOMINATED ──→ LOCKED ──→ ENGAGED
                           ↑            │                                        │          │ │ │
                           │            │              cancel_track               │          │ │ │
                           │            ←────────────────────────────────────────┘          │ │ │
                           │                                                                │ │ │
                           └──────────── cancel_track ──────────────────────────────────────┘ │ │
                                                                                    ↓   ↓   ↓
                                                                              DESTROYED DAMAGED ESCAPED
```

---

## Demo Mode

Demo mode runs the full F2T2EA kill chain automatically without human input, useful for demonstrations and system validation.

### Enabling Demo Mode

```bash
# Via launch script (recommended)
./palantir.sh --demo

# Via launch script without drone video simulator
./palantir.sh --demo --no-sim

# Via environment variable (backend only)
DEMO_MODE=true ./venv/bin/python3 src/python/api_main.py
```

### How It Works

When `DEMO_MODE=true`, the backend starts `demo_autopilot()` as an async background task alongside the normal 10Hz simulation loop. The autopilot drives the entire kill chain:

1. **Find/Fix**: Simulation detects targets normally via sensor coverage
2. **Auto-Nominate**: Detected targets are automatically nominated for engagement
3. **Auto-Approve** (HITL Gate 1): Nominations are auto-approved after a **5-second** delay
4. **COA Generation**: 3 Courses of Action are generated per approved nomination
5. **Auto-Authorize** (HITL Gate 2): Best COA is auto-authorized after a **3-second** delay
6. **Engage**: Strike is simulated with probabilistic outcomes (DESTROYED / DAMAGED / ESCAPED)
7. **Assess**: BDA result is logged and visible in the assistant feed

### No API Keys Required

Demo mode does not invoke LangChain/OpenAI agents. All AI reasoning is replaced with deterministic logic, making it fully self-contained with no external dependencies.

### UI Indicators

- A red **"DEMO MODE"** banner is displayed on the dashboard when demo mode is active
- All auto-pilot actions (nominations, approvals, authorizations, strikes) appear in the **Tactical AIP Assistant** message feed with timestamps
- The strike board updates in real time as targets progress through the kill chain

### Timing Summary

| Action | Delay |
|--------|-------|
| Target detection → nomination | Immediate (next autopilot cycle) |
| Nomination → approval | ~5 seconds |
| COA generation | 3 COAs generated immediately after approval |
| COA → authorization | ~3 seconds |
| Authorization → engagement | Immediate |
| Engagement → BDA result | Immediate (probabilistic) |

---

**Last Updated**: 2026-03-19
**API Version**: v2 (F2T2EA kill chain)
**Stability**: Stable (subject to change with PRD v2 upgrade)
