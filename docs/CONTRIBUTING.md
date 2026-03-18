# Contributing to Palantir C2

**Last Updated: 2026-03-17**

This guide covers development setup, testing, code style, and the PR process for Palantir.

## Development Setup

### Prerequisites

- **Python 3.10+** (verify with `python3 --version`)
- **Git** for version control
- **Node.js 18+** for frontend tooling (optional, for E2E tests)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/EthanSheehan/Palantir.git
cd Palantir

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install Python dependencies
./venv/bin/pip install -r requirements.txt

# Install optional: Node.js dependencies for E2E tests
npm install
```

### Environment Configuration

```bash
# Copy example to create .env
cp .env.example .env

# Edit .env and add API keys (optional — system works without them)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=claude-...
# GEMINI_API_KEY=AIza...
```

## Available Commands

### AUTO-GENERATED: Script Reference

| Command | Purpose | Runs |
|---------|---------|------|
| `./palantir.sh` | Launch complete system (backend + frontend + simulator) | FastAPI (:8000) + HTTP Server (:3000) + Simulator |
| `./venv/bin/python3 src/python/api_main.py` | Run FastAPI backend only | WebSocket server on :8000 |
| `cd src/frontend && python3 -m http.server 3000` | Run dashboard frontend only | Static server on :3000 |
| `./venv/bin/python3 src/python/vision/video_simulator.py` | Run drone simulator only | Connects to :8000/ws |
| `./venv/bin/python3 -m pytest src/python/tests/` | Run all Python tests | 214+ test cases |
| `./venv/bin/python3 -m pytest src/python/tests/test_FILENAME.py` | Run single test file | Single test module |
| `npm run test:e2e` | Run Playwright E2E tests | Browser-based tests |
| `npm run test:e2e:ui` | Run E2E tests with UI | Interactive test runner |
| `npm run test:e2e:debug` | Debug E2E tests with inspector | Step through tests |
| `npm run test:e2e:critical` | Run critical path tests only | 6 core user flows |
| `./venv/bin/pip install -r requirements.txt` | Install/update Python dependencies | Updates venv |

### Common Development Tasks

**Run the full system:**
```bash
./palantir.sh
# Opens browser at http://localhost:3000
# API docs available at http://localhost:8000/docs
```

**Run backend only (for testing):**
```bash
./venv/bin/python3 src/python/api_main.py
```

**Run tests with coverage:**
```bash
./venv/bin/python3 -m pytest src/python/tests/ -v --cov=src/python --cov-report=html
```

**Run specific test:**
```bash
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py -v
```

**Run E2E tests (requires running backend):**
```bash
# In one terminal
./palantir.sh

# In another terminal
npm run test:e2e:headed
```

## Testing Requirements

### Test Coverage

- **Minimum: 80% code coverage** on all new code
- **Unit tests**: For individual functions and utilities
- **Integration tests**: For API endpoints and database operations
- **E2E tests**: For critical user flows

### Test-Driven Development (Mandatory)

Every feature or bug fix follows this workflow:

1. **RED** — Write failing test first
2. **GREEN** — Implement minimal code to pass test
3. **IMPROVE** — Refactor while tests still pass
4. **VERIFY** — Confirm 80%+ coverage

Example for a new agent method:

```python
# test_new_agent.py
import pytest
from agents.new_agent import NewAgent

def test_new_agent_processes_detection():
    """NewAgent should process detection and update state."""
    agent = NewAgent()
    detection = Detection(...)
    result = agent.process(detection)
    assert result.status == "processed"
    assert len(result.recommendations) > 0

# agents/new_agent.py
def process(self, detection):
    return AgentResult(status="processed", recommendations=[...])
```

### Running Tests

```bash
# All tests
./venv/bin/python3 -m pytest src/python/tests/

# Single test file
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py

# Single test function
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py::test_drone_repositioning

# With verbose output
./venv/bin/python3 -m pytest src/python/tests/ -v

# With coverage report
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python --cov-report=term-missing
```

### E2E Test Structure

Critical user flows are tested with Playwright:

```bash
# Run only critical tests (6 core flows)
npm run test:e2e:critical

