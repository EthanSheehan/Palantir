# Grid-Sentinel Swarm Sensor Fusion Upgrade Plan

> Staged upgrade roadmap for drone swarm sensor fusion, intelligent target management, and battlespace assessment. Each stage is independently demoable via `./grid-sentinel.sh --demo`.

---

## Current State Summary

The system operates **individual UAVs** that independently detect, track, and paint targets. Key limitations:

- **1:1 UAV-to-target tracking** — `target.tracked_by_uav_id` is a single int, `uav.tracked_target_id` is a single int
- **No multi-sensor fusion** — each UAV evaluates detection independently; only the best single detection is kept per tick
- **No target verification workflow** — detection jumps from DETECTED straight to nomination
- **No swarm coordination** — UAVs assigned to zones by imbalance, never coordinate on shared targets
- **Dormant agents** — `battlespace_manager.py` and `ai_tasking_manager.py` have heuristic stubs that raise `NotImplementedError`
- **6 UAV modes** — IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, REPOSITIONING, RTB (all human-commanded except IDLE/SEARCH/REPOSITIONING)
- **Single feed type** — 10Hz state broadcast over WebSocket with drone video simulator overlay

### Current Architecture

```
sim_engine.py (742 lines)      ← UAV physics, target behaviors, detection loop
  ↓ get_state()
api_main.py (808 lines)        ← WebSocket server, 10Hz broadcast, command handler
  ↓ JSON state
frontend/ (6 JS modules)       ← Cesium 3D map, drone/enemy lists, strike board, drone cam
```

```
Agents pipeline (ISR → Strategy → Tactical → Effectors):
  isr_observer.py      → track correlation, classification
  strategy_analyst.py   → ROE evaluation, nomination
  tactical_planner.py   → COA generation
  effectors_agent.py    → engagement, BDA

Dormant:
  battlespace_manager.py  → threat rings (skeleton)
  ai_tasking_manager.py   → sensor retasking (skeleton)
```

---

## Stage 1: Multi-Sensor Target Fusion

**Goal**: Multiple UAVs contribute detections to the same target. Fused confidence increases with more sensors. Foundation for everything else.

### 1.1 Data Model Changes

**`sim_engine.py` — Target class**
```python
# BEFORE (1:1)
self.tracked_by_uav_id: Optional[int] = None

# AFTER (many:1)
self.tracked_by_uav_ids: list[int] = []        # all UAVs observing this target
self.sensor_contributions: list[dict] = []      # per-UAV detection details
self.fused_confidence: float = 0.0              # combined multi-sensor confidence
self.sensor_count: int = 0                      # how many distinct sensors contributing
```

**`sim_engine.py` — UAV class**
```python
# BEFORE (1:1)
self.tracked_target_id: Optional[int] = None

# AFTER (1:many)
self.tracked_target_ids: list[int] = []         # UAV can observe multiple targets in FOV
self.primary_target_id: Optional[int] = None    # the target this UAV is actively tasked against
```

### 1.2 New Module: `src/python/sensor_fusion.py`

```python
@dataclass(frozen=True)
class SensorContribution:
    uav_id: int
    sensor_type: str          # EO_IR, SAR, SIGINT
    individual_confidence: float
    range_m: float
    bearing_deg: float
    timestamp: float

@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float           # 1 - product(1 - ci)
    classification: str               # majority vote weighted by confidence
    sensor_count: int
    sensor_types: frozenset[str]      # distinct sensor modalities
    contributions: tuple[SensorContribution, ...]

def fuse_detections(contributions: list[SensorContribution]) -> FusedDetection:
    """Complementary fusion: fused = 1 - product(1 - ci)"""
```

**Fusion algorithm**: `fused_confidence = 1 - product(1 - ci)` for independent sensors. Simple, intuitive, correct behavior (more sensors = higher confidence, diminishing returns).

### 1.3 Detection Loop Changes (`sim_engine.py` tick)

```python
# BEFORE: keep only best single detection
best_detection = None
for u in self.uavs:
    result = evaluate_detection(...)
    if result.detected and result.confidence > best_detection.confidence:
        best_detection = result

# AFTER: accumulate all detections, fuse
all_detections = []
for u in self.uavs:
    result = evaluate_detection(...)
    if result.detected:
        all_detections.append(SensorContribution(
            uav_id=u.id, sensor_type=u.sensor_type,
            individual_confidence=result.confidence, ...
        ))
fused = fuse_detections(all_detections)
t.fused_confidence = fused.fused_confidence
t.sensor_contributions = all_detections
t.sensor_count = fused.sensor_count
```

### 1.4 WebSocket Protocol Extension

Target payload gains new fields (backward compatible — additive):
```json
{
  "id": 5,
  "fused_confidence": 0.94,
  "sensor_count": 3,
  "contributing_uav_ids": [2, 7, 11],
  "sensor_contributions": [
    {"uav_id": 2, "sensor_type": "EO_IR", "confidence": 0.72},
    {"uav_id": 7, "sensor_type": "SIGINT", "confidence": 0.85},
    {"uav_id": 11, "sensor_type": "SAR", "confidence": 0.68}
  ]
}
```

### 1.5 Frontend Changes

**`enemies.js`** — Target cards:
- Fused confidence bar with multi-color segments (EO_IR=blue, SAR=green, SIGINT=yellow)
- Sensor count badge ("3 SENSORS")
- List of contributing UAV IDs

**`targets.js`** — Map entities:
- Sensor fusion ring around targets: ring thickness/opacity scales with sensor count
- Color gradient: thin yellow (1 sensor) → thick green (2+) → bright white (3+ diverse sensors)

### 1.6 Tracking Mode Migration

All functions referencing `tracked_by_uav_id` / `tracked_target_id` (singular) must migrate:
- `_assign_target()` — add to lists instead of overwrite
- `cancel_track()` — remove from lists
- `_update_tracking_modes()` — iterate over `tracked_target_ids`
- `command_follow/paint/intercept` — set `primary_target_id` and add to tracking lists
- `demo_autopilot()` — update to use new fields
- `dronelist.js` — show all tracked targets, highlight primary
- `enemies.js` — show all tracking UAVs per target

### 1.7 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] Multiple UAVs near a target → fused confidence climbs
- [ ] Confidence bar shows per-sensor breakdown
- [ ] Removing a UAV from the area → fused confidence degrades
- [ ] Target cards show sensor count and contributing UAVs
- [ ] Existing follow/paint/intercept commands still work
- [ ] Demo autopilot runs without errors

### 1.8 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/sensor_fusion.py` | **NEW** | ~150 |
| `src/python/sim_engine.py` | MODIFY | ~100 changed |
| `src/python/api_main.py` | MODIFY | ~30 changed |
| `src/frontend/enemies.js` | MODIFY | ~50 changed |
| `src/frontend/targets.js` | MODIFY | ~30 changed |
| `src/frontend/dronelist.js` | MODIFY | ~20 changed |
| `src/frontend/dronecam.js` | MODIFY | ~15 changed |
| `src/python/tests/test_sensor_fusion.py` | **NEW** | ~100 |

### 1.9 Risk Assessment

**Medium risk**: The 1:1 tracking assumption is baked into `_update_tracking_modes()`, `command_follow()`, `command_paint()`, `cancel_track()`, demo autopilot, and both `enemies.js` and `dronelist.js`. All must be updated atomically.

---

## Stage 2: Target Verification Workflow

**Goal**: Targets must progress through a verification pipeline before nomination. Multi-sensor evidence required. Replaces the current jump from DETECTED straight to the strike board.

### 2.1 Extended State Machine

```
BEFORE:  UNDETECTED → DETECTED → TRACKED → IDENTIFIED → NOMINATED → LOCKED → ENGAGED → DESTROYED|ESCAPED

AFTER:   UNDETECTED → DETECTED → CLASSIFIED → VERIFIED → NOMINATED → LOCKED → ENGAGED → DESTROYED|ESCAPED
                         ↑                                    ↑
                    auto (1 sensor)                    ISR+Strategy pipeline
                                                       (only from VERIFIED)
```

**State promotion rules**:
| Transition | Criteria |
|-----------|----------|
| UNDETECTED → DETECTED | Any single sensor detection |
| DETECTED → CLASSIFIED | `fused_confidence >= 0.6` AND at least 1 sensor |
| CLASSIFIED → VERIFIED | `fused_confidence >= 0.8` AND (2+ different sensor types OR sustained tracking > 15s) |
| VERIFIED → NOMINATED | ISR Observer + Strategy Analyst pipeline (existing) |
| *regression* | No sensors observe for T seconds → regress one state |

**Configurable thresholds per target type** (SAMs verify faster due to high threat):
```python
VERIFICATION_THRESHOLDS = {
    "SAM":     {"classify": 0.5, "verify": 0.7, "min_sensors": 1},
    "RADAR":   {"classify": 0.5, "verify": 0.7, "min_sensors": 1},
    "TEL":     {"classify": 0.6, "verify": 0.8, "min_sensors": 2},
    "TRUCK":   {"classify": 0.6, "verify": 0.85, "min_sensors": 2},
    "CP":      {"classify": 0.55, "verify": 0.75, "min_sensors": 2},
    "default": {"classify": 0.6, "verify": 0.8, "min_sensors": 2},
}
```

