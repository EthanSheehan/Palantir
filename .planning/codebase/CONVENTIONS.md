# Coding Conventions

**Analysis Date:** 2026-03-19

## Naming Patterns

**Files:**
- Python: snake_case (`sim_engine.py`, `isr_observer.py`, `test_pattern_analyzer.py`)
- TypeScript/React: PascalCase for components/classes (`CesiumContainer.tsx`, `SimulationStore.ts`), camelCase for utilities and hooks (`useWebSocket.ts`, `useCesiumDrones.ts`)
- Tests: `test_*.py` prefix (Python), `.spec.ts` suffix (Playwright E2E)

**Functions:**
- Python: snake_case (`_pick_sensors()`, `_heading_from_velocity()`, `evaluate_detection()`)
- TypeScript: camelCase (`sendMessage()`, `setConnected()`, `useCesiumViewer()`)
- Private/internal functions: snake_case prefix with underscore (`_validate_payload()`, `_send_error()`)

**Variables:**
- Python: snake_case (`target_id`, `detection_confidence`, `relocate_timer`)
- TypeScript: camelCase (`droneId`, `selectedDroneId`, `wsRef`)
- Constants: UPPER_SNAKE_CASE (`MAX_WS_CONNECTIONS`, `FOLLOW_ORBIT_RADIUS_DEG`, `RATE_LIMIT_MAX_MESSAGES`)

**Types:**
- Python: PascalCase (Pydantic models: `Detection`, `PatternAnomaly`, `SimulationModel`)
- TypeScript: PascalCase interfaces and types (`SimState`, `UAV`, `Target`, `AssistantMessage`)
- Enums: PascalCase with all-caps values (`DetectionType`, `IdentityClassification`, `ROEAction`)

## Code Style

**Formatting:**
- No automated formatter detected (no .eslintrc, .prettierrc, or biome.json)
- Follow standard conventions per language:
  - Python: 4-space indentation (PEP 8)
  - TypeScript/React: 2-space indentation (observed in codebase)

**Linting:**
- Python: No linter config detected; rely on pydantic validation for schema enforcement
- TypeScript: No eslint config; tsconfig.json strict mode enabled (`"strict": true`)

**Imports Organization:**

*Python:*
1. Standard library (`from __future__ import`, `import asyncio`, `import json`)
2. Third-party packages (`import structlog`, `from fastapi import`, `from pydantic import`)
3. Local modules (`from sim_engine import`, `from schemas.ontology import`)
4. Blank line between groups

*TypeScript:*
1. React imports (`import React`, `import { useEffect }`)
2. Third-party packages (`import { create } from 'zustand'`, `import * as Cesium`)
3. Local imports (`import { useWebSocket }`, `import { SimulationStore }`)
4. Path aliases: None configured (tsconfig.json paths: `{}`)

## Error Handling

**Patterns:**
- **Validation at entry points**: `_validate_payload()` checks required fields and types before processing WebSocket messages
- **Structured error responses**: `_send_error()` function wraps errors in consistent JSON: `{"type": "ERROR", "message": "...", "action": "..."}`
- **Try/except scope**: Limited to risky operations (`FileNotFoundError`, `ValueError` in `trigger_demand_spike()`)
- **Logging with context**: structlog used throughout Python backend for contextual error logging:
  ```python
  logger.error("isr_strategy_pipeline_failed", error=str(exc))
  logger.warning("client_identification_failed", error=str(exc), fallback="DASHBOARD")
  ```
- **Silent failures on disconnection**: WebSocket errors caught and logged without propagation:
  ```python
  except (WebSocketDisconnect, ConnectionError, OSError):
      pass  # Client disconnected; suppress noise
  ```
- **Async exception handling**: asyncio timeouts and cancellations caught separately:
  ```python
  except (asyncio.TimeoutError, WebSocketDisconnect, ConnectionError, OSError) as exc:
      logger.warning("broadcast_send_failed", error=str(exc))
  ```

## Logging

**Framework:** structlog (Python backend)

**Configuration:**
- Loaded via `configure_logging()` in `logging_config.py`
- Logger obtained per-module: `logger = structlog.get_logger()`
- Structured fields included with every log call: `logger.info("event_name", key="value", ...)`

**Patterns:**
- **Startup/shutdown**: `logger.info("simulation_loop_started", hz=settings.simulation_hz)`
- **Errors**: `logger.error("description", error=str(exc))`
- **Warnings**: `logger.warning("client_identification_failed", error=str(exc), fallback="DASHBOARD")`
- **Contextual metadata**: Include relevant IDs, modes, reasons: `logger.info("client_identified", client_type=client_type)`