# Run with browser visible (headed mode)
npm run test:e2e:headed

# Debug with Playwright Inspector
npm run test:e2e:debug

# View test report
npm run test:e2e:report
```

## Code Style

### Python Code Style

Follow **PEP 8** with these project conventions:

- **Line length**: 100 characters (pragmatic, not strict)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Type hints**: Used on public API methods, optional on internal code
- **Immutability**: Create new objects, never mutate existing ones (Pydantic models are good)
- **Error handling**: Explicit handling at all boundaries
- **Function size**: Keep under 50 lines; extract helpers for larger functions
- **File size**: Keep under 800 lines; split large modules

### Example: Good Code

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Detection:
    """Immutable detection record."""
    threat_id: str
    confidence: float
    location: tuple

    def update_confidence(self, new_confidence: float) -> "Detection":
        """Return new Detection with updated confidence (immutable)."""
        if new_confidence < 0 or new_confidence > 1.0:
            raise ValueError("Confidence must be between 0 and 1")
        return Detection(
            threat_id=self.threat_id,
            confidence=new_confidence,
            location=self.location,
        )

def process_detection(detection: Detection) -> str:
    """Process a detection and return status."""
    try:
        updated = detection.update_confidence(0.95)
        return f"Processed {updated.threat_id}"
    except ValueError as e:
        logger.error("Invalid detection", error=str(e))
        raise
```

### JavaScript Code Style

- **Style**: Vanilla JS (no build step required)
- **Format**: 2-space indentation, semicolons optional (ESLint used in tests)
- **Modules**: ES6 imports/exports in `src/frontend/`
- **Comments**: JSDoc for public functions

### Frontend Architecture

- **Entry point**: `src/frontend/app.js` (~1500 lines)
- **No build step**: Served by Python's `http.server`
- **Modules**: Each feature has a dedicated `.js` file
  - `state.js` — Application state management
  - `websocket.js` — WebSocket client and event dispatch
  - `map.js` — Cesium 3D viewer initialization
  - `drones.js` — UAV visualization and list UI
  - `targets.js` — Target and threat ring rendering
  - `assistant.js` — Tactical AIP message feed
  - `strikeboard.js` — HITL approval UI

## Contributing Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
# or: git checkout -b fix/bug-description
# or: git checkout -b docs/documentation-update
```

### 2. Develop with TDD

```bash
# Write test first (RED)
# Then implement (GREEN)
# Then refactor (IMPROVE)

./venv/bin/python3 -m pytest src/python/tests/ -v
```

### 3. Run Full Test Suite Before Commit

```bash
# Python tests
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python

# E2E tests (optional but recommended)
npm run test:e2e:critical
```

### 4. Commit with Conventional Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>: <description>

git commit -m "feat: Add ROE evaluation to strategy analyst"
git commit -m "fix: Correct UAV fuel consumption calculation"
git commit -m "docs: Update API endpoint documentation"
git commit -m "test: Add edge case tests for sensor model"
git commit -m "refactor: Extract detection processing to utility"

# Types: feat, fix, docs, test, refactor, perf, chore, ci
```

### 5. Push and Open Pull Request

```bash
git push -u origin feat/your-feature-name
# Then open PR on GitHub

# PR title: Brief one-liner
# PR body: What changed, why, how to test
```

## Code Review Checklist

Every PR should address:

- [ ] **Tests**: New code has 80%+ test coverage
- [ ] **No hardcoded values**: Use config/env vars
- [ ] **Error handling**: All exceptions caught and logged
- [ ] **Type safety**: Type hints on public methods
- [ ] **Immutability**: No in-place mutations
- [ ] **Documentation**: README/docstrings updated
- [ ] **Performance**: No obvious inefficiencies
- [ ] **Security**: No secrets, injection vulnerabilities, etc.

## Architecture Guidelines

### Three Main Subsystems

**1. FastAPI Backend** (`src/python/api_main.py`)
- WebSocket server running 10Hz simulation loop
- Dual-client model: DASHBOARD (frontend) + SIMULATOR (drone)
- Broadcasts full state each tick
- Agents embedded in event loop