### 2.2 New Module: `src/python/verification_engine.py`

```python
def evaluate_target_state(
    target_state: str,
    fused_confidence: float,
    sensor_types: set[str],
    sustained_tracking_sec: float,
    target_type: str,
) -> str:
    """Pure function — returns the new state based on promotion/regression criteria."""
```

- Pure function, no side effects, fully testable
- Called from `sim_engine.tick()` after fusion
- Includes time-decay regression when sensors lose contact
- Demo preset: `DEMO_FAST` halves all thresholds for compelling timing

### 2.3 Pipeline Gate Change

**`api_main.py` — `_process_new_detection()`**:
```python
# BEFORE: triggers on any DETECTED target
if is_detected and not self.last_detected.get(tid, False):
    _process_new_detection(target, ...)

# AFTER: only triggers on VERIFIED targets
if target_state == "VERIFIED" and not self._verified.get(tid, False):
    _process_new_detection(target, ...)
```

### 2.4 New WebSocket Action

```json
{"action": "verify_target", "target_id": 5}
```
Operator manually promotes a CLASSIFIED target to VERIFIED (fast-track for urgent threats).

### 2.5 Frontend Changes

**`enemies.js`** — Target cards:
- State progression stepper: `DETECTED → CLASSIFIED → VERIFIED → NOMINATED`
- Each step shows a colored dot (gray=pending, yellow=current, green=passed)
- Progress bar showing confidence toward next threshold
- Manual "VERIFY" button on CLASSIFIED targets for operator override
- New state colors: `CLASSIFIED: '#f59e0b'`, `VERIFIED: '#10b981'`

**`state.js`** — Add `verificationThresholds` config (fetched from backend or hardcoded for display)

### 2.6 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] Targets appear as DETECTED with low confidence
- [ ] As more UAVs contribute sensors, confidence climbs → CLASSIFIED auto-promotion
- [ ] When second sensor type contributes → VERIFIED auto-promotion
- [ ] Only VERIFIED targets hit the strike board
- [ ] Manual "VERIFY" button fast-tracks a CLASSIFIED target
- [ ] Losing sensor contact → target regresses one state after timeout
- [ ] Demo timing feels natural (not too slow, not instant)

### 2.7 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/verification_engine.py` | **NEW** | ~120 |
| `src/python/sim_engine.py` | MODIFY | ~60 changed |
| `src/python/api_main.py` | MODIFY | ~40 changed |
| `src/frontend/enemies.js` | MODIFY | ~80 changed |
| `src/frontend/state.js` | MODIFY | ~10 changed |
| `src/python/tests/test_verification.py` | **NEW** | ~120 |

### 2.8 Risk Assessment

**Low risk**: Additive new states slot between existing ones. Only breaking change is that nominations require VERIFIED state (intentional — delays kill chain for better accuracy).

### 2.9 Dependencies

Requires Stage 1 (multi-sensor fusion) for the "2 different sensor types" verification criterion.

---

## Stage 3: Drone Modes — Human vs Autonomous

**Goal**: Comprehensive drone mode system with clear separation between human-commanded and autonomously-chosen modes. Operator can toggle between full manual control, supervised autonomy, and full autonomy per drone or fleet-wide.

### 3.1 Mode Architecture

#### Autonomy Levels (fleet-wide toggle)

| Level | Name | Behavior |
|-------|------|----------|
| 0 | **MANUAL** | All mode transitions require operator command. UAVs hold current mode until told otherwise. |
| 1 | **SUPERVISED** | System recommends mode transitions. Operator approves/rejects via notification. Auto-executes if no response in N seconds. |
| 2 | **AUTONOMOUS** | System freely transitions modes based on tactical situation. Operator can override any time. |

#### Complete Mode Table

| Mode | Human-Activated | Auto-Activated | Description | Orbit Radius |
|------|:-:|:-:|---|---|
| **IDLE** | - | Level 0+ | Loitering at assigned zone, no active task | 3km circle |
| **SEARCH** | - | Level 0+ | Scanning zone for targets (service timer) | 3km circle |
| **FOLLOW** | Level 0+ | Level 1+ | Loose orbit around target for observation | ~2km |
| **PAINT** | Level 0+ | Level 1+ | Tight orbit, laser/radar lock for targeting | ~1km |
| **INTERCEPT** | Level 0+ | Level 2 | Direct approach, danger close | ~300m |
| **SUPPORT** | Level 0+ | Level 1+ | **NEW** — En route to provide secondary sensor coverage | ~3km wide orbit |
| **VERIFY** | Level 0+ | Level 1+ | **NEW** — Dedicated verification pass: fly specific sensor geometry | varies by sensor |
| **OVERWATCH** | Level 0+ | Level 2 | **NEW** — Area denial: maintain persistent coverage of a zone | racetrack pattern |
| **BDA** | Level 0+ | Level 2 | **NEW** — Post-engagement assessment pass | tight orbit |
| **REPOSITIONING** | Level 0+ | Level 0+ | Transiting to new location | direct flight |
| **RTB** | Level 0+ | Level 0+ | Return to base (low fuel) | direct flight |

#### Mode Transitions (Autonomous)

```
                    ┌──────────────────────────────────────────┐
                    │                AUTONOMOUS                │
                    │         (system decides transitions)      │
                    └──────────────────────────────────────────┘

IDLE ──(target detected in zone)──→ SEARCH
SEARCH ──(detection confirmed)──→ FOLLOW
FOLLOW ──(verification needed)──→ VERIFY
FOLLOW ──(verified + nominated)──→ PAINT
PAINT ──(engagement complete)──→ BDA
BDA ──(assessment done)──→ SEARCH or IDLE
ANY ──(fuel < 2hrs)──→ RTB

                    ┌──────────────────────────────────────────┐
                    │           SWARM COORDINATOR              │
                    │        (sensor diversity logic)           │
                    └──────────────────────────────────────────┘

IDLE ──(swarm needs sensor type)──→ SUPPORT
SUPPORT ──(target verified)──→ SEARCH or FOLLOW
IDLE ──(coverage gap)──→ OVERWATCH
```

#### Mode Transition Rules

```python
AUTONOMOUS_TRANSITIONS = {
    # (current_mode, trigger) → new_mode
    ("IDLE", "target_detected_in_zone"):     "SEARCH",
    ("SEARCH", "high_confidence_detection"):  "FOLLOW",
    ("FOLLOW", "verification_gap"):           "VERIFY",
    ("FOLLOW", "target_verified_nominated"):  "PAINT",
    ("PAINT", "engagement_complete"):         "BDA",
    ("BDA", "assessment_complete"):           "SEARCH",
    ("IDLE", "swarm_support_requested"):      "SUPPORT",
    ("IDLE", "coverage_gap_detected"):        "OVERWATCH",
    ("SUPPORT", "target_verified"):           "SEARCH",
    ("ANY", "fuel_below_threshold"):          "RTB",
}
```

### 3.2 Autonomy Level Implementation

**`sim_engine.py` — SimulationModel**:
```python
class SimulationModel:
    def __init__(self, ...):
        self.autonomy_level: int = 1  # SUPERVISED default
        self.pending_transitions: list[dict] = []  # for SUPERVISED approval queue
```

**`api_main.py` — New WebSocket actions**:
```json
{"action": "set_autonomy_level", "level": 2}
{"action": "set_drone_autonomy", "drone_id": 5, "level": 0}
{"action": "approve_transition", "transition_id": "tr_001"}
{"action": "reject_transition", "transition_id": "tr_001"}
```

### 3.3 New Mode Behaviors (`sim_engine.py`)

**SUPPORT mode**:
- UAV flies toward target at cruise speed
- Enters wide orbit (~3km) to provide sensor data without interfering with primary tracker
- Automatically contributes to fusion for the target
- Releases back to SEARCH/IDLE when target verified or support no longer needed

**VERIFY mode**:
- UAV performs a specific sensor pass optimized for its sensor type:
  - EO_IR: fly perpendicular crossing pass for best aspect angle
  - SAR: maintain parallel track at optimal range for imaging
  - SIGINT: loiter within detection range, wait for emission cycle
- Returns to FOLLOW or SEARCH after verification window

**OVERWATCH mode**:
- UAV flies a racetrack pattern over assigned zone
- Wider coverage than SEARCH (elongated pattern vs circle)
- Maintains persistent presence — does not transition to IDLE after service timer
- Used to deny adversary freedom of movement in critical zones

**BDA mode**:
- Post-engagement assessment: tight orbit with maximum sensor dwell
- Reports damage assessment after engagement
- Automatically transitions out after assessment window (configurable, ~30s)

### 3.4 Frontend — Mode Control UI

