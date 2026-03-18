# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Palantir is a decision-centric AI-assisted Command & Control (C2) system that automates the F2T2EA kill chain (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, a physics-based tactical simulator, and a Cesium 3D geospatial frontend.

## Running the System

```bash
# Launch everything (backend + frontend + drone simulator)
./palantir.sh

# Or run components individually:
./venv/bin/python3 src/python/api_main.py          # FastAPI backend on :8000
cd src/frontend && python3 -m http.server 3000      # Web UI on :3000
./venv/bin/python3 src/python/vision/video_simulator.py  # Drone simulator
```

## Tests

```bash
# Run all tests
./venv/bin/python3 -m pytest src/python/tests/

# Run a single test file
./venv/bin/python3 -m pytest src/python/tests/test_pattern_analyzer.py
```

## Dependencies

```bash
# Install Python dependencies into the existing venv
./venv/bin/pip install -r requirements.txt
```

Environment variables go in a `.env` file (loaded via python-dotenv). Required for LangChain/OpenAI agent features (e.g. `OPENAI_API_KEY`).

## Architecture

### Three Main Subsystems

**1. FastAPI Backend (`src/python/api_main.py`)**
- WebSocket server running a 10Hz simulation loop
- Dual-client model: `DASHBOARD` clients (frontend) and `SIMULATOR` clients (drone sim)
- `TacticalAssistant` embedded in the loop generates AI recommendations on new target detections
- Broadcasts full simulation state as JSON each tick

**2. Simulation Engine (`src/python/sim_engine.py`)**
- `SimulationModel` manages UAV positions/modes (idle/serving/repositioning) and target movement (SAM, TEL, TRUCK, CP unit types)
- Romania macro grid with zone-based imbalance tracking drives UAV repositioning logic
- Mission scenarios: circular scanning, target tracking, target painting (lock)

**3. Cesium Frontend (`src/frontend/`)**
- Vanilla JS (~1500 lines in `app.js`) with Cesium JS for 3D WGS-84 visualization
- No build step — served directly by Python's `http.server`
- Tabs: MISSION / ASSETS / ENEMIES; includes Tactical AIP Assistant widget
- Connects to backend WebSocket at `ws://localhost:8000/ws`

### AI Agent Layer (`src/python/agents/`)

Four LangGraph/LangChain agents that form the kill chain pipeline:
- `isr_observer.py` — sensor fusion (UAV, satellite, SIGINT)
- `strategy_analyst.py` — ROE evaluation and priority scoring
- `tactical_planner.py` — Course of Action (COA) generation
- `effectors_agent.py` — execution and Battle Damage Assessment

Agents communicate through Pydantic models defined in `src/python/core/ontology.py`. This is the shared data contract — all detection, identity, and tasking types live here.

### State Management

- LangGraph state with annotated reducers lives in `src/python/core/state.py`
- The `add` reducer pattern is used for accumulating strike board entries, tasking requests, and rejected actions
- `src/python/schemas/ontology.json` provides JSON serialization of the ontology

### WebSocket Protocol

The backend sends JSON payloads each tick containing drone positions, target positions, grid zone states, and tactical assistant messages. The frontend subscribes and updates Cesium entities in real time. Simulator clients send back video frames (base64 MJPEG) and telemetry.

## Integrated Agent Workflow (MANDATORY)

This project uses four complementary systems that work together:

| System | Role | Invocation |
|--------|------|------------|
| **everything-claude-code** | Code quality agents (review, TDD, security, build) | `subagent_type: "everything-claude-code:<agent>"` |
| **GSD (Get Shit Done)** | Spec-driven planning, phased execution, context rot prevention | `/gsd:*` slash commands |
| **DevFleet** | Parallel execution in isolated git worktrees with mission DAG | `/everything-claude-code:devfleet` |
| **Ralph** | Autonomous loop execution for unattended task completion | `ralph` CLI from terminal |

### CORE RULE: Always Spawn Agent Teams

Never work alone. For every non-trivial task, spin up a team of subagents in parallel. Use the right model for each agent (haiku for lightweight, sonnet for coding, opus for architecture). See `~/.claude/rules/agents.md` for full team composition rules.

### When to Use Which System

