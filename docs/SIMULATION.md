# AMC-Grid Simulation Engine -- Technical Reference

**Date:** 2026-03-19
**Source files:** `src/python/sim_engine.py`, `src/python/sensor_model.py`, `src/python/sensor_fusion.py`, `src/python/verification_engine.py`, `theaters/*.yaml`

---

## Table of Contents

1. [Overview](#overview)
2. [Simulation Tick Loop](#simulation-tick-loop)
3. [UAV Flight Modes](#uav-flight-modes)
4. [Fixed-Wing Physics Model](#fixed-wing-physics-model)
5. [Target Types and RCS](#target-types-and-rcs)
6. [Target Behaviors](#target-behaviors)
7. [Radar Emitters](#radar-emitters)
8. [Sensor Model and Detection Pipeline](#sensor-model-and-detection-pipeline)
9. [Target State Machine](#target-state-machine)
10. [Zone Coverage and Demand](#zone-coverage-and-demand)
11. [Theater Configuration](#theater-configuration)
12. [Environment Conditions](#environment-conditions)
13. [WebSocket State Payload](#websocket-state-payload)
14. [Constants Reference](#constants-reference)
15. [Multi-Sensor Fusion](#multi-sensor-fusion)
16. [Target Verification Engine](#target-verification-engine)

---

## Overview

The AMC-Grid simulation engine (`SimulationModel`) is a 10 Hz real-time tactical simulator that models UAV surveillance operations against heterogeneous ground threats. It runs inside the FastAPI backend's WebSocket loop and broadcasts full simulation state to all connected clients each tick.

The engine handles:

- Fixed-wing UAV kinematics with turn-rate-limited flight
- 10 distinct ground target types with type-specific movement behaviors
- A physics-informed probabilistic sensor model (EO/IR, SAR, SIGINT)
- Grid-based zone demand and UAV load balancing
- A target state machine that tracks entities through the F2T2EA kill chain
- Theater-configurable scenarios loaded from YAML

The simulation is deterministic within a tick but stochastic across ticks (Poisson demand arrivals, probabilistic detection, random target behavior timers).

---

## Simulation Tick Loop

Each tick executes 9 ordered steps. The tick rate is 10 Hz, enforced by clamping `dt_sec` to a maximum of 0.1 seconds.

| Step | Description | Details |
|------|-------------|---------|
| 1 | **Update UAV zone associations** | Reset all zone `uav_count` to 0, then assign each UAV to its current zone. UAVs outside all zones are teleported to the grid center. |
| 2 | **Demand generation** | Poisson arrivals per zone: each zone generates arrivals with probability `demand_rate * dt_sec` per tick. Arrivals increment the zone's `queue`. |
| 3 | **Assign missions** | IDLE UAVs in zones with queued demand are promoted to SEARCH mode. Each assignment decrements `queue` by 1 and sets `service_timer = 2.0s`. |
| 4 | **Calculate imbalances** | `RomaniaMacroGrid.calculate_macro_flow()` computes zone-level supply/demand imbalance and returns dispatch instructions. |
| 5 | **Execute dispatches** | IDLE UAVs in over-supplied zones are set to REPOSITIONING with a target coordinate in the under-supplied zone. |
| 6 | **Update tracking modes** | Runs the orbit/intercept kinematics for UAVs in FOLLOW, PAINT, or INTERCEPT mode (see [Tracking Mode Kinematics](#tracking-mode-kinematics)). |
| 7 | **Update kinematics** | Runs `UAV.update()` for all non-tracking UAVs (IDLE, SEARCH, REPOSITIONING, RTB). |
| 8 | **Decrement service timers** | SEARCH UAVs have their `service_timer` decremented. When it reaches 0, they revert to IDLE. |
| 9 | **Update targets and detection** | Runs target movement behaviors, then evaluates probabilistic detection for every (UAV, target) pair. Updates target state and confidence. |

---

## UAV Flight Modes

Each UAV operates in exactly one of 7 flight modes at any time.

### Mode Summary

| Mode | Speed | Turn Rate | Orbit Radius | Target State Effect | Trigger |
|------|-------|-----------|-------------|-------------------|---------|
| **IDLE** | 0.5x cruise | 1x `MAX_TURN_RATE` | ~3 km loiter circle | None | Default; reverts from SEARCH when timer expires |
| **SEARCH** | 0.5x cruise | 1x `MAX_TURN_RATE` | ~3 km loiter circle | None | Zone has demand; lasts `SERVICE_TIME_SEC` (2s) |
| **FOLLOW** | 1x cruise | Turn-limited | ~2 km loose orbit | Target -> TRACKED | `command_follow(uav_id, target_id)` |
| **PAINT** | 1x cruise | Turn-limited | ~1 km tight orbit | Target -> LOCKED | `command_paint(uav_id, target_id)` |
| **INTERCEPT** | 1.5x cruise (approach), 1x (orbit) | Turn-limited | ~300 m danger-close orbit | Target -> LOCKED | `command_intercept(uav_id, target_id)` |
| **REPOSITIONING** | 1x cruise | 3x `MAX_TURN_RATE` | N/A (direct flight) | None | Zone imbalance dispatch or `command_move()` |
| **RTB** | Decaying (0.98x/tick) | None | N/A | None | `fuel_hours < 1.0` |

### Mode Details

**IDLE / SEARCH**: Identical physics. The UAV flies a fixed-wing circular loiter pattern at half cruise speed. If near-stationary (speed < 30% of loiter speed), it kicks off with a random heading. A constant `MAX_TURN_RATE` turn is applied each tick, producing a continuous circle. SEARCH differs only in that it has a `service_timer` that reverts the UAV to IDLE on expiry.

**FOLLOW**: The UAV maintains a loose orbit around the tracked target at `FOLLOW_ORBIT_RADIUS_DEG` (0.018 deg, ~2 km). It uses radial/tangential velocity mixing:
- Inside 80% of orbit radius: push outward (radial -0.3, tangential 0.7)
- Outside 120% of orbit radius: push inward (radial +0.3, tangential 0.7)
- Within band: pure tangential orbit

The target's state is set to TRACKED. `_turn_toward()` ensures smooth fixed-wing arcs.

**PAINT**: Same orbit logic as FOLLOW but tighter at `PAINT_ORBIT_RADIUS_DEG` (0.009 deg, ~1 km) with stronger radial weighting (0.4/0.6). Represents laser designation. Target state is set to LOCKED.

**INTERCEPT**: Two-phase approach:
1. **Approach** (distance > `INTERCEPT_CLOSE_DEG` / ~300 m): Direct flight toward target at 1.5x cruise speed.
2. **Orbit** (distance <= ~300 m): Switches to tight tangential orbit at cruise speed.

Target state is set to LOCKED. This is the most aggressive tracking mode.

**REPOSITIONING**: Direct flight toward a destination coordinate. Uses `_turn_toward()` with a 3x turn rate multiplier for urgency. On arrival (within 0.005 deg), reverts to IDLE. Can be triggered by zone rebalancing or manual `command_move()`.

**RTB** (Return to Base): Triggers automatically when `fuel_hours < 1.0`. Currently implemented as velocity decay (0.98x per tick) -- the UAV gradually decelerates. This is a placeholder for future base-return navigation.

### Tracking Mode Kinematics

Tracking modes (FOLLOW, PAINT, INTERCEPT) are handled in `_update_tracking_modes()`, which runs separately from the main `UAV.update()` method. This separation ensures tracking UAVs use target-relative kinematics while non-tracking UAVs use zone-relative kinematics.

While actively tracking, the UAV continuously boosts the target's `detection_confidence` by `0.1 * dt_sec` per tick, simulating persistent sensor contact.

If the tracked target becomes invalid (e.g., destroyed), the UAV reverts to SEARCH mode.

---

## Fixed-Wing Physics Model

All UAV movement uses a fixed-wing physics model that enforces realistic turn constraints.

### Core Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `SPEED_DEG_PER_SEC` | 0.005 | Base cruise speed in degrees/second (~550 m/s at mid-latitudes) |
| `MAX_TURN_RATE` | `radians(3.0)` | Standard rate turn: 3 deg/sec (~0.0524 rad/s) |
| `LOITER_RADIUS_DEG` | 0.027 | Loiter circle radius (~3 km) |

### Turn Mechanics: `_turn_toward()`

The `_turn_toward()` method implements rate-limited heading changes:

```
1. Compute current heading from (vx, vy) via atan2
2. Compute desired heading from target velocity vector
3. Calculate angular difference, normalized to [-pi, pi]
4. Clamp to MAX_TURN_RATE * dt_sec * 3 (the 3x multiplier provides responsiveness)
5. Apply new heading, recompute (vx, vy) at the given speed
```

The method uses `atan2(vx, vy)` (note: x before y), which produces headings where 0 = north, 90 = east -- consistent with geographic bearing conventions.

### Heading Computation

The helper `_heading_from_velocity(vx, vy)` converts velocity components to a 0-360 degree heading using `degrees(atan2(vx, vy)) % 360`. This is broadcast to clients for entity orientation on the map.

### Speed Regimes

| Context | Speed | Derivation |
|---------|-------|------------|
| IDLE / SEARCH loiter | 0.0025 deg/s | `SPEED_DEG_PER_SEC * 0.5` |
| FOLLOW / PAINT orbit | 0.005 deg/s | `SPEED_DEG_PER_SEC` |
| INTERCEPT approach | 0.0075 deg/s | `SPEED_DEG_PER_SEC * 1.5` |
| REPOSITIONING | 0.005 deg/s | `SPEED_DEG_PER_SEC` (but 3x turn rate) |
| RTB | Decaying | `velocity * 0.98` per tick |

### Fuel Model

Each UAV has `fuel_hours` (default 24h from theater config) and `fuel_rate` (default 1.0). Fuel is consumed every tick:

```
fuel_hours -= (dt_sec / 3600.0) * fuel_rate
```

When `fuel_hours < 1.0`, the UAV automatically enters RTB mode regardless of its current mode.

---

## Target Types and RCS

The simulation models 10 ground target types, each with a base radar cross-section (RCS) in square meters.

| Type | RCS (m^2) | Behavior | Description |
|------|-----------|----------|-------------|
| SAM | 15.0 | stationary | Surface-to-air missile system |
| TEL | 10.0 | shoot_and_scoot | Transporter-Erector-Launcher |
| TRUCK | 5.0 | patrol | Generic transport vehicle |
| CP | 8.0 | stationary | Command Post |
| MANPADS | 0.5 | ambush | Man-Portable Air-Defense System |
| RADAR | 20.0 | stationary | Radar installation |
| C2_NODE | 6.0 | stationary | Command and Control node |
| LOGISTICS | 4.0 | patrol | Logistics convoy |
| ARTILLERY | -- | -- | (Defined in ontology; spawned by theater config) |
| APC | -- | -- | (Defined in ontology; spawned by theater config) |

RCS values determine how easily a target is detected by sensors. Higher RCS means greater detection probability at a given range. MANPADS (0.5 m^2) is by far the hardest to detect; RADAR (20.0 m^2) is the easiest.

---

## Target Behaviors

Each target type has an assigned movement behavior that governs its tick-by-tick updates.

### stationary

**Types:** SAM, CP, RADAR, C2_NODE

No movement. Velocity is zeroed each tick. These are fixed installations.

### patrol

**Types:** TRUCK, LOGISTICS (at 0.5x speed)

Follows a loop of 3-5 random waypoints within the theater bounds. On initialization, waypoints are generated randomly. The target moves toward the current waypoint at its configured speed; when within 0.005 degrees (~500 m), it advances to the next waypoint. After the last waypoint, it loops back to the first.

LOGISTICS units use `LOGISTICS_SPEED_MULT = 0.5`, making them half the speed of TRUCK units.

Patrol targets bounce off theater boundaries (velocity reversal on boundary contact).

### shoot_and_scoot

**Type:** TEL

The TEL alternates between stationary phases and relocation:

1. **Stationary phase**: Stays in place for 30-60 seconds (randomized `relocate_timer`).
2. **Relocation**: When the timer expires, teleports to a random position within theater bounds. Timer resets to 30-60 seconds.
3. **Concealment**: If any UAV is within `CONCEALMENT_DIST_DEG` (0.03 deg, ~3 km), the TEL freezes in place with `concealed = True` and velocity zeroed. This simulates the TEL hiding from overhead surveillance.

### ambush

**Type:** MANPADS

Normally stationary. When a UAV approaches within `MANPADS_FLEE_DIST_DEG` (0.045 deg, ~5 km):

1. The MANPADS executes a displacement to a random offset (-0.1 to +0.1 degrees in each axis).
2. Position is clamped to theater bounds.
3. A `flee_cooldown` of 15 seconds is set, during which the MANPADS remains stationary and ignores further UAV proximity triggers.
4. After cooldown expires, it resumes monitoring for UAV proximity.

### Concealment

TEL and MANPADS types check for UAV proximity each tick. If any UAV is within `CONCEALMENT_DIST_DEG` (0.03 deg, ~3 km), the target sets `concealed = True`. This flag is available in the state payload for UI rendering and potentially affects future detection logic.

---

## Radar Emitters

Types in the `EMITTING_TYPES` set (SAM and RADAR) have an `is_emitting` boolean that toggles probabilistically.

- **Toggle probability**: `EMIT_TOGGLE_PROB = 0.005` per tick (0.5% chance each 0.1s tick)
- **Effect**: SIGINT sensors can only detect targets that are actively emitting. When `is_emitting = False`, SIGINT returns `Pd = 0.0` for that target.
- **Initial state**: All emitting types start with `is_emitting = True`.

The toggle simulates radar emission control (EMCON) -- real air defense systems periodically shut down radar to avoid anti-radiation missile targeting.

---

## Sensor Model and Detection Pipeline

The sensor model (`sensor_model.py`) provides a physics-informed probability of detection (Pd) for each UAV-target pair. All types are immutable frozen dataclasses.

### Sensor Types

| Sensor | Max Range | Resolution Factor | Weather Sensitivity | Requires Emitter |
|--------|-----------|-------------------|--------------------|--------------------|
| EO_IR | 50 km | 1.0 | 0.8 (high) | No |
| SAR | 100 km | 0.7 | 0.2 (low) | No |
| SIGINT | 200 km | 0.3 | 0.0 (immune) | Yes |

### Detection Evaluation Flow

For each (UAV, target) pair in step 9 of the tick:

1. **Range computation**: Equirectangular approximation converts degree separation to meters.
2. **Aspect angle**: Computed from UAV-to-target bearing minus target heading. Broadside (90 deg) maximizes effective RCS; head-on (0 deg) minimizes it.
3. **RCS modulation**: `effective_RCS = base_RCS * (0.3 + 1.2 * sin^2(aspect))`
   - Head-on (0 deg): 0.3x base RCS
   - Broadside (90 deg): 1.5x base RCS
4. **Pd calculation**: See formula below.
5. **Detection roll**: `random() < Pd` determines if the target is detected this tick.
6. **Confidence**: `Pd * resolution_factor` (clamped to [0, 1]).

### Pd Formula

```
range_term     = 1 - (range / max_range)^2
rcs_gain       = log10(effective_RCS / reference_RCS)
weather_penalty = weather_sensitivity * (cloud_cover + precipitation * 0.5) * 0.6

snr_norm = range_term + rcs_gain * 0.3 - weather_penalty
Pd       = sigmoid(snr_norm * 10 - 5)
```

The sigmoid maps the normalized SNR to a smooth 0-1 probability curve. The `* 10 - 5` scaling centers the transition region around `snr_norm = 0.5`.

**Hard gates:**
- SIGINT with `emitting = False` returns `Pd = 0.0` immediately.
- Range beyond `max_range` produces a negative `range_term`, driving Pd toward 0.

### Detection Fade

When no UAV detects a target in a given tick and the target is not being actively tracked (`tracked_by_uav_id is None`):

```
detection_confidence *= 0.95  (per tick, exponential decay)
if detection_confidence < 0.1:
    state -> UNDETECTED
    detection_confidence -> 0.0
```

This simulates sensor contact fading when a target leaves coverage. At 10 Hz, confidence halves roughly every 1.4 seconds of non-detection.

### Worked Example: SAM at 30 km, EO_IR, Clear Weather

```
range_term     = 1 - (30000 / 50000)^2 = 1 - 0.36 = 0.64
base_rcs       = 15.0 m^2
aspect         = 90 deg (broadside)
effective_rcs  = 15.0 * (0.3 + 1.2 * 1.0) = 15.0 * 1.5 = 22.5
rcs_gain       = log10(22.5 / 5.0) = log10(4.5) = 0.653
weather_penalty = 0.8 * (0.0 + 0.0) * 0.6 = 0.0

snr_norm = 0.64 + 0.653 * 0.3 - 0.0 = 0.836
Pd       = sigmoid(0.836 * 10 - 5) = sigmoid(3.36) = 0.966

confidence = 0.966 * 1.0 = 0.966
```

Result: 96.6% detection probability at broadside, clear weather, 30 km range.

---

## Target State Machine

Targets progress through a linear state machine representing the F2T2EA kill chain.

```
UNDETECTED -> DETECTED -> TRACKED -> IDENTIFIED -> NOMINATED -> LOCKED -> ENGAGED -> DESTROYED
                                                                                  \-> ESCAPED
```

### State Transitions

| From | To | Trigger |
|------|----|---------|
| UNDETECTED | DETECTED | Sensor detects target (`random() < Pd`) |
| DETECTED | TRACKED | UAV enters FOLLOW mode on target |
| DETECTED | LOCKED | UAV enters PAINT or INTERCEPT mode on target |
| DETECTED | UNDETECTED | Detection confidence fades below 0.1 |
| TRACKED | LOCKED | UAV switches to PAINT or INTERCEPT |
| TRACKED | DETECTED | UAV cancels track (`cancel_track()`) |
| LOCKED | DETECTED | UAV cancels track (`cancel_track()`) |
| NOMINATED | LOCKED | External (demo autopilot or human approval) |
| ENGAGED | DESTROYED | Strike outcome (demo autopilot) |
| ENGAGED | ESCAPED | Strike outcome (demo autopilot) |
| Any | DESTROYED | `_set_target_state(target_id, "DESTROYED")` -- zeros velocity |

The IDENTIFIED, NOMINATED, ENGAGED transitions are driven by the AI agent layer and demo autopilot, not by the simulation engine directly.

---

## Zone Coverage and Demand

The simulation uses a grid-based zone system (`RomaniaMacroGrid`) to manage UAV distribution across the theater.

### Zone Properties

Each zone tracks:

| Property | Description |
|----------|-------------|
| `queue` | Accumulated demand (integer, incremented by Poisson arrivals) |
| `uav_count` | Number of UAVs currently within the zone |
| `demand_rate` | Base Poisson arrival rate (lambda) for the zone |
| `imbalance` | Computed supply/demand mismatch, drives repositioning |

### Demand Generation

Demand arrives via a Poisson process each tick:
```
prob = demand_rate * dt_sec
while prob > 0:
    if random() < min(1.0, prob): arrivals++
    prob -= 1.0
```

### Mission Assignment

IDLE UAVs in zones with positive queue are promoted to SEARCH. The number assigned is `min(queue, idle_uav_count)`, and queue is decremented accordingly.

### Rebalancing

`calculate_macro_flow()` identifies zones with surplus UAVs (low demand, high count) and deficit zones (high demand, low count). It returns dispatch instructions that move IDLE UAVs from surplus to deficit zones via REPOSITIONING mode.

### Demand Spike

`trigger_demand_spike(lon, lat)` adds 120 to the queue of the zone containing the given coordinates. This is used by the frontend to simulate intelligence-driven tasking surges.

---

## Theater Configuration

Theaters are defined in YAML files under `theaters/`. Available theaters: **Romania**, **South China Sea**, **Baltic**.

### YAML Schema

```yaml
name: "Romania Eastern Flank"
description: "NATO defensive scenario -- Romanian AO"
bounds:
  min_lon: 20.26
  max_lon: 29.67
  min_lat: 43.62
  max_lat: 48.27
grid:
  cols: 50
  rows: 50
blue_force:
  uavs:
    count: 20
    type: MQ-9
    base_lon: 25.0
    base_lat: 45.5
    default_altitude_m: 3000
    sensor_type: EO_IR
    endurance_hours: 24
red_force:
  units:
    - type: SAM
      count: 3
      behavior: stationary
      threat_range_km: 30
    - type: TEL
      count: 4
      behavior: shoot_and_scoot
      speed_kmh: 40
    # ... additional unit types
environment:
  weather: clear
  time_of_day: day
  terrain: mixed
```

### Theater Initialization

When `SimulationModel` is instantiated with a theater name:

1. Theater YAML is loaded via `theater_loader.load_theater()`.
2. Bounds, UAV count, altitude, sensor type, and endurance are read from `blue_force`.
3. Target pool is built from `red_force.units` -- each entry's `type` and `count` determine spawn composition.
4. UAVs and targets are spawned randomly within grid zones.

If theater loading fails, the simulation falls back to hardcoded defaults: 20 UAVs, Romania-sized bounds, and a fixed target pool of 3 SAM, 4 TEL, 8 TRUCK, 2 CP.

---

## Environment Conditions

The `EnvironmentConditions` dataclass controls weather effects on sensor performance.

| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| `time_of_day` | 0.0 - 24.0 hours | 12.0 | Reserved for future use (night penalty) |
| `cloud_cover` | 0.0 - 1.0 | 0.0 | Degrades EO_IR heavily, SAR slightly, SIGINT immune |
| `precipitation` | 0.0 - 1.0 | 0.0 | Additional weather penalty (weighted 0.5x vs cloud cover) |

Environment can be changed at runtime via `SimulationModel.set_environment()`.

### Sensor Degradation by Weather

The weather penalty formula:

```
penalty = weather_sensitivity * (cloud_cover + precipitation * 0.5) * 0.6
```

| Scenario (cloud=0.8, precip=0.5) | EO_IR (0.8) | SAR (0.2) | SIGINT (0.0) |
|-----------------------------------|-------------|-----------|--------------|
| Weather penalty | 0.504 | 0.126 | 0.0 |

Heavy overcast with rain significantly degrades EO_IR detection (penalty ~0.5 subtracted from snr_norm) while SAR remains largely effective and SIGINT is completely unaffected.

---

## WebSocket State Payload

`SimulationModel.get_state()` returns the full simulation state as a JSON-serializable dictionary, broadcast to all connected WebSocket clients each tick.

### Payload Structure

```json
{
  "uavs": [
    {
      "id": 0,
      "lon": 25.123,
      "lat": 45.456,
      "mode": "SEARCH",
      "altitude_m": 3000.0,
      "sensor_type": "EO_IR",
      "heading_deg": 127.3,
      "tracked_target_id": null,
      "fuel_hours": 23.45
    }
  ],
  "zones": [
    {
      "x_idx": 0,
      "y_idx": 0,
      "lon": 20.5,
      "lat": 43.8,
      "width": 0.188,
      "height": 0.093,
      "queue": 0,
      "uav_count": 1,
      "imbalance": -0.5
    }
  ],
  "flows": [
    { "source": [25.0, 45.0], "target": [27.0, 46.0] }
  ],
  "targets": [
    {
      "id": 0,
      "lon": 26.789,
      "lat": 44.321,
      "type": "SAM",
      "detected": true,
      "state": "DETECTED",
      "detection_confidence": 0.873,
      "detected_by_sensor": "EO_IR",
      "is_emitting": true,
      "heading_deg": 0.0,
      "tracked_by_uav_id": null
    }
  ],
  "environment": {
    "time_of_day": 12.0,
    "cloud_cover": 0.0,
    "precipitation": 0.0
  },
  "theater": {
    "name": "romania",
    "bounds": {
      "min_lon": 20.26,
      "max_lon": 29.67,
      "min_lat": 43.62,
      "max_lat": 48.27
    }
  }
}
```

---

## Constants Reference

All tunable simulation parameters in one place.

### UAV Constants

| Constant | Value | Unit | Description |
|----------|-------|------|-------------|
| `SPEED_DEG_PER_SEC` | 0.005 | deg/s | Base cruise speed |
| `MAX_TURN_RATE` | `radians(3.0)` (~0.0524) | rad/s | Standard rate turn |
| `LOITER_RADIUS_DEG` | 0.027 | deg | Fixed-wing loiter circle (~3 km) |
| `FOLLOW_ORBIT_RADIUS_DEG` | 0.018 | deg | Follow mode orbit (~2 km) |
| `PAINT_ORBIT_RADIUS_DEG` | 0.009 | deg | Paint mode orbit (~1 km) |
| `INTERCEPT_CLOSE_DEG` | 0.003 | deg | Intercept danger-close threshold (~300 m) |
| `FOLLOW_OFFSET_DEG` | 0.01 | deg | Follow offset distance |
| `SERVICE_TIME_SEC` | 2.0 | s | SEARCH mode duration before revert to IDLE |

### Target Constants

| Constant | Value | Unit | Description |
|----------|-------|------|-------------|
| `MANPADS_FLEE_DIST_DEG` | 0.045 | deg | MANPADS flee trigger distance (~5 km) |
| `CONCEALMENT_DIST_DEG` | 0.03 | deg | TEL/MANPADS concealment trigger (~3 km) |
| `LOGISTICS_SPEED_MULT` | 0.5 | multiplier | Logistics patrol speed relative to TRUCK |
| `EMIT_TOGGLE_PROB` | 0.005 | probability/tick | Radar EMCON toggle rate |

### Sensor Constants

| Constant | Value | Description |
|----------|-------|-------------|
| EO_IR max range | 50,000 m | Electro-optical / infrared |
| SAR max range | 100,000 m | Synthetic aperture radar |
| SIGINT max range | 200,000 m | Signals intelligence |
| Fallback RCS | 3.0 m^2 | Used for unknown target types |
| Confidence decay | 0.95x/tick | Detection fade rate |
| Confidence threshold | 0.1 | Below this, target reverts to UNDETECTED |

### Detection Formula Quick Reference

```
effective_RCS   = base_RCS * (0.3 + 1.2 * sin^2(aspect))
range_term      = 1 - (range / max_range)^2
rcs_gain        = log10(effective_RCS / reference_RCS)
weather_penalty = sensitivity * (cloud + precip * 0.5) * 0.6
snr_norm        = range_term + rcs_gain * 0.3 - weather_penalty
Pd              = sigmoid(snr_norm * 10 - 5)
confidence      = Pd * resolution_factor
```

---

## Multi-Sensor Fusion

**Source:** `src/python/sensor_fusion.py`

The fusion module combines confidence readings from multiple sensors observing the same target into a single `fused_confidence` value. It uses **complementary fusion** — a standard technique where independent sensor readings combine multiplicatively.

### Algorithm

```
fused_confidence = 1 - ∏(1 - max_confidence_per_sensor_type)
```

1. **Group by sensor type** — each sensor type (EO_IR, SAR, SIGINT) contributes at most one reading per target
2. **Max within type** — if multiple UAVs of the same sensor type observe the same target, take the highest confidence
3. **Complementary combine** — multiply the miss probabilities, then subtract from 1

### Example

A target observed by EO_IR (0.7) and SAR (0.6):
```
fused = 1 - (1 - 0.7) × (1 - 0.6) = 1 - 0.3 × 0.4 = 0.88
```

### Data Types

All types are immutable frozen dataclasses:

| Type | Fields | Description |
|------|--------|-------------|
| `SensorContribution` | `uav_id`, `sensor_type`, `confidence` | Single sensor reading |
| `FusionResult` | `contributions`, `fused_confidence` | Combined result |

### Integration with Sim Engine

Each tick (step 9), the sim engine:
1. Collects all successful sensor detections for each target
2. Passes them to `fuse_sensors()` to compute `FusionResult`
3. Updates `target.fused_confidence` and `target.sensor_contributions`
4. Feeds `fused_confidence` into the verification engine for state advancement

---

## Target Verification Engine

**Source:** `src/python/verification_engine.py`

The verification engine is a pure-function state machine that gates targets before they can enter the kill chain. This prevents false positives and single-sensor flukes from being nominated for engagement.

### Verification States

```
DETECTED → CLASSIFIED → VERIFIED → NOMINATED
```

### Pure Function Interface

```python
def evaluate_verification(
    current_state: str,
    fused_confidence: float,
    distinct_sensor_count: int,
    time_in_current_state_sec: float,
    target_type: str,
    thresholds: dict[str, VerificationThreshold] | None = None,
) -> str:
    """Returns the new state (may be same as current_state)."""
```

No side effects, no mutation — the caller (sim_engine) is responsible for applying the returned state.

### Per-Target-Type Thresholds

High-threat targets verify faster:

| Type | Classify Conf | Verify Conf | Min Sensors | Sustained (s) | Regression (s) |
|------|--------------|-------------|-------------|----------------|-----------------|
| SAM | 0.50 | 0.70 | 2 | 10 | 8 |
| TEL | 0.50 | 0.70 | 2 | 10 | 10 |
| MANPADS | 0.50 | 0.70 | 2 | 10 | 8 |
| RADAR | 0.55 | 0.75 | 2 | 12 | 10 |
| C2_NODE | 0.55 | 0.75 | 2 | 12 | 10 |
| ARTILLERY | 0.55 | 0.75 | 2 | 12 | 10 |
| CP | 0.60 | 0.80 | 2 | 15 | 15 |
| TRUCK | 0.60 | 0.80 | 2 | 15 | 15 |
| LOGISTICS | 0.60 | 0.80 | 2 | 15 | 15 |
| APC | 0.60 | 0.80 | 2 | 15 | 15 |

### Advancement Rules

- **DETECTED → CLASSIFIED**: `fused_confidence >= classify_confidence`
- **CLASSIFIED → VERIFIED**: `fused_confidence >= verify_confidence` AND (`distinct_sensor_count >= verify_sensor_types` OR `time_in_state >= verify_sustained_sec`)
- **VERIFIED → NOMINATED**: Handled externally by the ISR pipeline

### Regression

If `fused_confidence` drops to 0.0 (no sensor contact), the target regresses one state after `regression_timeout_sec`:
- CLASSIFIED → DETECTED
- VERIFIED → CLASSIFIED

### Manual Override

The `verify_target` WebSocket action fast-tracks a CLASSIFIED target to VERIFIED, bypassing the automated criteria. This allows operators to inject human intelligence.

### DEMO_FAST Preset

When `DEMO_MODE=true`, `DEMO_FAST_THRESHOLDS` are used:
- All confidence thresholds reduced by 0.1 (minimum 0.3/0.4)
- All time thresholds halved
- Allows rapid kill chain progression for demonstrations