**`dronelist.js`** — Enhanced drone card (when selected):

```
┌─────────────────────────────────┐
│ UAV-5              FOLLOW ●     │
│ FOLLOWING TGT-12                │
│─────────────────────────────────│
│ Alt: 3.00km  Sensor: EO/IR     │
│ Tracking: TGT-12               │
│ Coords: 26.1234, 44.5678       │
│─────────────────────────────────│
│ HUMAN MODES:                    │
│ [SEARCH] [FOLLOW] [PAINT]      │
│ [INTERCEPT] [VERIFY] [SUPPORT] │
│─────────────────────────────────│
│ AUTO MODES: (system-assigned)   │
│ [OVERWATCH] [BDA]              │
│─────────────────────────────────│
│ [Set Waypoint] [Range] [🎯]    │
└─────────────────────────────────┘
```

**Fleet autonomy toggle** (top of ASSETS tab):
```
AUTONOMY: [MANUAL] [SUPERVISED] [AUTONOMOUS]
                      ↑ active
```

**Transition notification** (SUPERVISED mode):
- When system recommends a transition, show a toast notification:
  ```
  RECOMMENDATION: UAV-7 → SUPPORT (TGT-5 needs SIGINT verification)
  [APPROVE] [REJECT] [AUTO in 15s]
  ```

### 3.5 WebSocket Protocol

UAV payload gains:
```json
{
  "id": 5,
  "mode": "SUPPORT",
  "autonomy_level": 1,
  "primary_target_id": 12,
  "tracked_target_ids": [12, 14],
  "mode_source": "AUTO",
  "pending_transition": null
}
```

New broadcast type:
```json
{
  "type": "TRANSITION_RECOMMENDATION",
  "transition_id": "tr_001",
  "uav_id": 7,
  "from_mode": "IDLE",
  "to_mode": "SUPPORT",
  "reason": "TGT-5 needs SIGINT verification",
  "auto_approve_sec": 15
}
```

### 3.6 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] Autonomy toggle works (MANUAL / SUPERVISED / AUTONOMOUS)
- [ ] In MANUAL: drones only change mode via operator commands
- [ ] In SUPERVISED: system recommends transitions, shows notification, auto-approves after timeout
- [ ] In AUTONOMOUS: drones freely transition between modes
- [ ] SUPPORT mode: drone flies to target, provides secondary sensor data
- [ ] VERIFY mode: drone performs sensor-specific pass
- [ ] OVERWATCH mode: racetrack pattern over zone
- [ ] BDA mode: post-engagement assessment, auto-transitions out
- [ ] All human-activated modes (FOLLOW, PAINT, etc.) still work in all autonomy levels
- [ ] Mode source indicator shows "HUMAN" vs "AUTO" on drone cards

### 3.7 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/sim_engine.py` | MODIFY | ~200 changed (new mode behaviors) |
| `src/python/api_main.py` | MODIFY | ~60 changed (new actions) |
| `src/frontend/dronelist.js` | MODIFY | ~100 changed (mode UI) |
| `src/frontend/drones.js` | MODIFY | ~30 changed (new mode colors) |
| `src/frontend/dronecam.js` | MODIFY | ~20 changed (new mode indicators) |
| `src/frontend/state.js` | MODIFY | ~10 changed |
| `src/python/tests/test_drone_modes.py` | **NEW** | ~150 |

### 3.8 Risk Assessment

**Medium risk**: New modes interact with zone-based repositioning and tracking logic. SUPPORT and OVERWATCH must not starve area coverage. Need minimum-idle-count constraint.

### 3.9 Dependencies

Requires Stage 1 (multi-sensor fusion) for SUPPORT mode sensor contribution. Requires Stage 2 (verification) for VERIFY mode triggers.

---

## Stage 4: Swarm Coordination & Intelligent Tasking

**Goal**: UAVs coordinate as a swarm to optimally cover the battlespace. System automatically tasks additional UAVs with complementary sensors to accelerate verification. Formation-based coverage.

### 4.1 New Module: `src/python/swarm_coordinator.py`

```python
class SwarmCoordinator:
    """Runs each tick after detection evaluation. Assigns UAVs to support targets."""

    def __init__(self, min_idle_count: int = 3):
        self.min_idle_count = min_idle_count  # minimum UAVs that must stay in SEARCH
        self.active_swarms: dict[int, SwarmTask] = {}  # target_id → swarm task

    def evaluate_and_assign(
        self,
        targets: list[Target],
        uavs: list[UAV],
        autonomy_level: int,
    ) -> list[TaskingOrder]:
        """Determine which UAVs should support which targets."""

    def _identify_sensor_gaps(self, target) -> set[str]:
        """What sensor types are missing for this target's verification?"""

    def _find_best_support_uav(self, target, needed_sensor: str, uavs) -> Optional[UAV]:
        """Greedy nearest-available with sensor-type match."""

@dataclass(frozen=True)
class SwarmTask:
    target_id: int
    assigned_uav_ids: tuple[int, ...]
    sensor_coverage: dict[str, bool]  # {"EO_IR": True, "SIGINT": False, "SAR": True}
    formation_type: str  # "WIDE_ORBIT", "TIGHT_ORBIT", "STAGGERED"

@dataclass(frozen=True)
class TaskingOrder:
    uav_id: int
    target_id: int
    mode: str           # "SUPPORT", "VERIFY", etc.
    reason: str
    priority: int       # 1=critical, 5=nice-to-have
```

### 4.2 Swarm Assignment Algorithm

Greedy assignment (O(N*M) — fine for 20 UAVs at 10Hz):

```
1. For each DETECTED/CLASSIFIED target:
   a. Identify missing sensor types for verification
   b. Score targets by: threat_level × (1 - fused_confidence) × time_detected

2. Sort targets by score (highest first)

3. For each target (highest priority first):
   a. Find nearest IDLE/SEARCH UAV with matching sensor type
   b. Skip if assigning would drop IDLE count below min_idle_count
   c. Issue TaskingOrder: UAV → SUPPORT → target
   d. Update sensor_coverage for the target

4. Return list of TaskingOrders
```

### 4.3 Integration into Tick Loop

```python
# sim_engine.py — SimulationModel.tick()
def tick(self):
    # ... existing steps 1-9 ...

    # 10. Swarm Coordination (after detection evaluation)
    if self.autonomy_level >= 1:  # SUPERVISED or AUTONOMOUS
        orders = self.swarm_coordinator.evaluate_and_assign(
            self.targets, self.uavs, self.autonomy_level
        )
        for order in orders:
            if self.autonomy_level == 2:  # AUTONOMOUS: execute immediately
                self._execute_tasking_order(order)
            else:  # SUPERVISED: queue for approval
                self.pending_transitions.append(order)
```

### 4.4 WebSocket Protocol

New fields in state broadcast:
```json
{
  "swarm_tasks": [
    {
      "target_id": 5,
      "assigned_uav_ids": [2, 7, 11],
      "sensor_coverage": {"EO_IR": true, "SAR": true, "SIGINT": false},
      "formation_type": "WIDE_ORBIT"
    }
  ]
}
```

New WebSocket actions:
```json
{"action": "request_swarm_support", "target_id": 5}
{"action": "release_swarm", "target_id": 5}
```

### 4.5 Frontend — Swarm Visualization

**`drones.js`** — Map:
- Formation lines between UAVs assigned to same target (dashed cyan polylines)
- SUPPORT mode color: teal (`#14b8a6`)
- VERIFY mode color: amber (`#f59e0b`)
- OVERWATCH mode color: indigo (`#6366f1`)
- BDA mode color: gray-blue (`#475569`)

**New module: `src/frontend/swarm.js`**:
- Swarm overview panel (slide-out or tab)
- Per-target sensor coverage indicator: icons for EO_IR/SAR/SIGINT, filled when contributing
- "Request Swarm" button on target cards (enemies.js)
- Active swarm list showing formation status

### 4.6 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] Single EO_IR UAV detects target → system dispatches SIGINT + SAR UAVs
- [ ] Formation lines appear on map between swarm members
- [ ] As supporting UAVs arrive, sensor coverage fills in
- [ ] Target rapidly promotes through CLASSIFIED → VERIFIED
- [ ] "Request Swarm" button causes rapid convergence on a specific target
- [ ] "Release Swarm" disperses supporting UAVs back to area coverage
- [ ] Minimum idle count is respected (not all UAVs swarm one target)

### 4.7 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/swarm_coordinator.py` | **NEW** | ~300 |
| `src/python/sim_engine.py` | MODIFY | ~80 changed |
| `src/python/api_main.py` | MODIFY | ~40 changed |
| `src/frontend/swarm.js` | **NEW** | ~200 |
| `src/frontend/drones.js` | MODIFY | ~40 changed |
| `src/frontend/enemies.js` | MODIFY | ~30 changed |
| `src/frontend/app.js` | MODIFY | ~10 changed (import swarm.js) |
| `src/python/tests/test_swarm_coordinator.py` | **NEW** | ~150 |

