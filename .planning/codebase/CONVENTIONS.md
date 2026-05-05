# Coding Conventions

**Analysis Date:** 2026-03-20

## Naming Patterns

**Python Files:**
- Snake case: `sim_engine.py`, `sensor_fusion.py`, `verification_engine.py`
- Module names describe domain: `arena_agent.py`, `pattern_analyzer.py`

**Python Functions & Variables:**
- Snake case throughout: `evaluate_target_state()`, `fuse_detections()`, `get_sector_activity()`
- Private functions prefixed with `_`: `_generate_response()`, `_detect_first_target()`
- Constants in ALL_CAPS: `TARGET_STATES`, `VERIFICATION_THRESHOLDS`, `EMITTING_TYPES`, `MAX_TURN_RATE`
- Class attributes match function conventions: `llm_client`, `tracked_target_id`

**Python Classes:**
- PascalCase: `SimulationModel`, `PatternAnalyzerAgent`, `VerificationThreshold`, `SensorContribution`
- Dataclasses use `@dataclass(frozen=True)` for immutability: `SensorContribution`, `FusedDetection` (see `src/python/sensor_fusion.py`)
- Enums inherit from `str` and `Enum`: `class DetectionType(str, Enum)`

**TypeScript Files:**
- PascalCase for components and pages: `App.tsx`, `DroneCamPIP.tsx`, `CesiumContainer.tsx`
- Kebab case for utility/hook files: `useWebSocket.ts`, `useSensorCanvas.ts`
- Store files: `SimulationStore.ts`, `types.ts`

**TypeScript Variables, Functions, Types:**
- camelCase for functions and variables: `buildInitialSlots()`, `sendMessage()`, `onSensorModeChange()`
- PascalCase for types and interfaces: `type SensorMode = 'EO_IR' | 'SAR' | 'SIGINT' | 'FUSION'`
- Private state in Zustand: prefix with `_` or use closure scope
- React hooks use `use` prefix: `useWebSocket()`, `useSensorCanvas()`
- Event handlers: `onEvent` pattern: `onSensorModeChange()`, `onSend()`

**TypeScript Enums:**
- Mixed case to match domain: `SensorMode` (runtime union type, not enum)
- Sensor types as string literals: `'EO_IR'`, `'SAR'`, `'SIGINT'`, `'FUSION'`

## Code Style

**Formatting:**
- Python: 4-space indentation, soft tabs (verified in all `.py` files)
- TypeScript/React: 2-space indentation (verified in `.tsx` and `.ts` files)
- Line lengths: no enforced limit detected, but stay under 100-120 columns for readability
- Trailing newlines on all files

**Linting:**
- Python: No eslint/prettier detected for Python — rely on PEP 8 conventions manually
- TypeScript: No eslint/prettier config detected (`.eslintrc*`, `.prettierrc*` absent)
- Type checking: `tsconfig.json` has `"strict": true` — enforce strict types
- TypeScript strict mode: `strict: true`, `esModuleInterop: true`, `skipLibCheck: true`

**Imports Organization:**

**Python order:**
1. Standard library imports (e.g., `import sys`, `import math`)
2. Third-party imports (e.g., `from pydantic import BaseModel`, `import structlog`)
3. Local imports (e.g., `from sensor_fusion import fuse_detections`, `from core.ontology import Detection`)
4. Blank line between groups

Example from `src/python/sim_engine.py`:
```python
import math
import random
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

from romania_grid import RomaniaMacroGrid
from sensor_model import evaluate_detection, EnvironmentConditions
from theater_loader import load_theater, TheaterConfig, list_theaters

import structlog
```

**TypeScript order:**
1. React and framework imports
2. Third-party UI libraries (Blueprint, Zustand, etc.)
3. Local component imports
4. Hook imports
5. Type imports
6. Style/asset imports

Example from `src/frontend-react/src/overlays/DroneCamPIP.tsx`:
```typescript
import { useRef, useState, useEffect } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { useSensorCanvas } from '../hooks/useSensorCanvas';
import { SigintDisplay } from '../components/SigintDisplay';
import type { SensorMode } from '../store/types';
```

## Error Handling

**Python Patterns:**

1. **Exceptions are explicit** — Don't silently catch errors:
```python
# From tests/test_pattern_analyzer.py
def test_invalid_anomaly_type_rejected(self):
    with pytest.raises(Exception):
        PatternAnomaly(**self._make_anomaly(anomaly_type="InvalidType"))
```

2. **Raise NotImplementedError for stubs:**
```python
# From src/python/agents/pattern_analyzer.py
def _generate_response(self, historical_data: str) -> str:
    raise NotImplementedError("LLM integration needs to be completed.")
```

3. **Validate at system boundaries** — Use Pydantic models for validation:
```python
# From src/python/core/ontology.py
class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Degrees latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Degrees longitude")
```

4. **Test both success and failure paths:**
```python
# From tests/test_sensor_fusion.py
def test_empty_contributions(self):
    result = fuse_detections([])
    assert result.fused_confidence == 0.0
```

**TypeScript/React Patterns:**

1. **Handle reconnection gracefully:**
```typescript
// From src/frontend-react/src/hooks/useWebSocket.ts
ws.onclose = () => {
  store.getState().setConnected(false);
  if (isMounted) {
    reconnectTimeout = setTimeout(connect, 1000);
  }
};
```

