# Testing Patterns

**Analysis Date:** 2026-03-20

## Test Framework

**Python:**
- Framework: `pytest` (from `requirements.txt: pytest-asyncio>=0.23.0`)
- Async support: `pytest-asyncio` for async test functions
- Config: `src/python/tests/conftest.py` adds `src/python` to `sys.path` for bare imports

**TypeScript/E2E:**
- Framework: `Playwright` (from `@playwright/test: ^1.58.2`)
- Config: `playwright.config.ts` at root
- Reporter: HTML (default), JUnit XML for CI, list output

**Run Commands:**

```bash
# Python tests
./venv/bin/python3 -m pytest src/python/tests/                    # Run all Python tests
./venv/bin/python3 -m pytest src/python/tests/test_pattern_analyzer.py  # Single file
./venv/bin/python3 -m pytest -v                                   # Verbose mode
./venv/bin/python3 -m pytest --tb=short                           # Short traceback

# E2E tests
npm run test:e2e                     # Run all E2E tests
npm run test:e2e:ui                  # Interactive UI mode
npm run test:e2e:headed              # Visible browser
npm run test:e2e:debug               # Debug mode with inspector
npm run test:e2e:live                # Tests marked @live (requires real backend)
npm run test:e2e:critical            # Run critical test suite
```

## Test File Organization

**Location — Python:**
- Co-located in `src/python/tests/` directory
- One test file per module: `test_sim_integration.py` tests `sim_engine.py`, `test_sensor_fusion.py` tests `sensor_fusion.py`
- Total: 6514 lines across 20+ test files

**Naming Convention:**
- Prefix: `test_` (e.g., `test_pattern_analyzer.py`)
- Test functions: `test_[subject]_[condition]()` (e.g., `test_valid_anomaly()`, `test_empty_contributions()`)
- Test classes: `Test[Subject]` (e.g., `TestPatternAnomalySchema`, `TestFuseDetections`)

**Location — TypeScript/E2E:**
- `tests/e2e/` directory at root
- File pattern: `NN-[feature].spec.ts` (e.g., `01-websocket-connection.spec.ts`, `02-tab-navigation.spec.ts`)
- Helpers: `tests/e2e/helpers/`, Fixtures: `tests/e2e/fixtures/`, Pages: `tests/e2e/pages/`

**Directory Structure:**
```
tests/e2e/
├── 01-websocket-connection.spec.ts
├── 02-tab-navigation.spec.ts
├── 03-drone-list.spec.ts
├── fixtures/
│   └── base.ts                  # Base test fixture with wsMock
├── helpers/
│   └── ws-mock.ts              # WebSocket mock helper
├── pages/
│   └── PalantirPage.ts          # Page Object Model
└── ...

src/python/tests/
├── conftest.py
├── test_pattern_analyzer.py
├── test_sensor_fusion.py
├── test_sim_integration.py
└── ... (20+ files)
```

## Test Structure

**Python — Unit Test Suite Pattern:**

From `src/python/tests/test_pattern_analyzer.py`:
```python
"""
Tests for the Pattern Analyzer agent, schemas, and historical data store.
"""

import pytest
from unittest.mock import MagicMock

# Group 1: Schema validation tests
class TestPatternAnomalySchema:
    """Verify PatternAnomaly accepts valid data and rejects invalid data."""

    def _make_anomaly(self, **overrides) -> dict:
        """Helper factory method — builds test anomaly with defaults."""
        defaults = { ... }
        defaults.update(overrides)
        return defaults

    def test_valid_anomaly(self):
        anomaly = PatternAnomaly(**self._make_anomaly())
        assert anomaly.anomaly_id == "ANOM-001"

    def test_invalid_anomaly_type_rejected(self):
        with pytest.raises(Exception):
            PatternAnomaly(**self._make_anomaly(anomaly_type="InvalidType"))

# Group 2: Integration tests
class TestHistoricalActivity:
    """Verify the simulated historical activity data store."""

    def test_bravo_entries_exist(self):
        bravo = get_sector_activity("Bravo")
        assert len(bravo) > 0
        assert all(a.sector == "Bravo" for a in bravo)
```

**Patterns:**

