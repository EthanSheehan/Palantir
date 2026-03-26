# Wave 6C-Beta: openapi_spec — Results

## Status: COMPLETE

## What Was Built

### 1. `docs/asyncapi.yaml` (AsyncAPI 2.6.0 specification)

Full AsyncAPI 2.6.0 specification documenting the Palantir WebSocket protocol.

**Coverage:**
- 36 client → server messages documented (all actions in `_DISPATCH_TABLE` + `IDENTIFY` handshake)
- 12 server → client messages documented
- All payload schemas with required fields, types, enums, constraints
- Realistic examples for every message
- Two server environments: `ws://localhost:8000/ws` (dev) and `wss://{host}:{port}/ws` (prod)

**Message categories:**
- Connection handshake: `IDENTIFY`
- Drone control (8): `scan_area`, `follow_target`, `paint_target`, `intercept_target`, `intercept_enemy`, `cancel_track`, `move_drone`, `spike`
- HITL approvals (6): `approve_nomination`, `reject_nomination`, `retask_nomination`, `authorize_coa`, `reject_coa`, `verify_target`
- Swarm (2): `request_swarm`, `release_swarm`
- Autonomy control (6): `set_autonomy_level`, `set_action_autonomy`, `force_manual`, `set_drone_autonomy`, `approve_transition`, `reject_transition`
- Configuration (4): `set_coverage_mode`, `set_roe`, `get_roe`, `SET_SCENARIO`
- Feed subscriptions (2): `subscribe`, `subscribe_sensor_feed`
- Queries (2): `sitrep_query` / `generate_sitrep`, `retask_sensors`
- Persistence (2): `save_checkpoint`, `load_mission`
- Simulation control (1): `reset`

**Schemas documented:**
- `UavState` — full UAV object with all 16 fields
- `TargetState` — full target object with state machine fields
- `EnemyUavState`, `ZoneState`, `SwarmTask`, `StrikeBoardEntry`
- `AssessmentResult` with nested `ThreatCluster`, `CoverageGap`, `MovementCorridor`
- `IsrQueueEntry`, `KillChainState`, `EnvironmentState`, `TheaterState`
- All command payload schemas with field types, constraints (min/max, maxLength, pattern, enum)

**Source verified from:**
- `websocket_handlers.py` — `_DISPATCH_TABLE`, `_ACTION_SCHEMAS`, all handler functions
- `sim_engine.py` — `get_state()` return structure (all UAV/target/zone/enemy fields)
- `simulation_loop.py` — broadcast format, assessment serialization, sensor feed
- `api_main.py` — connection lifecycle, auth, rate limits, close codes

### 2. `docs/websocket_protocol.md` (human-readable documentation)

Human-readable protocol guide covering:
- Connection URL, limits table (max connections, message size, rate limit, timeout)
- Authentication: 3 token tiers, identification handshake, close codes
- Message format: command (action-based) and response (type-based)
- Server broadcast format: full `data` field breakdown with UAV and Target object field tables
- Quick reference table of all 36 client actions with required fields
- Server → Client message type table (12 types) with trigger and description
- Intel feed section with example payloads for INTEL_FEED, COMMAND_FEED, SENSOR_FEED
- 6 working code examples (connect, receive state, command drone, approve nomination, subscribe feeds, sitrep query)
- Error handling reference table

## Files Created

- `/docs/asyncapi.yaml` — AsyncAPI 2.6.0 specification (~700 lines)
- `/docs/websocket_protocol.md` — Human-readable protocol documentation (~320 lines)

## No Code Changes

This feature documents existing behavior only. No Python or TypeScript files were modified.
