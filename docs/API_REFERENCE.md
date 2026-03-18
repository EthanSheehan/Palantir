# Palantir C2 API Reference

**Last Updated: 2026-03-17**

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
        "mode": "scanning",
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

**Agents**: `isr_observer`, `strategy_analyst`, `tactical_planner`, `effectors_agent`

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

#### `view_target`
Center camera on target.

**Message:**
```json
{
  "type": "view_target",
  "payload": {
    "target_id": "SAM-1"
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
Command drone to lock onto target (for targeting).

**Message:**
```json
{
  "type": "paint_target",
  "payload": {
    "drone_id": "UAV-1",
    "target_id": "SAM-1",
    "action": "lock"  // "lock" or "unlock"
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

**Last Updated**: 2026-03-17
**API Version**: v2 (F2T2EA kill chain)
**Stability**: Stable (subject to change with PRD v2 upgrade)