1. **Test classes organize related tests:**
   - One `Test[Subject]` class per logical grouping
   - Private helper methods prefixed with `_`: `_make_anomaly()`, `_detect_first_target()`
   - Shared fixtures via `pytest.fixture` or conftest-level fixtures

2. **Descriptive test names:**
   ```python
   test_valid_anomaly()  # ← Success case
   test_invalid_anomaly_type_rejected()  # ← Rejection case
   test_empty_contributions()  # ← Edge case
   test_confidence_bounded()  # ← Constraint validation
   ```

3. **Single assert per test** (when possible):
   ```python
   def test_fused_confidence_uses_product_complement(self):
       # 1 - (1-0.6)*(1-0.5) = 1 - 0.4*0.5 = 0.8
       assert result.fused_confidence == pytest.approx(0.8)
   ```

4. **Approximate assertions for floats:**
   ```python
   assert result.fused_confidence == pytest.approx(0.8)  # ← Not exact equality
   assert 0.0 <= result.fused_confidence <= 1.0           # ← Bounds check
   ```

**TypeScript/E2E — Playwright Test Pattern:**

From `tests/e2e/01-websocket-connection.spec.ts`:
```typescript
import { test, expect } from './fixtures/base';

test.describe('WebSocket Connection', () => {
  test('sends IDENTIFY handshake immediately after connecting', async ({
    palantirPage,
    wsMock,
  }) => {
    const identPayload = await wsMock.waitForIdentify();

    expect(identPayload.type).toBe('IDENTIFY');
    expect(identPayload.client_type).toBe('DASHBOARD');
  });

  test('shows "Uplink Active" status once WebSocket opens', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();
    await palantirPage.assertConnected();
  });
});
```

**Patterns:**

1. **Descriptive test names in plain English:**
   - `'sends IDENTIFY handshake immediately after connecting'`
   - `'shows "Signal Lost" when WebSocket closes'`
   - `'updates UAV and zone counters from state payload'`

2. **Block comments explain test intent:**
   ```typescript
   /**
    * CRITICAL: WebSocket Connection & Handshake
    *
    * Validates that the frontend correctly:
    *   1. Opens a WebSocket connection to ws://localhost:8000/ws
    *   2. Sends an IDENTIFY handshake with client_type "DASHBOARD"
    */
   ```

3. **Fixtures injection for test setup:**
   ```typescript
   test('...', async ({ palantirPage, wsMock }) => {
     // palantirPage auto-navigates to / and sets up WS mock
     // wsMock allows assertions on WebSocket messages
   })
   ```

## Mocking

**Python Mocking:**

Framework: `unittest.mock` (standard library)

```python
# From test_pattern_analyzer.py
from unittest.mock import MagicMock

def test_agent_initialises(self):
    mock_client = MagicMock()
    agent = PatternAnalyzerAgent(mock_client)
    assert agent.llm_client is mock_client
```

**What to Mock:**
- External LLM clients (OpenAI, Anthropic, Ollama)
- Database connections
- File I/O operations

**What NOT to Mock:**
- Pydantic models (test validation logic)
- Pure functions (test actual computation)
- Dataclass immutability

**TypeScript Mocking:**

Framework: Custom WebSocket mock (`tests/e2e/helpers/ws-mock.ts`)

```typescript
// From base.ts fixture
const mock = await createWsMock(page);
await use(mock);

// In tests
await wsMock.waitForIdentify();  // Wait for handshake
await wsMock.sendState(state);   // Inject simulated state
await wsMock.closeConnection();  // Simulate disconnect
```

**Mock Strategy:**
- **Intercept at route level** — Route handler installed BEFORE page load
- **No real backend required** — Tests run with `wsMock` by default
- **Live tests annotated** — `@live` tag for tests needing real services
- **Isolation** — Each test gets a fresh mock instance

## Fixtures and Factories

**Python Fixtures:**

From `conftest.py`:
```python
"""Pytest configuration — add src/python to sys.path so bare imports work."""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
```