- **Interactive single tasks** (bug fix, small feature, 1-3 files): ECC agents directly
- **Parallelizable feature** (independent parts, 4-10 files): DevFleet worktrees + ECC review
- **Multi-phase feature** (new subsystem, 10+ files): GSD phases → DevFleet execution → ECC review
- **Unattended batch work** (task list, PRD, 20+ tasks): Ralph loop (can spawn DevFleet per iteration)
- **Ad-hoc tasks with GSD guarantees**: `/gsd:quick` for atomic commits and state tracking

### everything-claude-code Agents (Proactive)

These MUST be used proactively — do not wait for the user to ask.

| Trigger | Agent (`subagent_type`) | When |
|---------|------------------------|------|
| Feature request or complex task | `everything-claude-code:planner` | Before writing any code |
| Architectural decision | `everything-claude-code:architect` | System design, scalability questions |
| New feature or bug fix | `everything-claude-code:tdd-guide` | Write tests first (RED/GREEN/IMPROVE) |
| Code written or modified | `everything-claude-code:python-reviewer` | Immediately after any Python change |
| Code written or modified | `everything-claude-code:code-reviewer` | Immediately after any non-Python change |
| Build/test failure | `everything-claude-code:build-error-resolver` | When pytest or any build fails |
| Before commit | `everything-claude-code:security-reviewer` | Check for secrets, injection, OWASP Top 10 |
| Dead code / cleanup | `everything-claude-code:refactor-cleaner` | Code maintenance tasks |
| Documentation needed | `everything-claude-code:doc-updater` | After significant changes |
| E2E testing needed | `everything-claude-code:e2e-runner` | Critical user flow validation |
| Database changes | `everything-claude-code:database-reviewer` | Schema/query changes |

### GSD Commands (User-Initiated)

Key commands for phased development:

| Command | Purpose |
|---------|---------|
| `/gsd:new-project` | Initialize project with requirements + roadmap |
| `/gsd:plan-phase N` | Research + plan phase N with fresh context |
| `/gsd:execute-phase N` | Execute all plans in parallel waves |
| `/gsd:verify-work N` | User acceptance testing |
| `/gsd:quick` | Ad-hoc task with GSD guarantees |
| `/gsd:progress` | Show current progress |
| `/gsd:debug` | Diagnose issues |
| `/gsd:map-codebase` | Analyze existing codebase |
| `/gsd:health` | System health check |

GSD stores state in `.planning/` directory (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md).

### DevFleet (Parallel Worktree Execution)

DevFleet runs parallel agents in isolated git worktrees with a mission DAG. Use `/everything-claude-code:devfleet` or let `/build` auto-select it.

Best for: parallelizable features where parts touch different files and can be implemented independently, then auto-merged.

### Ralph (Autonomous Loop)

Ralph runs Claude CLI in a loop for unattended work. Config lives in `.ralph/`.

```bash
ralph --monitor          # Start autonomous loop with dashboard
ralph-import prd.md      # Import tasks from a PRD
```

Edit `.ralph/fix_plan.md` to define the task list. Ralph handles session continuity, rate limiting, and stagnation detection automatically.

### Parallel Execution (REQUIRED)

Always launch independent agents in parallel. Example: after writing a feature, launch `python-reviewer` and `security-reviewer` simultaneously — never sequentially.

### Development Pipelines

**ECC only — single task (1-3 files):**
1. **Plan** → `everything-claude-code:planner` (sonnet)
2. **TDD** → `everything-claude-code:tdd-guide` (sonnet)
3. **Implement** → write code
4. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
5. **Fix** → address findings
6. **Commit** → conventional commits

**DevFleet — parallelizable feature (4-10 files):**
1. **Plan** → `everything-claude-code:planner` (sonnet) → break into independent units
2. **Execute** → DevFleet dispatches each unit to isolated worktree (sonnet per mission)
3. **Auto-merge** → worktrees merge on completion
4. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
5. **Fix + Commit**

**GSD + DevFleet — major feature (10+ files):**
1. `/gsd:discuss-phase N` → capture decisions
2. `/gsd:plan-phase N` → research + plan (opus for planning, fresh context)
3. **DevFleet** executes plans as parallel worktree missions (sonnet)
4. `/gsd:verify-work N` → user acceptance testing
5. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
6. **Commit** → conventional commits

**Ralph — unattended batch (20+ tasks):**
1. Edit `.ralph/fix_plan.md` with tasks
2. `ralph --monitor` → autonomous execution with safety guardrails
3. Review results when complete