### 4.8 Risk Assessment

**Medium risk**: Swarm coordination interacts with zone-based repositioning (`calculate_macro_flow`). Must ensure swarm tasks take priority over zone balancing without starving area coverage.

### 4.9 Dependencies

Requires Stage 1 (fusion) + Stage 2 (verification) + Stage 3 (modes).

---

## Stage 5: Information Feeds & Communication Channels

**Goal**: Upgrade from a single 10Hz state broadcast to multiple specialized feed types. Rich information channels for different consumers with appropriate update rates and filtering.

### 5.1 Feed Architecture

```
                    ┌──────────────────────────────┐
                    │       WebSocket Server        │
                    │      (api_main.py)            │
                    └─────────┬────────────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
   STATE_FEED            INTEL_FEED             SENSOR_FEED
   (10Hz)               (event-driven)          (per-UAV)
   Full sim state       Target intel updates    Raw sensor data
   All clients          Dashboard only          Per-subscription
```

### 5.2 Feed Types

#### STATE_FEED (existing, enhanced)
- **Rate**: 10Hz (unchanged)
- **Content**: UAV positions, target positions, zones, flows, environment
- **Consumer**: Dashboard (overview mode)
- **Change**: Add fusion data, swarm tasks, autonomy state

#### INTEL_FEED (new)
- **Rate**: Event-driven (fires on state changes, not every tick)
- **Content**: Target state transitions, verification progress, threat assessments, strike board updates
- **Consumer**: Dashboard (intelligence panel)
- **Events**:
  ```json
  {"type": "INTEL_FEED", "event": "TARGET_CLASSIFIED", "target_id": 5, "confidence": 0.72, "sensor_types": ["EO_IR", "SIGINT"]}
  {"type": "INTEL_FEED", "event": "TARGET_VERIFIED", "target_id": 5, "confidence": 0.91, "verification_method": "multi_sensor"}
  {"type": "INTEL_FEED", "event": "SWARM_DISPATCHED", "target_id": 5, "uav_ids": [2, 7]}
  {"type": "INTEL_FEED", "event": "THREAT_CLUSTER_DETECTED", "cluster_id": "cl_1", "type": "SAM_BATTERY", "center": [26.1, 44.5]}
  ```

#### SENSOR_FEED (new)
- **Rate**: Per-UAV, 2Hz (every 5th tick)
- **Content**: Raw detection results per UAV — what each sensor is seeing
- **Consumer**: Dashboard (per-drone detail view, drone cam)
- **Subscription**: Client subscribes to specific UAV IDs
  ```json
  {"action": "subscribe_sensor_feed", "uav_ids": [5, 7]}
  {"action": "unsubscribe_sensor_feed", "uav_ids": [5]}
  ```
- **Payload**:
  ```json
  {
    "type": "SENSOR_FEED",
    "uav_id": 5,
    "sensor_type": "EO_IR",
    "detections": [
      {"target_id": 12, "confidence": 0.72, "range_m": 8500, "bearing_deg": 45.2},
      {"target_id": 14, "confidence": 0.31, "range_m": 22000, "bearing_deg": 120.8}
    ],
    "coverage_arc": {"center_deg": 45.2, "width_deg": 60},
    "environment_quality": 0.85
  }
  ```

#### COMMAND_FEED (new)
- **Rate**: Event-driven
- **Content**: All command executions, mode transitions, autonomy decisions
- **Consumer**: Dashboard (command log / audit trail)
- **Payload**:
  ```json
  {
    "type": "COMMAND_FEED",
    "event": "MODE_TRANSITION",
    "uav_id": 7,
    "from_mode": "IDLE",
    "to_mode": "SUPPORT",
    "source": "SWARM_COORDINATOR",
    "reason": "TGT-5 needs SIGINT verification",
    "timestamp": "14:32:05"
  }
  ```

#### DRONE_VIDEO_FEED (existing, enhanced)
- **Rate**: 30fps per subscribed drone
- **Content**: Synthetic camera view from drone perspective
- **Enhancement**: Overlay fused target data, sensor contributions, verification status on the drone cam HUD

### 5.3 Backend Implementation

**`api_main.py`** — Feed management:
```python
# Client subscriptions
client_subscriptions: dict[WebSocket, set[str]] = {}  # ws → {"STATE_FEED", "INTEL_FEED", ...}
sensor_subscriptions: dict[WebSocket, set[int]] = {}  # ws → {5, 7}  (UAV IDs)

# Event emitter for INTEL_FEED
class IntelFeedEmitter:
    def __init__(self):
        self._last_target_states: dict[int, str] = {}

    def check_and_emit(self, targets: list[dict]) -> list[dict]:
        """Compare current states to last known, emit events on changes."""
```

**Feed subscription protocol**:
```json
{"action": "subscribe", "feeds": ["STATE_FEED", "INTEL_FEED", "COMMAND_FEED"]}
{"action": "subscribe_sensor_feed", "uav_ids": [5, 7]}
```

Default on connect: `STATE_FEED` + `INTEL_FEED` + `COMMAND_FEED` (backward compatible).

### 5.4 Frontend — Feed Integration

**Intel Panel** (new sidebar section or tab):
- Real-time intelligence feed showing target state transitions
- Filterable by event type, target, severity
- Color-coded entries (green=verification progress, yellow=new contact, red=threat escalation)
- Clickable entries jump to target on map

**Command Log** (new collapsible panel):
- Audit trail of all commands (human and autonomous)
- Shows source (HUMAN, SWARM_COORD, AUTOPILOT)
- Filterable by UAV or action type

**Drone Cam Enhancements** (`dronecam.js`):
- Overlay fused confidence bar on tracked targets
- Show sensor contribution icons (which sensors see this target)
- Verification progress indicator on HUD
- Multi-target tracking: show all detected targets with bounding boxes, not just the tracked one
- Sensor FOV cone visualization on the HUD

**Sensor Coverage Map** (new Cesium layer):
- Per-UAV sensor cone visualization on the map
- Overlapping cones show where multi-sensor coverage exists
- Coverage gaps highlighted (areas with no sensor presence)

### 5.5 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] Intel feed shows real-time target state transitions
- [ ] Command log shows all mode transitions with source attribution
- [ ] Sensor feed subscription works (select drone → see its raw detections)
- [ ] Drone cam shows fused confidence and multi-target bounding boxes
- [ ] Sensor coverage cones visible on map
- [ ] Feed filtering works (filter by target, event type)
- [ ] No performance degradation from additional feeds

### 5.6 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/api_main.py` | MODIFY | ~150 changed (feed system) |
| `src/python/intel_feed.py` | **NEW** | ~100 |
| `src/frontend/feeds.js` | **NEW** | ~200 (intel panel, command log) |
| `src/frontend/dronecam.js` | MODIFY | ~80 changed (enhanced HUD) |
| `src/frontend/map.js` | MODIFY | ~60 changed (sensor coverage cones) |
| `src/frontend/app.js` | MODIFY | ~15 changed (wire feeds.js) |
| `src/frontend/sidebar.js` | MODIFY | ~20 changed (new tabs) |
| `src/frontend/index.html` | MODIFY | ~30 changed (new panels) |
| `src/python/tests/test_feeds.py` | **NEW** | ~80 |

### 5.7 Risk Assessment

**Low-medium risk**: Additional WebSocket traffic could impact performance. Mitigation: feeds are subscribe-only (clients opt in), sensor feed is throttled to 2Hz, state feed remains at 10Hz.

### 5.8 Dependencies

Requires Stages 1-4 (fusion data, verification states, modes, swarm tasks to feed).

---

## Stage 6: Battlespace Assessment & Threat Picture

**Goal**: Live Common Operating Picture (COP) that synthesizes all target data into threat clusters, identifies patterns, and provides a holistic threat picture.

### 6.1 New Module: `src/python/battlespace_assessment.py`