**Event Logging (Separate):**
- Async event logger writes JSONL to disk: `log_event("event_type", {"data": "..."})`
- Used for audit trail of mission-critical events
- Async queue-based: `log_event()` enqueues, background task writes

## Comments

**When to Comment:**
- Module-level docstrings: Describe purpose, not just "this file"
  ```python
  """
  agents/isr_observer.py
  ======================
  ISR Observer Agent — ingests multi-domain sensor data (UAV, Satellite, SIGINT),
  fuses detections into tracks, and maps them to the Common Ontology.
  """
  ```
- Complex algorithms: Add inline comments for non-obvious logic (e.g., `MANPADS_FLEE_DIST_DEG` threshold explanation)
- Magic numbers: Define as named constants with units (`FOLLOW_ORBIT_RADIUS_DEG = 0.018  # ~2km`)
- Skip trivial comments: `x = x + 1  # Add 1` is redundant

**JSDoc/TSDoc:**
- Python docstrings: Function-level docstrings on public functions and classes
  ```python
  def _validate_payload(payload: dict, schema: dict[str, str]) -> str | None:
      """Validate that payload contains required fields with correct types.

      schema maps field_name -> type_name ("int", "float", "str").
      Returns an error message string on failure, None on success.
      """
  ```
- TypeScript: Minimal TSDoc (no @param, @returns decorators observed)
- Pydantic Field descriptions: Include in schema models:
  ```python
  class Detection(BaseModel):
      confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence 0-1")
  ```

## Function Design

**Size:**
- Python functions typically 15-50 lines (e.g., `_validate_payload()`, `_check_rate_limit()`)
- TypeScript hooks: 30-100 lines (e.g., `useWebSocket()`, `CesiumContainer()`)
- Larger functions split across multiple methods (e.g., `SimulationModel` with separate `command_follow()`, `command_paint()`, `command_intercept()`)

**Parameters:**
- Named parameters preferred over positional for clarity
- Type hints on all Python functions: `def evaluate_detection(lat: float, lon: float) -> DetectionResult:`
- TypeScript: Implicit types from interfaces/types (no explicit `: Type` on every param)
- Avoid >3 positional args; use dataclass/dict for complex parameter groups

**Return Values:**
- Return early on validation failure: `if error: return error_message`
- Explicit None return for async operations that have side effects
- Pydantic models for structured returns (not dicts): `PatternAnalyzerOutput`, `Detection`

## Module Design

**Exports:**
- Python: Classes and public functions at module level; private helpers prefixed with `_`
- TypeScript: Named exports for all components and hooks; default export avoided
  ```typescript
  export function useWebSocket() { ... }
  export const WebSocketContext = createContext(...);
  ```

**Barrel Files:**
- `src/python/schemas/` has `__init__.py` for common imports
- `src/python/agents/` has `__init__.py` (empty, no re-exports)
- TypeScript: No barrel files observed; imports are direct

**Single Responsibility:**
- One class per file: `SimulationModel` in `sim_engine.py`, `PatternAnalyzerAgent` in `pattern_analyzer.py`
- Hooks are co-located with usage: `useCesiumDrones.ts` in cesium folder (not a generic hooks library)
- Utilities split by domain: `geo_utils.py`, `coordinate_transformer.py`

## Type Hints

**Python:**
- Full type hints on all function signatures (PEP 484)
- Union types: `Optional[int]`, `str | None` (both observed, prefer `|` for newer code)
- Complex types documented in docstrings
- Pydantic provides runtime validation; type hints are also static checkpoints

**TypeScript:**
- Strict mode enabled (`"strict": true` in tsconfig.json)
- Interface definitions for all major data structures (`SimState`, `SimulationData`, `UAV`)
- Props interfaces required for React components

## Immutability Patterns

**Python:**
- Pydantic models used for immutable data contracts
- Detection, Track, and ontology models are value objects (treated as immutable)
- Mutable state in `SimulationModel` class (targets, UAVs) explicitly managed

**TypeScript:**
- Zustand store uses immutable state: `set((state) => ({ ...state, field: newValue }))`
- React hooks follow immutability: spread operator for arrays/objects
  ```typescript
  const newMessages = [...get().assistantMessages, newMessage];
  ```
- No direct mutation of store state

---

*Convention analysis: 2026-03-19*
