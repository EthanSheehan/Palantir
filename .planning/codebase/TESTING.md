# Testing Patterns

**Analysis Date:** 2026-03-19

## Test Framework

**Runner:**
- **Python:** pytest (`conftest.py` configures sys.path)
- **TypeScript/E2E:** Playwright (`@playwright/test` ^1.58.2)

**Assertion Library:**
- Python: pytest assertions and Pydantic validation
- TypeScript: Playwright assertions (`expect()`)

**Run Commands:**
```bash
# Python unit tests
./venv/bin/python3 -m pytest src/python/tests/

# Run single test file
./venv/bin/python3 -m pytest src/python/tests/test_pattern_analyzer.py

# E2E tests
npm test                              # Run all E2E tests
npm run test:e2e:ui                   # Open Playwright UI
npm run test:e2e:headed               # Run with visible browser
npm run test:e2e:debug                # Debug mode
npm run test:e2e:critical             # Run critical path tests only
npm run test:e2e:live                 # Run @live tagged tests (requires backend)
```

## Test File Organization

**Location:**
- Python: `src/python/tests/test_*.py` (co-located with source in same package)
- E2E: `tests/e2e/*.spec.ts` (separate directory, Playwright format)

**Naming:**
- Python: `test_<module>.py` (e.g., `test_pattern_analyzer.py`, `test_hitl_manager.py`)
- TypeScript E2E: `NN-<feature>.spec.ts` (e.g., `01-websocket-connection.spec.ts`, `02-tab-navigation.spec.ts`)

**Structure:**
```
src/python/tests/
├── conftest.py              # pytest configuration (path setup)
├── test_pattern_analyzer.py
├── test_hitl_manager.py
├── test_sensor_model.py
├── test_event_logger.py
└── test_sim_integration.py

tests/e2e/
├── 01-websocket-connection.spec.ts
├── 02-tab-navigation.spec.ts
├── 03-drone-list.spec.ts
├── 04-enemy-list.spec.ts
├── 05-mission-status.spec.ts
└── 06-tactical-assistant.spec.ts
```

## Test Structure

**Suite Organization (Python):**
```python
import pytest
from unittest.mock import MagicMock

class TestPatternAnomalySchema:
    """Verify PatternAnomaly accepts valid data and rejects invalid data."""

    def _make_anomaly(self, **overrides) -> dict:
        """Helper: build test data with defaults."""
        defaults = {
            "anomaly_id": "ANOM-001",
            "anomaly_type": AnomalyType.ROUTE_FREQUENCY_CHANGE,
            # ... more fields
        }
        defaults.update(overrides)
        return defaults

    def test_valid_anomaly(self):
        anomaly = PatternAnomaly(**self._make_anomaly())
        assert anomaly.anomaly_id == "ANOM-001"
```

**Patterns:**
- Test classes group related tests: `TestPatternAnomalySchema`, `TestHistoricalActivity`, `TestPatternAnalyzerAgent`
- Helper methods prefixed with `_make_` or `_get_`: `_make_anomaly()`, return test data with sensible defaults
- Assertions per test are minimal: one behavior per test (e.g., `test_valid_anomaly` tests happy path, `test_invalid_anomaly_type_rejected` tests validation)

**Fixtures:**
```python
@pytest.fixture
def manager():
    return HITLManager()

@pytest.fixture
def sample_target_data():
    return {
        "target_id": 42,
        "target_type": "SAM",
        "target_location": (44.5, 26.1),
        "detection_confidence": 0.92,
    }

@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Redirect LOG_DIR to a temp directory."""
    monkeypatch.setattr(event_logger, "LOG_DIR", tmp_path)
    return tmp_path
```

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_start_and_log_event(log_dir):
    """Events enqueued via log_event are written to a JSONL file."""
    await event_logger.start_logger()
    event_logger.log_event("test_event", {"key": "value"})
    await event_logger.stop_logger()

    files = list(log_dir.glob("events-*.jsonl"))
    assert len(files) == 1
```

## Mocking

**Framework:** unittest.mock (`MagicMock`, `patch`)

**Patterns:**
```python
from unittest.mock import MagicMock, patch

# Test fixture with mock LLM client
class TestPatternAnalyzerAgent:
    def test_agent_initialises(self):
        mock_llm = MagicMock()
        agent = PatternAnalyzerAgent(mock_llm)
        assert agent.llm_client is mock_llm

# Mock module-level attribute
@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(event_logger, "LOG_DIR", tmp_path)
    return tmp_path
```

**What to Mock:**
- External LLM clients (OpenAI, Anthropic, Ollama) — use `MagicMock()`
- File I/O operations — use `tmp_path` fixture and `monkeypatch`
- WebSocket connections — mock at protocol level

**What NOT to Mock:**
- Pydantic models — instantiate real models to validate schema
- Business logic in domain models (e.g., `Target.update()`) — test with real instances
- Configuration and ontology — use real configs from `config.py`, ontology enums

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def sample_coas():
    return [
        CourseOfAction(
            id="COA-1",
            effector_name="F-35A Lightning II",
            effector_type="Kinetic",
            time_to_effect_min=12.5,
            pk_estimate=0.95,
            risk_score=8.5,
            composite_score=0.45,
            reasoning_trace="Fastest strike option",
            status="PROPOSED",
        ),
        # ... more COAs
    ]
```