2. **Null checks on optional values:**
```typescript
// From DroneCamPIP.tsx
const drone = useSimStore((s) =>
  droneId != null ? s.uavs.find((u) => u.id === droneId) ?? null : null
);
```

3. **Graceful unknown type handling:**
```typescript
// WebSocket message handler ignores unknown types
if (payload.type === 'ASSISTANT_MESSAGE') {
  // process
} else if (payload.type === 'FEED_EVENT') {
  // process
} // Unknown types simply return
```

## Logging

**Framework:**
- Python: `structlog` — structured logging with context
- TypeScript: `console` object directly (no structured logger detected)

**Python Patterns:**

```python
# From src/python/sim_engine.py
import structlog
logger = structlog.get_logger()

# Usage with context (seen in codebase)
logger.info("event", target_id=target.id, state=new_state)
```

**TypeScript Patterns:**
- Use `console.log()`, `console.warn()`, `console.error()` directly
- Avoid logging in production; rely on server-side logs
- WebSocket errors and connection state changes are logged implicitly via store state changes

## Comments

**When to Comment:**

1. **Module docstrings — ALWAYS on every Python module:**
```python
# From src/python/sensor_fusion.py
"""
sensor_fusion.py
================
Pure-function multi-sensor fusion module for Grid-Sentinel C2.

Implements complementary fusion across sensor types (1 - product(1-ci))
with max-within-type deduplication. No state, no side effects.
"""
```

2. **Class and method docstrings — on public APIs:**
```python
# From src/python/agents/pattern_analyzer.py
class PatternAnalyzerAgent:
    """Predictive intelligence agent that detects adversary pattern anomalies."""

    def __init__(self, llm_client: Any):
        """
        Initialise the Pattern Analyzer Agent.

        Args:
            llm_client: An initialised LLM client (e.g., OpenAI, Anthropic,
                        or wrapped LiteLLM client).
        """
```

3. **Inline comments for non-obvious logic:**
```python
# From src/python/sim_engine.py
# Types that emit radar signals
EMITTING_TYPES = frozenset({"SAM", "RADAR"})

# Probability per tick that an emitting type toggles is_emitting
EMIT_TOGGLE_PROB = 0.005
```

4. **No JSDoc in TypeScript** — Use inline comments instead

**Test comments:**
```python
# From tests/test_sensor_fusion.py
# 1 - (1-0.6)*(1-0.5) = 1 - 0.4*0.5 = 0.8
assert result.fused_confidence == pytest.approx(0.8)
```

## Function Design

**Size Guidelines:**
- Target 20–50 lines per function
- Max 80 lines (includes docstring and tests)
- Pure functions (no side effects) are preferred — see `src/python/verification_engine.py` for `evaluate_target_state()` pattern

**Parameters:**
- Limit to 4–5 positional parameters
- Use `**kwargs` or dataclasses for >5 parameters
- Type hints required on all Python functions

```python
# From verification_engine.py
def evaluate_target_state(
    current_state: str,
    target_type: str,
    fused_confidence: float,
    sensor_type_count: int,
    time_in_current_state_sec: float,
    seconds_since_last_sensor: float,
    demo_fast: bool = False,
) -> str:
```

**Return Values:**
- Single return types (not tuples) where possible
- Use dataclasses/Pydantic models for multiple return values:

```python
# From sensor_fusion.py
@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float
    sensor_count: int
    sensor_types: tuple[str, ...]
    contributing_uav_ids: tuple[int, ...]
    contributions: tuple[SensorContribution, ...]

def fuse_detections(contributions: Sequence[SensorContribution]) -> FusedDetection:
```

## Module Design

**Python Exports:**
- Use explicit `__all__` if the module is meant to be imported by other modules (not always present, but recommended)
- Pydantic models and dataclasses export themselves implicitly
- Private functions/classes prefixed with `_` are not exported

**Barrel Files:**
- Not used in this codebase — each module is imported directly
- Example: `from sensor_fusion import fuse_detections` not `from . import fuse_detections`

**React Component Organization:**

```typescript
// Standard component structure (from DroneCamPIP.tsx)
// 1. Imports at top
// 2. Type definitions / Interfaces
// 3. Helper functions
// 4. Main component
// 5. Subcomponents
```

## Immutability

**Python:**
- Use `@dataclass(frozen=True)` to enforce immutability:
```python
@dataclass(frozen=True)
class SensorContribution:
    uav_id: int
    sensor_type: str
    confidence: float
    range_m: float
    bearing_deg: float
    timestamp: float
```

- Pure functions that return new instances, never mutate parameters:
```python
# Good: returns new FusedDetection
def fuse_detections(contributions: Sequence[SensorContribution]) -> FusedDetection:

# Bad: mutates contributions in place
def fuse_detections(contributions: List[SensorContribution]) -> None:  # ← Never do this
```

**TypeScript/React:**
- Zustand store uses immutable updates via spread operator:
```typescript
// From SimulationStore.ts
setSimData: (data: { ... }) => {
  set((state) => ({
    ...state,
    uavs: data.uavs,
    targets: data.targets,
    // Create new object, don't mutate existing
  }));
}
```

---

*Convention analysis: 2026-03-20*