**2. Simulation Engine** (`src/python/sim_engine.py`)
- `SimulationModel` manages UAV and target states
- Probabilistic detection with Pd/RCS models
- Zone-based coverage optimization
- 8 target unit types with type-specific behaviors

**3. Cesium Frontend** (`src/frontend/app.js`)
- Vanilla JS with Cesium for 3D visualization
- WebSocket connection to backend
- Tab-based UI: MISSION / ASSETS / ENEMIES
- Real-time entity updates at 10Hz

### AI Agent Pipeline

```
Detection → ISR Observer → Strategy Analyst
→ [HITL Gate 1] → Tactical Planner
→ [HITL Gate 2] → Effectors Agent → Assessment
```

Each agent:
- Operates in **heuristic mode** by default (no API keys needed)
- Upgrades to **LLM mode** when `.env` has API keys
- Uses **multi-provider fallback**: Gemini → Anthropic → Ollama → heuristic
- Communicates via Pydantic models in `src/python/core/ontology.py`

### Adding a New Agent

1. Create `src/python/agents/my_agent.py` with `MyAgent` class
2. Implement required methods: `invoke()` or `stream()`
3. Add tests in `src/python/tests/test_my_agent.py`
4. Wire into pipeline in `src/python/api_main.py`
5. Update this guide with agent description

### Adding a New Endpoint

1. Create function in `api_main.py` with `@app.post()` or `@app.get()` decorator
2. Use Pydantic models for request/response validation
3. Add error handling with meaningful messages
4. Write integration test in `src/python/tests/test_agent_wiring.py`
5. Document in README.md

## Environment Variables

### AUTO-GENERATED: Environment Documentation

| Variable | Type | Required | Default | Purpose |
|----------|------|----------|---------|---------|
| `OPENAI_API_KEY` | string | No | (empty) | OpenAI API key for agent LLM reasoning |
| `ANTHROPIC_API_KEY` | string | No | (empty) | Anthropic Claude API key (fallback provider) |
| `GEMINI_API_KEY` | string | No | (empty) | Google Gemini API key (primary LLM) |
| `HOST` | string | No | `0.0.0.0` | Server bind address |
| `PORT` | integer | No | `8000` | FastAPI server port |
| `LOG_LEVEL` | string | No | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `SIMULATION_HZ` | integer | No | `10` | Simulation tick rate (Hz) |
| `WS_BACKEND_URL` | string | No | `ws://localhost:8000/ws` | WebSocket backend URL (used by simulator) |
| `DEFAULT_THEATER` | string | No | `romania` | Default theater: romania, south_china_sea, baltic |

**For local development**, copy `.env.example` to `.env` and leave API keys empty. The system runs fully with heuristic agents.

**For production**, ensure all required API keys are set via environment variables (never hardcode).

## Troubleshooting

### Backend won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Try again
./venv/bin/python3 src/python/api_main.py
```

### Tests fail with import errors

```bash
# Reinstall dependencies
./venv/bin/pip install -r requirements.txt --force-reinstall

# Clear pytest cache
rm -rf .pytest_cache __pycache__

# Try again
./venv/bin/python3 -m pytest src/python/tests/ -v
```

### WebSocket connection fails

```bash
# Verify backend is running
curl http://localhost:8000/api/theaters

# Check if .env has correct WS_BACKEND_URL
cat .env | grep WS_BACKEND_URL
```

### E2E tests timeout

```bash
# Run with longer timeout
npm run test:e2e:headed -- --timeout=60000

# Or run tests one at a time
npm run test:e2e -- --workers=1
```

## Additional Resources

- **Architecture**: See [CLAUDE.md](../CLAUDE.md)
- **API Docs**: `http://localhost:8000/docs` (when running)
- **Coding Standards**: [Coding Style Rules](https://github.com/EthanSheehan/Palantir/blob/main/.claude/rules/coding-style.md)
- **Testing Guide**: [Testing Requirements](https://github.com/EthanSheehan/Palantir/blob/main/.claude/rules/testing.md)
- **Git Workflow**: [Git Workflow](https://github.com/EthanSheehan/Palantir/blob/main/.claude/rules/git-workflow.md)

## Questions?

Open an issue or discussion on GitHub with the `question` label.