**Location:**
- `src/python/tests/conftest.py` — shared pytest config
- Per-test-file fixtures: defined in `test_*.py` with `@pytest.fixture` decorator
- No factory pattern observed; use fixture with `**overrides` pattern instead:
  ```python
  def _make_anomaly(self, **overrides) -> dict:
      defaults = {...}
      defaults.update(overrides)
      return defaults
  ```

## Coverage

**Requirements:** Not explicitly enforced in config; 80%+ target implied by project standards

**View Coverage:**
```bash
# Generate coverage report
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python --cov-report=html

# View HTML report
open htmlcov/index.html
```

**Gaps Observed:**
- Integration between agents (ISRObserver → StrategyAnalyst → TacticalPlanner pipeline) lacks end-to-end tests
- WebSocket message handling has limited test coverage (validation tested, but message routing logic not)
- Cesium visualization hooks have no unit tests (E2E only)

## Test Types

**Unit Tests:**
- Scope: Individual functions, classes, and Pydantic schemas
- Examples: `test_valid_anomaly()`, `test_compute_aspect_rcs()`, `test_deg_to_meters()`
- Approach: Instantiate class/call function with known inputs, assert output

**Integration Tests:**
- Scope: Data flow through multiple modules (sensor model → detection → agent pipeline)
- Examples: `test_sensor_fusion.py`, `test_agent_wiring.py`
- Approach: Load real configs, run partial pipelines, validate intermediate state

**E2E Tests (Playwright):**
- Scope: Critical user flows (WebSocket connection, tab navigation, drone selection, strike board)
- Examples: `01-websocket-connection.spec.ts`, `06-tactical-assistant.spec.ts`
- Approach: Start backend, connect frontend, simulate user interactions, verify Cesium state
- Config: `playwright.config.ts` (root level)

## Common Patterns

**Validation Testing (Pydantic Schemas):**
```python
class TestPatternAnomalySchema:
    def test_valid_anomaly(self):
        anomaly = PatternAnomaly(**self._make_anomaly())
        assert anomaly.anomaly_id == "ANOM-001"

    def test_invalid_anomaly_type_rejected(self):
        with pytest.raises(Exception):
            PatternAnomaly(**self._make_anomaly(anomaly_type="InvalidType"))
```

**Enum Coverage:**
```python
def test_all_anomaly_types(self):
    for atype in AnomalyType:
        anomaly = PatternAnomaly(**self._make_anomaly(anomaly_type=atype))
        assert anomaly.anomaly_type == atype
```

**Error Testing (Exception Handling):**
```python
def test_invalid_severity_rejected(self):
    with pytest.raises(Exception):
        PatternAnomaly(**self._make_anomaly(severity="EXTREME"))
```

**Async Error Testing:**
```python
@pytest.mark.asyncio
async def test_log_event_before_start():
    """log_event before start_logger silently drops the event."""
    # Should not raise
    event_logger.log_event("dropped", {"x": 1})
```

## Test-Driven Development (TDD)

**Applied in:**
- `src/python/tests/test_sensor_model.py` — Written FIRST (before implementation)
  - Tests define expected behavior (deg_to_meters, compute_aspect_rcs)
  - Implementation follows to pass tests
  - Comments in file: "Tests for sensor_model.py — written FIRST (TDD RED phase)"

**Pattern:**
1. **RED**: Write test that fails
2. **GREEN**: Write minimal implementation to pass
3. **IMPROVE**: Refactor (rarely done in this codebase, focus is on getting features working)

## State Management Testing (Frontend)

**Zustand Store:**
- No explicit unit tests for store mutations
- Store behavior verified via E2E tests: `useSimStore` mutations tested through UI interactions
- Example: `setConnected()`, `addAssistantMessage()` tested indirectly via Playwright

**Async Hook Testing (useWebSocket):**
- No Jest/Vitest unit tests observed
- WebSocket reconnection logic tested via E2E: Playwright kills connection, observes reconnect behavior

## Known Testing Limitations

1. **No agent pipeline E2E tests**: Full F2T2EA chain (ISR → Strategy → Planner → Effectors) untested as integrated unit
2. **No Cesium hook unit tests**: All visualization hooks tested only via Playwright E2E
3. **No store mutation unit tests**: Zustand store behavior verified only through full system E2E
4. **No mock WebSocket tests for message routing**: WebSocket payload validation tested, but multi-message scenarios and ordering untested
5. **Limited performance tests**: No load testing for WebSocket broadcast with many clients

---

*Testing analysis: 2026-03-19*