```python
class BattlespaceAssessor:
    """Processes all verified targets to produce the COP."""

    def __init__(self, assessment_interval_sec: float = 5.0):
        self._last_assessment_time = 0.0
        self.threat_clusters: list[ThreatCluster] = []
        self.coverage_gaps: list[CoverageGap] = []
        self.zone_threat_scores: dict[tuple, float] = {}
        self.movement_corridors: list[MovementCorridor] = []

    def tick(self, targets, uavs, zones, now: float) -> Optional[BattlespaceAssessment]:
        """Run assessment if interval has elapsed. Returns None otherwise."""

    def _cluster_targets(self, targets) -> list[ThreatCluster]:
        """Distance-based clustering with type affinity."""

    def _identify_coverage_gaps(self, uavs, zones) -> list[CoverageGap]:
        """Zones with no UAV coverage and unknown threat status."""

    def _score_zone_threats(self, targets, zones) -> dict[tuple, float]:
        """Aggregate threat score per grid zone."""

    def _detect_movement_corridors(self, targets) -> list[MovementCorridor]:
        """Identify patrol routes from mobile target movement history."""

@dataclass(frozen=True)
class ThreatCluster:
    cluster_id: str
    target_ids: tuple[int, ...]
    center_lon: float
    center_lat: float
    radius_m: float
    cluster_type: str           # "SAM_BATTERY", "CONVOY", "CP_COMPLEX", "AD_NETWORK"
    threat_score: float         # 0.0 - 1.0
    component_types: tuple[str, ...]

@dataclass(frozen=True)
class CoverageGap:
    zone_id: tuple[int, int]
    center_lon: float
    center_lat: float
    last_surveyed_sec_ago: float
    estimated_threat_level: str  # "UNKNOWN", "LOW", "MEDIUM", "HIGH"

@dataclass(frozen=True)
class MovementCorridor:
    corridor_id: str
    waypoints: tuple[tuple[float, float], ...]  # (lon, lat) sequence
    target_type: str            # "TRUCK", "LOGISTICS"
    activity_level: float       # 0.0 - 1.0

@dataclass(frozen=True)
class BattlespaceAssessment:
    threat_clusters: tuple[ThreatCluster, ...]
    coverage_gaps: tuple[CoverageGap, ...]
    zone_threat_scores: dict[tuple, float]
    movement_corridors: tuple[MovementCorridor, ...]
    timestamp: float
```

### 6.2 Clustering Algorithm

DBSCAN-like with type affinity:

```
1. Group targets by type affinity:
   SAM_BATTERY: {SAM, RADAR, CP} within 5km
   CONVOY: {TRUCK, LOGISTICS} within 3km on similar heading
   CP_COMPLEX: {CP, C2_NODE} within 3km
   AD_NETWORK: {SAM, RADAR, MANPADS} within 10km

2. For each affinity group:
   a. Start with highest-priority ungrouped target
   b. Find all targets within radius that match affinity types
   c. If cluster has 2+ targets, create ThreatCluster
   d. Compute center, radius, threat_score

3. Threat scoring:
   threat_score = sum(type_weight * verification_level) / max_possible
   where type_weight = {SAM: 1.0, RADAR: 0.9, TEL: 0.8, CP: 0.7, ...}
```

### 6.3 Wire into Runtime

**`sim_engine.py`** — Add to tick (or separate 5s timer):
```python
# Target movement history for corridor detection
for t in self.targets:
    t.position_history.append((t.x, t.y, now))  # bounded deque, ~60 entries
```

**`api_main.py`** — Add to state broadcast:
```json
{
  "battlespace_assessment": {
    "threat_clusters": [...],
    "coverage_gaps": [...],
    "zone_threat_scores": {"2,3": 0.8, "1,4": 0.2},
    "movement_corridors": [...]
  }
}
```

### 6.4 Wire Existing Agents

**`agents/battlespace_manager.py`**:
- Activate heuristic threat ring generation from verified SAM/RADAR positions
- Feed threat rings from Stage 6 assessment into tactical planner for COA safe paths

**`agents/pattern_analyzer.py`** (if exists):
- Wire movement history into anomaly detection
- Feed pattern analysis results into the COP

### 6.5 Frontend — Assessment Visualization

**New module: `src/frontend/assessment.js`**:

**Threat clusters** — Cesium convex hull overlays:
- Colored semi-transparent polygons around grouped targets
- SAM_BATTERY = red, CONVOY = orange, CP_COMPLEX = yellow, AD_NETWORK = purple
- Label showing cluster type and threat score
- Click to see cluster details

**Movement corridors** — Polylines:
- Dashed lines following detected patrol routes
- Color by target type (TRUCK=white, LOGISTICS=gray)
- Width by activity level

**Coverage gaps** — Zone overlay:
- Red-hatched zones where UAV coverage is absent
- Darker red for zones with HIGH estimated threat

**Zone threat heatmap** — Replace or augment current imbalance coloring:
- Blue (low threat) → yellow (medium) → red (high threat)
- Toggle between "imbalance view" and "threat view"

**ASSESSMENT tab** (new sidebar tab):
- Threat cluster summary cards
- Top 3 threats with details
- Coverage gap alerts
- Pattern anomaly feed
- Zone threat overview

### 6.6 Demo Checkpoint

Run `./grid-sentinel.sh --demo` and verify:
- [ ] SAM + RADAR + CP auto-clustered as "SAM_BATTERY" with convex hull
- [ ] Truck patrol routes rendered as movement corridors
- [ ] Coverage gap overlay highlights unsurveyed zones
- [ ] Zone threat heatmap shows threat density
- [ ] ASSESSMENT tab shows real-time threat summary
- [ ] Clicking a cluster selects all member targets
- [ ] Threat score updates as targets are verified/neutralized

### 6.7 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/battlespace_assessment.py` | **NEW** | ~350 |
| `src/python/sim_engine.py` | MODIFY | ~40 changed (position history) |
| `src/python/api_main.py` | MODIFY | ~40 changed (assessment broadcast) |
| `src/python/agents/battlespace_manager.py` | MODIFY | ~60 changed (activate heuristics) |
| `src/frontend/assessment.js` | **NEW** | ~300 |
| `src/frontend/map.js` | MODIFY | ~80 changed (heatmap, hulls) |
| `src/frontend/sidebar.js` | MODIFY | ~20 changed (new tab) |
| `src/frontend/index.html` | MODIFY | ~20 changed |
| `src/frontend/app.js` | MODIFY | ~15 changed |
| `src/python/tests/test_battlespace.py` | **NEW** | ~120 |

### 6.8 Risk Assessment

**Low risk**: Mostly additive read-only overlay on existing data. No changes to core simulation or tracking. 5-second assessment interval prevents performance overhead. Convex hull rendering needs Cesium `GroundPrimitive` batch rendering for performance.

### 6.9 Dependencies

Requires Stage 2 (verification states) so assessment operates on verified data. Benefits from Stage 4 (swarm) to address coverage gaps automatically.

---

## Stage 7: Adaptive ISR & Closed-Loop Intelligence

**Goal**: Close the loop. The system uses the battlespace assessment to autonomously prioritize targets, dynamically retask the swarm, and adapt ISR coverage based on the evolving threat picture. The capstone that ties everything together.

### 7.1 Activate AI Tasking Manager

**`agents/ai_tasking_manager.py`** — Implement `_generate_response_heuristic()`:

```python
def _generate_response_heuristic(self, detection, available_assets):
    """
    Ranks targets by verification gap and matches UAV sensor capabilities.
    """
    # 1. Score all DETECTED/CLASSIFIED targets:
    #    score = threat_weight × (1 - fused_confidence) × time_since_detection

    # 2. For each high-scoring target:
    #    a. Identify missing sensor types
    #    b. Find nearest UAV with matching sensor
    #    c. Issue SensorTaskingOrder

    # 3. Return orders sorted by priority
```

### 7.2 Adaptive Coverage Mode

**`sim_engine.py`** — New coverage algorithm:

```python
class SimulationModel:
    def __init__(self, ...):
        self.coverage_mode: str = "balanced"  # "balanced" | "threat_adaptive"

    def _adaptive_coverage(self):
        """Redistribute IDLE UAVs based on threat assessment instead of queue imbalance."""
        assessment = self.battlespace_assessor.latest
        if not assessment:
            return self.grid.calculate_macro_flow(dt_sec)  # fallback

        # Priority zones: coverage gaps with high threat + zones near threat clusters
        priority_zones = sorted(
            assessment.coverage_gaps,
            key=lambda g: g.estimated_threat_level_score,
            reverse=True
        )

        # Dispatch IDLE UAVs to highest priority coverage gaps
        for gap in priority_zones:
            idle_nearby = [u for u in self.uavs if u.mode == "IDLE" and ...]
            if idle_nearby:
                u = idle_nearby[0]
                u.mode = "OVERWATCH"
                u.target = (gap.center_lon, gap.center_lat)
```

### 7.3 ISR Priority Queue

The AI tasking manager maintains a priority queue of intelligence needs:

```python
@dataclass
class IntelRequirement:
    target_id: int
    required_sensor_types: set[str]
    priority: float          # 0.0 - 1.0
    reason: str
    deadline_sec: float      # time before requirement expires

class ISRPriorityQueue:
    def __init__(self):
        self.requirements: list[IntelRequirement] = []

    def add_from_assessment(self, assessment: BattlespaceAssessment):
        """Generate intel requirements from coverage gaps and unverified threats."""

    def get_next(self) -> Optional[IntelRequirement]:
        """Pop highest priority requirement."""
```

### 7.4 WebSocket Protocol

New actions:
```json
{"action": "set_coverage_mode", "mode": "threat_adaptive"}
{"action": "override_tasking", "uav_id": 7, "target_id": 5}
```

New state fields:
```json
{
  "coverage_mode": "threat_adaptive",
  "isr_priority_queue": [
    {"target_id": 5, "priority": 0.9, "reason": "SAM battery partially verified"},
    {"target_id": 12, "priority": 0.6, "reason": "Coverage gap in Zone B3"}
  ]
}
```