From test modules:
```python
@pytest.fixture
def sim():
    random.seed(42)
    return SimulationModel()

def _tick_n(sim: SimulationModel, n: int):
    """Helper function — advance simulation N ticks."""
    for _ in range(n):
        sim.tick()

class TestProbabilisticDetection:
    def test_some_targets_detected_after_100_ticks(self, sim):
        _tick_n(sim, 100)
        # assertions...
```

**Factory Pattern Example:**

From `test_pattern_analyzer.py`:
```python
def _make_anomaly(self, **overrides) -> dict:
    """Factory with defaults — allows flexible test data."""
    defaults = {
        "anomaly_id": "ANOM-001",
        "anomaly_type": AnomalyType.ROUTE_FREQUENCY_CHANGE,
        "sector": "Bravo",
        "description": "Supply convoy frequency increased 200%.",
        "severity": AlertSeverity.HIGH,
        "baseline_value": 3.0,
        "observed_value": 9.0,
        "deviation_pct": 200.0,
        "first_observed": "2026-01-08T04:00:00Z",
        "reasoning": "Baseline is 3 convoys/week; observed 9 in last 7 days.",
    }
    defaults.update(overrides)  # Override specific fields per test
    return defaults

def test_valid_anomaly(self):
    anomaly = PatternAnomaly(**self._make_anomaly())

def test_all_severity_levels(self):
    for sev in AlertSeverity:
        anomaly = PatternAnomaly(**self._make_anomaly(severity=sev))
        assert anomaly.severity == sev
```

**TypeScript Test Helpers:**

From `tests/e2e/helpers/ws-mock.ts`:
```typescript
export function mockUav(id: number) { ... }
export function mockZone(x: number, y: number) { ... }
export function buildState(props: Partial<SimState>) { ... }

// Usage in tests
const state = buildState({
  uavs: [mockUav(1), mockUav(2), mockUav(3)],
  zones: [mockZone(0, 0), mockZone(1, 0), mockZone(2, 0)],
});
await wsMock.sendState(state);
```

## Coverage

**Requirements:**
- Minimum target: 80% code coverage (enforced by project standards)
- Measure via `pytest --cov` (pytest-cov plugin, not detected in requirements but likely available)

**View Coverage:**
```bash
# Python coverage
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python --cov-report=html

# Generate HTML report in htmlcov/index.html
```

**Coverage Strategy:**
- Unit tests: 100% coverage of pure functions and Pydantic models
- Integration tests: Cover sensor fusion, state transitions, agent wiring
- E2E tests: Focus on critical user flows (WebSocket, tab navigation, drone selection)

**Uncovered areas allowed:**
- Error handling stubs that raise `NotImplementedError`
- Legacy code paths
- Platform-specific branches

## Test Types

**Unit Tests — Python:**

Scope: Single functions or classes in isolation
Location: `src/python/tests/test_*.py`

Examples:
- `TestPatternAnomalySchema` — validates Pydantic schema
- `TestFuseDetections` — tests `fuse_detections()` with various input combinations
- `TestSetEnvironment` — tests environment configuration

```python
class TestFuseDetections:
    def test_empty_contributions(self):
        result = fuse_detections([])
        assert result.fused_confidence == 0.0
        assert result.sensor_count == 0

    def test_two_types_fuse_higher(self):
        contribs = [
            SensorContribution(uav_id=1, sensor_type="EO_IR", confidence=0.6,
                               range_m=5000, bearing_deg=0.0, timestamp=1.0),
            SensorContribution(uav_id=2, sensor_type="SAR", confidence=0.5,
                               range_m=6000, bearing_deg=10.0, timestamp=1.0),
        ]
        result = fuse_detections(contribs)
        assert result.fused_confidence == pytest.approx(0.8)
```

**Integration Tests — Python:**

Scope: Multiple components working together
Location: `src/python/tests/test_*integration*.py`, `test_sim_engine.py`, etc.

Examples:
- `TestProbabilisticDetection` — simulation engine + sensor model
- `TestCommandsAfterSensorIntegration` — UAV commands + target state transitions
- `TestSimIntegration` — full simulation loop

```python
class TestProbabilisticDetection:
    def test_some_targets_detected_after_100_ticks(self, sim):
        """Integration: simulator + sensor model produces detections."""
        ever_detected = False
        for _ in range(500):
            sim.tick()
            if any(t.state != "UNDETECTED" for t in sim.targets):
                ever_detected = True
                break
        assert ever_detected
```