### 7.5 Frontend — Adaptive ISR UI

**Assistant panel** — Retasking feed:
```
14:32:05 RETASK: UAV-7 (SIGINT) → Zone B3
         Reason: SAM battery partially verified, SIGINT confirmation needed
14:32:12 COVERAGE: UAV-3 → OVERWATCH Zone C1
         Reason: No coverage for 45s, adjacent to threat cluster CL-1
14:32:20 VERIFY: UAV-11 (SAR) → TGT-5
         Reason: Classification uncertain, SAR imaging pass requested
```

**Coverage mode toggle** (ASSETS tab):
```
COVERAGE: [BALANCED] [THREAT ADAPTIVE]
                        ↑ active
```

**ISR Priority Queue** (ASSESSMENT tab):
- List of outstanding intelligence requirements
- Shows which UAV is assigned, ETA, and priority
- Operator can promote/demote requirements

**Drone list** — Per-UAV tasking status:
```
UAV-7  SUPPORT  [AUTO: Swarm Coord]  TGT-5
UAV-3  OVERWATCH [AUTO: Coverage]     Zone C1
UAV-11 VERIFY   [AUTO: ISR Queue]    TGT-5
UAV-2  FOLLOW   [HUMAN]              TGT-12
```

### 7.6 Demo Checkpoint — Full Integration

Run `./grid-sentinel.sh --demo` and verify the complete loop:

1. **Detection**: UAVs spread across battlespace, detecting targets
2. **Fusion**: Multiple UAVs contribute detections, fused confidence rises
3. **Verification**: Targets auto-promote through DETECTED → CLASSIFIED → VERIFIED
4. **Swarm**: System dispatches complementary sensor UAVs to accelerate verification
5. **Assessment**: Verified targets cluster into threat groups (SAM batteries, convoys)
6. **Adaptive ISR**: System identifies coverage gaps and retasks UAVs
7. **Nomination**: Only VERIFIED targets hit the strike board
8. **Engagement**: Full F2T2EA kill chain with BDA assessment pass
9. **Loop**: BDA results feed back into assessment, coverage adapts

Specific scenarios to verify:
- [ ] Partial SAM battery detected → AI dispatches SIGINT UAV to verify RADAR → assessment updates cluster
- [ ] Coverage gap in south → automatic UAV redistribution via OVERWATCH
- [ ] Toggle balanced/threat-adaptive → UAVs shift from uniform to threat-focused clustering
- [ ] Operator overrides autonomous tasking → system respects override
- [ ] All three autonomy levels work (MANUAL/SUPERVISED/AUTONOMOUS)
- [ ] Intel feed shows complete audit trail of all decisions
- [ ] Command feed shows attribution (HUMAN vs AUTO vs SWARM_COORD)
- [ ] Assessment tab provides holistic threat picture
- [ ] Performance is acceptable (no jitter at 10Hz)

### 7.7 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/python/agents/ai_tasking_manager.py` | MODIFY | ~100 changed |
| `src/python/agents/battlespace_manager.py` | MODIFY | ~80 changed |
| `src/python/isr_priority.py` | **NEW** | ~120 |
| `src/python/sim_engine.py` | MODIFY | ~80 changed |
| `src/python/api_main.py` | MODIFY | ~60 changed |
| `src/frontend/feeds.js` | MODIFY | ~60 changed |
| `src/frontend/dronelist.js` | MODIFY | ~40 changed |
| `src/frontend/assessment.js` | MODIFY | ~40 changed |
| `src/python/tests/test_adaptive_isr.py` | **NEW** | ~120 |

### 7.8 Risk Assessment

**High risk**: Changes the fundamental UAV assignment logic. Zone-imbalance system is deeply integrated. Need extensive testing to ensure threat-adaptive mode doesn't create coverage black holes. Agent activation may surface edge cases in heuristic logic.

### 7.9 Dependencies

Requires all prior stages. This is the capstone.

---

## Stage 8: Map Modes & Tactical Views

**Goal**: Multiple map visualization modes that operators can toggle between, each optimized for a different tactical need. Transform the single dark-tile view into a multi-layered tactical display.

### 8.1 Map View Modes

Toggled via a mode selector bar at the top of the map (keyboard shortcuts in parentheses):

| Mode | Key | What It Shows | When to Use |
|------|-----|---------------|-------------|
| **OPERATIONAL** (default) | `1` | Current view: dark tiles, drone pins, target cylinders, zone grid, flow lines | General ops, default on load |
| **ISR COVERAGE** | `2` | Sensor coverage cones per UAV overlaid on map. Overlapping areas highlighted green. Gaps highlighted red-hatched. Confidence heatmap under cones. | Planning sensor coverage, identifying blind spots |
| **THREAT** | `3` | Zone threat heatmap (from Stage 6 battlespace assessment). Threat clusters as convex hulls. SAM engagement envelopes as red circles. Movement corridors as dashed polylines. | Threat awareness, route planning |
| **FUSION** | `4` | Per-target fusion rings showing sensor count. Lines connecting each contributing UAV to the target. Color-coded by sensor type. Verification progress bars floating above targets. | Monitoring verification pipeline |
| **SWARM** | `5` | Swarm formation lines. UAV-to-target assignment arrows. Sensor diversity indicators per target. Idle/available UAV count per zone. | Managing swarm tasking |
| **TERRAIN** | `6` | Cesium world terrain with elevation shading. Line-of-sight analysis from selected UAV. Terrain masking visualization (areas hidden from sensor by terrain). | Terrain analysis, LOS planning |

### 8.2 Layer Architecture

Each mode is a **preset** that toggles multiple Cesium layers on/off:

```javascript
const MAP_MODES = {
    OPERATIONAL: {
        layers: ['zones', 'drones', 'targets', 'flows', 'compass'],
        zoneColorMode: 'imbalance',  // red/blue imbalance
    },
    ISR_COVERAGE: {
        layers: ['drones', 'targets', 'sensorCones', 'coverageHeatmap', 'coverageGaps'],
        zoneColorMode: 'none',
    },
    THREAT: {
        layers: ['drones', 'targets', 'threatHeatmap', 'threatClusters', 'samEnvelopes', 'corridors'],
        zoneColorMode: 'threat',  // blue-yellow-red threat score
    },
    FUSION: {
        layers: ['drones', 'targets', 'fusionRings', 'sensorLines', 'verificationBars'],
        zoneColorMode: 'none',
    },
    SWARM: {
        layers: ['drones', 'targets', 'formationLines', 'assignmentArrows', 'sensorDiversity'],
        zoneColorMode: 'availability',  // idle UAV count
    },
    TERRAIN: {
        layers: ['drones', 'targets', 'terrain3d', 'losAnalysis', 'terrainMasking'],
        zoneColorMode: 'none',
    },
};
```

Individual layers can also be toggled independently via a layer panel (like a GIS layer control).

### 8.3 New Cesium Layers

**Sensor Coverage Cones** (`src/frontend/layers/coverage.js`):
- Per-UAV cone projected from drone position to ground
- EO_IR: 60° FOV cone, 50km range (matches `HFOV_DEG` and `SENSOR_RANGE_KM` in dronecam.js)
- SAR: 45° side-looking swath, 100km range
- SIGINT: 360° circle, 200km range
- Color by sensor type (EO_IR=blue, SAR=green, SIGINT=yellow)
- Overlapping zones show combined coverage intensity

**Threat Heatmap** (`src/frontend/layers/threat.js`):
- Zone-based heatmap replacing imbalance coloring
- Colors: transparent (no threat) → blue (low) → yellow (medium) → red (high)
- Data source: `battlespace_assessment.zone_threat_scores`

**SAM Engagement Envelopes** (`src/frontend/layers/threat.js`):
- Circle around each verified SAM/RADAR at engagement range
- SAM: 30km radius red circle (typical SA-series)
- MANPADS: 5km radius pink circle
- Semi-transparent fill with dashed outline

**Line-of-Sight Analysis** (`src/frontend/layers/terrain.js`):
- When drone selected in TERRAIN mode, compute LOS to each target
- Green line = clear LOS, red line = terrain-blocked
- Uses Cesium terrain sampling for elevation data
- Terrain masking overlay: areas invisible to selected drone shaded dark

**Fusion Rings & Sensor Lines** (`src/frontend/layers/fusion.js`):
- Concentric rings around targets: one ring per contributing sensor
- Dashed lines from each contributing UAV to the target, colored by sensor type
- Floating verification progress bar above target entity

### 8.4 Camera Presets

Quick camera position presets (accessible via buttons or keyboard):

| Preset | Key | Description |
|--------|-----|-------------|
| **Theater Overview** | `Home` | Full theater view, -45° pitch, fits all entities |
| **Follow Drone** | Click drone | Macro tracking (current behavior, smooth camera follow) |
| **Third Person** | Double-click drone | Chase cam behind drone (current behavior) |
| **Top-Down** | `T` | Directly overhead (-90° pitch), current center point |
| **Oblique** | `O` | 30° pitch view from current position (good for terrain awareness) |
| **Free Camera** | `F` | Unlock camera from any tracking, free roam |
| **Target Focus** | Click target | Fly to target with 45° pitch at 1km range |
| **Cluster View** | Click cluster hull | Zoom to fit threat cluster with padding |

### 8.5 Map Overlay Controls

**Layer panel** (collapsible, bottom-left of map):
```
MAP LAYERS                    [▼]
─────────────────────────────────
☑ Zone Grid         ☑ Drone Labels
☑ Flow Lines        ☑ Target Labels
☐ Sensor Cones      ☐ SAM Envelopes
☐ Threat Heatmap    ☐ Coverage Gaps
☐ Formation Lines   ☐ LOS Analysis
☐ Movement Corridors ☐ Fusion Rings
─────────────────────────────────
MODE: [OPS][ISR][THR][FUS][SWM][TER]
```

### 8.6 Frontend Implementation

**New module: `src/frontend/mapmode.js`** (~250 lines):
- `setMapMode(mode)` — activates/deactivates layers per preset
- `toggleLayer(layerName)` — individual layer toggle
- `getActiveMode()` — returns current mode
- Keyboard shortcuts via document keydown listener

**New directory: `src/frontend/layers/`**:
- `coverage.js` — sensor cone rendering (~150 lines)
- `threat.js` — threat heatmap + SAM envelopes (~150 lines)
- `fusion.js` — fusion rings + sensor lines (~120 lines)
- `terrain.js` — LOS analysis + terrain masking (~150 lines)
- `swarm.js` — formation lines + assignment arrows (from Stage 4 `swarm.js`, refactored)

### 8.7 Demo Checkpoint

- [ ] Mode selector bar visible, keyboard shortcuts work
- [ ] ISR COVERAGE mode shows sensor cones and coverage gaps
- [ ] THREAT mode shows heatmap and SAM envelopes
- [ ] FUSION mode shows rings and sensor contribution lines
- [ ] SWARM mode shows formation lines and assignment arrows
- [ ] TERRAIN mode shows LOS analysis from selected drone
- [ ] Camera presets work (Top-Down, Oblique, Free Camera)
- [ ] Individual layer toggles work independently of mode
- [ ] Mode switching is instant (no reload, just layer visibility toggle)
- [ ] Performance acceptable with all layers active

### 8.8 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/frontend/mapmode.js` | **NEW** | ~250 |
| `src/frontend/layers/coverage.js` | **NEW** | ~150 |
| `src/frontend/layers/threat.js` | **NEW** | ~150 |
| `src/frontend/layers/fusion.js` | **NEW** | ~120 |
| `src/frontend/layers/terrain.js` | **NEW** | ~150 |
| `src/frontend/map.js` | MODIFY | ~60 changed (layer management hooks) |
| `src/frontend/app.js` | MODIFY | ~20 changed (imports, mode init) |
| `src/frontend/index.html` | MODIFY | ~40 changed (mode bar, layer panel) |
| `src/frontend/style.css` | MODIFY | ~80 changed (mode bar, layer panel styles) |

### 8.9 Dependencies

Requires Stage 1 (fusion data for FUSION mode), Stage 4 (swarm data for SWARM mode), Stage 6 (assessment data for THREAT mode). Can implement OPERATIONAL and TERRAIN modes independently.

---

## Stage 9: Upgraded Simulated Drone Feeds

**Goal**: Transform the current synthetic drone camera from a simple projection overlay into a rich, multi-mode sensor feed with realistic HUD elements, sensor switching, multi-target tracking, and picture-in-picture layouts.

### 9.1 Current Drone Cam State

The existing `dronecam.js` (351 lines) renders:
- Green-tinted canvas with grid lines
- Target symbols projected based on bearing/range from drone's perspective
- HUD with telemetry (ID, ALT, HDG, MODE, coords)
- Tracking reticle on followed target
- Pulsing red lock box in PAINT mode
- Corner brackets for tactical frame

### 9.2 Sensor Feed Modes

Each drone has a sensor type. The camera feed should reflect what that sensor actually "sees":

| Sensor Mode | Visual Style | Information Overlay |
|-------------|-------------|-------------------|
| **EO/IR (Electro-Optical/Infrared)** | Green-tinted thermal imagery (current style, enhanced). Hot targets glow white/bright. Background terrain has thermal noise texture. Day/night affects contrast. | Target bounding boxes, confidence bars, classification labels |
| **SAR (Synthetic Aperture Radar)** | Orange/amber radar return imagery. Terrain shows as radar echo texture. Moving targets show velocity vectors. Static targets show sharp returns. | Coherent change detection highlights, RCS values, range rings |
| **SIGINT (Signals Intelligence)** | Dark blue spectrum display. No visual scene — shows signal waterfall/spectrum instead. Detected emissions as frequency peaks. | Emitter classification, signal strength, bearing lines, frequency bands |
| **MULTI-SENSOR FUSION** | Split-screen or overlay combining all contributing sensors on a target. Available when multiple UAVs observe same target. | Fused confidence meter, per-sensor contribution bars, verification status |

### 9.3 Enhanced HUD Elements

#### Standard HUD (all modes)
```
┌─────────────────────────────────────────────────────────┐
│ UAV-5  EO/IR          14:32:05Z     44.5678N 26.1234E  │
│ ALT: 3.0km  HDG: 045  SPD: 120kn              MODE: FW │
│                                                         │
│ ┌─COMPASS TAPE──────────────────────────────────────┐   │
│ │    N    030    060    E    120    150    S         │   │
│ └───────────────────────▲───────────────────────────┘   │
│                                                         │
│              ┌──────────┐                               │
│              │  TARGET   │                               │
│              │  BOX      │                               │
│              └──────────┘                               │
│                                                         │
│ ┌─TARGET INFO─────────────┐  ┌─SENSOR STATUS──────────┐│
│ │ TGT: SAM #5             │  │ SENSOR: EO/IR          ││
│ │ STATE: CLASSIFIED       │  │ QUALITY: 85%           ││
│ │ RNG: 8.5km BRG: 045    │  │ FUSED: 3 SENSORS       ││
│ │ FUSED CONF: 0.82       │  │ VERIF: ████████░░ 80%  ││
│ │ ░░░░░░░░████ 82%       │  │ [EO] [SAR] [---]       ││
│ └─────────────────────────┘  └────────────────────────┘│
│                                                         │
│ FUEL: ████████████████░░░░ 16.2h        AUTONOMY: SUP  │
└─────────────────────────────────────────────────────────┘
```

#### New HUD Components

**Compass tape** (top): horizontal compass strip showing heading with bearing markers to tracked targets.

**Sensor status panel** (bottom-right):
- Current sensor type and quality (affected by weather, range)
- Fused sensor count (how many UAVs contributing to current target)
- Verification progress bar
- Sensor type icons showing which modalities are active

**Fuel gauge** (bottom): horizontal bar showing remaining endurance.

**Multi-target indicators**: All detected targets in FOV get bounding boxes, not just the tracked one. Primary target gets reticle + lock box. Secondary targets get dashed boxes.

**Threat warning**: Flash "THREAT" indicator when drone enters SAM engagement envelope.

### 9.4 Drone Cam Layouts

Switchable via buttons on the drone cam panel:

| Layout | Description |
|--------|-------------|
| **SINGLE** | Full-frame single sensor feed (current, enhanced) |
| **PIP** | Primary feed full-frame + small picture-in-picture of different sensor on same target (e.g., EO/IR main + SIGINT PIP from supporting UAV) |
| **SPLIT** | Side-by-side: two sensor feeds on same target from different UAVs |
| **QUAD** | 2x2 grid: up to 4 drone feeds simultaneously (select which 4 drones) |
| **OVERVIEW** | Wide-angle simplified view of all drones' FOVs on a 2D tactical map |

### 9.5 Synthetic Scene Enhancement

**Terrain texture**: Instead of flat dark green, generate procedural terrain noise based on drone altitude and heading. Mountains/valleys affect thermal signature visibility.

**Target rendering**:
- Size scales with range (closer = larger bounding box)
- Moving targets show velocity vector arrow
- Concealed targets show dashed/faded bounding box
- Destroyed targets show "X" overlay

**Environmental effects**:
- Cloud cover: adds fog/static overlay proportional to `environment.cloud_cover`
- Precipitation: vertical line artifacts (rain noise)
- Night: darker background, targets glow brighter (thermal contrast increase)
- Time-of-day affects overall brightness

**Scan lines / noise**: Subtle scan line overlay for realism. Random noise artifacts that increase with range or bad weather.

### 9.6 SIGINT Waterfall Display

When a SIGINT-equipped drone is selected, replace the visual camera with a spectrum/waterfall display:

```
┌─SIGINT DISPLAY──────────────────────────────────┐
│                                                  │
│  FREQ (MHz)  100    200    300    400    500     │
│  ─────────────────────────────────────────────   │
│  ████░░░░░░░████░░░░░░░░░░░░░░░████░░░░░░░░░   │  ← current
│  ████░░░░░░░████░░░░░░░░░░░░░░░████░░░░░░░░░   │  ← -1s
│  ░░░░░░░░░░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │  ← -2s
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████░░░░░░░░░░   │  ← -3s
│  ─────────────────────────────────────────────   │
│                                                  │
│  DETECTED EMITTERS:                              │
│  ● SA-6 RADAR (155MHz) BRG: 045° RNG: 85km     │
│  ● COMM RELAY (340MHz) BRG: 120° RNG: 45km     │
│  ○ UNKNOWN   (480MHz) BRG: 270° RNG: 150km     │
│                                                  │
│  STATUS: COLLECTING  DWELL: 12.5s               │
└──────────────────────────────────────────────────┘
```

### 9.7 Backend Support

**`sim_engine.py`** — Additional state per UAV for feed simulation:
```python
class UAV:
    # ... existing ...
    self.sensor_quality: float = 1.0    # 0-1, degraded by weather/range
    self.fov_targets: list[int] = []    # target IDs currently in FOV
    self.sigint_detections: list[dict] = []  # for SIGINT waterfall
```

**`api_main.py`** — Enhanced SENSOR_FEED payload:
```json
{
    "type": "SENSOR_FEED",
    "uav_id": 5,
    "sensor_type": "EO_IR",
    "sensor_quality": 0.85,
    "fov_targets": [
        {
            "target_id": 12,
            "bearing_deg": 45.2,
            "range_m": 8500,
            "confidence": 0.72,
            "velocity_mps": 15.0,
            "velocity_heading_deg": 270,
            "is_primary": true
        }
    ],
    "environment_effects": {
        "cloud_penalty": 0.15,
        "precip_penalty": 0.0,
        "night_bonus": 0.1
    }
}
```

### 9.8 Demo Checkpoint

- [ ] EO/IR feed: green thermal with terrain noise, hot targets glow
- [ ] SAR feed: amber radar returns, sharp target echoes
- [ ] SIGINT feed: waterfall display with detected emitters
- [ ] Compass tape shows bearing to tracked target
- [ ] Multi-target: all FOV targets get bounding boxes
- [ ] Verification progress bar on HUD
- [ ] Fused confidence meter showing multi-sensor contribution
- [ ] PIP layout: main feed + picture-in-picture from supporting UAV
- [ ] SPLIT layout: two sensor types side-by-side
- [ ] QUAD layout: 4 drone feeds simultaneously
- [ ] Environmental effects: cloud fog, rain noise, night brightness
- [ ] Threat warning when drone enters SAM envelope
- [ ] Scan line overlay for realism

### 9.9 Files Changed

| File | Action | Lines (~) |
|------|--------|-----------|
| `src/frontend/dronecam.js` | MODIFY (major rewrite) | ~500 changed/new |
| `src/frontend/sigint_display.js` | **NEW** | ~200 |
| `src/frontend/cam_layouts.js` | **NEW** | ~150 |
| `src/python/sim_engine.py` | MODIFY | ~30 changed (FOV target list, sensor quality) |
| `src/python/api_main.py` | MODIFY | ~20 changed (enhanced sensor feed) |
| `src/frontend/index.html` | MODIFY | ~15 changed (layout buttons) |
| `src/frontend/style.css` | MODIFY | ~40 changed (cam layout styles) |

### 9.10 Dependencies

Requires Stage 1 (fusion data for multi-sensor overlay), Stage 5 (SENSOR_FEED subscription), Stage 3 (drone modes for mode indicator).

---

## Cross-Cutting Architecture Decisions

### ADR-001: Fusion Algorithm

**Decision**: Complementary fusion: `fused = 1 - product(1 - ci)` for independent sensors.
**Rationale**: Simple, intuitive, no tuning parameters. Correct behavior. Upgrade to Dempster-Shafer later if needed.
**Trade-off**: Assumes sensor independence (approximately true for different modalities, not for two EO_IR at same angle).

### ADR-002: State Transition Engine

**Decision**: Pure-function state machine in `verification_engine.py`, called from `sim_engine.tick()`.
**Rationale**: Testable in isolation, no side effects, clear separation from simulation physics.

### ADR-003: Swarm Coordinator Placement

**Decision**: Standalone `swarm_coordinator.py` module, called from tick() after detection evaluation.
**Rationale**: `sim_engine.py` is already 742 lines. Composition over inheritance.

### ADR-004: Feed Architecture

**Decision**: Multiple typed feeds over single WebSocket, subscription-based.
**Rationale**: Prevents bandwidth waste for clients that don't need all data. Event-driven feeds reduce unnecessary traffic.

### ADR-005: Autonomy Levels

**Decision**: Three-tier autonomy (MANUAL/SUPERVISED/AUTONOMOUS) with per-drone override.
**Rationale**: Military C2 systems require clear human-in-the-loop controls. SUPERVISED with auto-approve timeout balances responsiveness with oversight.

### ADR-006: Frontend Module Strategy

**Decision**: One new JS module per major feature. Extend existing modules only for incremental changes.
**Rationale**: Follows existing pattern of many small files. `app.js` stays thin.

---

## Execution Summary

```
Stage 1: Multi-Sensor Fusion        ~500 new lines    [FOUNDATION]
    ↓ DEMO + VERIFY
Stage 2: Verification Workflow       ~400 new lines    [TARGET STATES]
    ↓ DEMO + VERIFY
Stage 3: Drone Modes                 ~600 new lines    [HUMAN/AUTO MODES]
    ↓ DEMO + VERIFY
Stage 4: Swarm Coordination          ~700 new lines    [SWARM INTELLIGENCE]
    ↓ DEMO + VERIFY
Stage 5: Information Feeds           ~600 new lines    [CHANNELS & UI]
    ↓ DEMO + VERIFY
Stage 6: Battlespace Assessment      ~900 new lines    [COP & THREAT PICTURE]
    ↓ DEMO + VERIFY
Stage 7: Adaptive ISR                ~600 new lines    [CAPSTONE — CLOSED LOOP]
    ↓ DEMO + VERIFY
Stage 8: Map Modes & Tactical Views  ~900 new lines    [VISUALIZATION]
    ↓ DEMO + VERIFY
Stage 9: Upgraded Drone Feeds        ~900 new lines    [SENSOR DISPLAYS]
    ↓ FINAL DEMO
```

### New Files Created (per stage)

| Stage | New Python | New JS |
|-------|-----------|--------|
| 1 | `sensor_fusion.py`, `tests/test_sensor_fusion.py` | — |
| 2 | `verification_engine.py`, `tests/test_verification.py` | — |
| 3 | `tests/test_drone_modes.py` | — |
| 4 | `swarm_coordinator.py`, `tests/test_swarm_coordinator.py` | `swarm.js` |
| 5 | `intel_feed.py`, `tests/test_feeds.py` | `feeds.js` |
| 6 | `battlespace_assessment.py`, `tests/test_battlespace.py` | `assessment.js` |
| 7 | `isr_priority.py`, `tests/test_adaptive_isr.py` | — |
| 8 | — | `mapmode.js`, `layers/coverage.js`, `layers/threat.js`, `layers/fusion.js`, `layers/terrain.js` |
| 9 | — | `sigint_display.js`, `cam_layouts.js` |

**Total**: ~6,100 new lines, 7 new Python modules, 10 new JS modules, 7 test files

### Modified Files (cumulative)

| File | Stages | Total Changes (~) |
|------|--------|-------------------|
| `sim_engine.py` | 1,2,3,4,6,7,9 | ~590 lines changed |
| `api_main.py` | 1,2,3,4,5,7,9 | ~400 lines changed |
| `dronecam.js` | 1,3,5,9 | ~600 lines changed (major rewrite in Stage 9) |
| `enemies.js` | 1,2,4 | ~160 lines changed |
| `dronelist.js` | 1,3,7 | ~160 lines changed |
| `map.js` | 5,6,8 | ~200 lines changed |
| `drones.js` | 1,3,4 | ~70 lines changed |
| `app.js` | 4,5,6,8 | ~60 lines changed |
| `index.html` | 5,6,8,9 | ~105 lines changed |
| `style.css` | 8,9 | ~120 lines changed |
| `state.js` | 2,3 | ~20 lines changed |
| `sidebar.js` | 5,6 | ~40 lines changed |

### Implementation Team per Stage

Each stage uses this agent pipeline:

```
Wave 1 (parallel): Explore codebase + research (haiku)
Wave 2: planner (sonnet) → plan decomposition
Wave 3: tdd-guide (sonnet) → write tests first
Wave 4: implement code changes
Wave 5 (parallel): python-reviewer (sonnet) + security-reviewer (sonnet)
Wave 6: fix review findings + commit
Wave 7 (background): doc-updater (haiku)
```