**Integration Tests — TypeScript:**

Scope: Frontend components + WebSocket communication
Location: `tests/e2e/[NN]-*.spec.ts`

Examples:
- `test('sends IDENTIFY handshake immediately after connecting')` — validates WebSocket init
- `test('clicking ASSETS tab shows assets content')` — UI state transitions
- `test('updates UAV and zone counters from state payload')` — state sync

```typescript
test('updates UAV and zone counters from state payload', async ({
  palantirPage,
  wsMock,
}) => {
  await wsMock.waitForIdentify();

  const state = buildState({
    uavs: [mockUav(1), mockUav(2), mockUav(3)],
    zones: [mockZone(0, 0), mockZone(1, 0), mockZone(2, 0)],
  });

  await wsMock.sendState(state);

  await expect(palantirPage.uavCount).toHaveText('3', { timeout: 5000 });
  await expect(palantirPage.zoneCount).toHaveText('5', { timeout: 5000 });
});
```

**E2E Tests — Critical Flows:**

Scope: Full user workflows from page load to action execution
Marked: `npm run test:e2e:critical` runs prioritized critical suite

Critical test files:
- `01-websocket-connection.spec.ts` — Backend communication
- `02-tab-navigation.spec.ts` — Navigation state
- `03-drone-list.spec.ts` — Asset listing
- `04-enemy-list.spec.ts` — Enemy listing
- `05-mission-status.spec.ts` — Mission state
- `06-tactical-assistant.spec.ts` — Agent recommendations

## Common Patterns

**Async Testing — Python:**

Use `pytest-asyncio` for async functions:
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

(Not widely used in this codebase — simulation is tick-based, not async)

**Async Testing — TypeScript/E2E:**

All E2E tests are async:
```typescript
test('sends IDENTIFY handshake', async ({ palantirPage, wsMock }) => {
  const identPayload = await wsMock.waitForIdentify();  // await on async operations
  expect(identPayload.type).toBe('IDENTIFY');
});
```

**Error Testing — Python:**

Use `pytest.raises()` context manager:
```python
def test_invalid_anomaly_type_rejected(self):
    with pytest.raises(Exception):
        PatternAnomaly(**self._make_anomaly(anomaly_type="InvalidType"))

def test_invalid_severity_rejected(self):
    with pytest.raises(Exception):
        PatternAnomaly(**self._make_anomaly(severity="EXTREME"))
```

**State Assertion — TypeScript/E2E:**

Use Playwright locators and assertions:
```typescript
await expect(palantirPage.connStatus).toHaveText('Signal Lost', {
  timeout: 5000,
});
await expect(palantirPage.connStatus).toHaveClass(/disconnected/);
```

**Graceful Failure Testing:**

```typescript
test('ignores malformed/unknown message types gracefully', async ({
  palantirPage,
  wsMock,
  page,
}) => {
  await wsMock.waitForIdentify();

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  // Inject unknown message type
  await page.evaluate(() => {
    const event = new MessageEvent('message', {
      data: JSON.stringify({ type: 'UNKNOWN_TYPE', foo: 'bar' }),
    });
    if (window.__ws) window.__ws.dispatchEvent(event);
  });

  // Status should still be connected (no crash)
  await palantirPage.assertConnected();

  // No uncaught errors
  expect(
    errors.filter((e) => !e.includes('Cesium') && !e.includes('Ion'))
  ).toHaveLength(0);
});
```

## Playwright Configuration Details

From `playwright.config.ts`:

```typescript
{
  testDir: './tests/e2e',
  fullyParallel: false,        // Serial execution — Cesium is GPU-heavy
  forbidOnly: !!process.env.CI, // .only() forbidden in CI
  retries: process.env.CI ? 2 : 1,
  workers: 1,                   // Single worker for stability
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    navigationTimeout: 30000,    // Extended for Cesium CDN
    actionTimeout: 10000,
  },
  timeout: 60000,               // 60s per test
  expect: { timeout: 10000 },   // 10s for assertions
}
```

---

*Testing analysis: 2026-03-20*
