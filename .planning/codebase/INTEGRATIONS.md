# External Integrations

**Analysis Date:** 2026-03-20

## APIs & External Services

**LLM Providers (Multi-Provider Chain):**
- Google Gemini (primary)
  - SDK: `google-genai` 1.0.0+
  - Auth: `GEMINI_API_KEY` env var
  - Models: `gemini-2.0-flash` (fast/default), `gemini-2.5-pro-preview-06-05` (reasoning)
  - Integration: `src/python/llm_adapter.py` with fallback chain

- Anthropic Claude (secondary)
  - SDK: `anthropic` 0.40.0+
  - Auth: `ANTHROPIC_API_KEY` env var
  - Models: `claude-haiku-4-5-20251001` (fast), `claude-sonnet-4-6` (default/reasoning)
  - Integration: `src/python/llm_adapter.py`

- OpenAI (legacy fallback)
  - SDK: `langchain-openai` 0.0.8+
  - Auth: `OPENAI_API_KEY` env var
  - Integration: `src/python/llm_adapter.py` with LangChain

- Ollama (local LLM — free fallback)
  - SDK: `ollama` 0.4.0+
  - Connection: HTTP to `http://localhost:11434` (default)
  - Models: `llama3.2:8b` (fast/default), `llama3.3:70b` (reasoning)
  - Probe: `src/python/llm_adapter.py._probe_ollama()` checks availability at startup
  - Fallback: Heuristic responses if all LLM providers unavailable

**LLM Provider Chain (Detection Logic):**
- `src/python/llm_adapter.py` implements priority-ordered fallback:
  1. Google Gemini (if `GEMINI_API_KEY` set and SDK available)
  2. Anthropic Claude (if `ANTHROPIC_API_KEY` set and SDK available)
  3. OpenAI (if `OPENAI_API_KEY` set and SDK available)
  4. Ollama (if running locally and models available)
  5. Heuristic responses (no-crash fallback, always available)

**LangChain/LangGraph Agents:**
- Framework: LangGraph 0.0.21+ for multi-agent orchestration
- Agents at `src/python/agents/`:
  - `isr_observer.py` — Multi-domain sensor fusion (UAV, Satellite, SIGINT)
  - `strategy_analyst.py` — ROE evaluation and priority scoring
  - `tactical_planner.py` — Course of Action (COA) generation
  - `effectors_agent.py` — Execution and Battle Damage Assessment
  - `pattern_analyzer.py` — Activity pattern analysis
  - `ai_tasking_manager.py` — Sensor retasking optimization
  - `battlespace_manager.py` — Map layers and threat rings
  - `synthesis_query_agent.py` — SITREP generation and NL queries
  - `performance_auditor.py` — System performance monitoring
- Agents use `LLMAdapter` for provider abstraction; can run on heuristics if no LLM available

## Data Storage

**Configuration Storage:**
- YAML files: `theaters/*.yaml` (romania.yaml, baltic.yaml, south_china_sea.yaml)
  - Loaded at startup by `src/python/theater_loader.py`
  - Contains theater bounds, grid, UAV config, red force units, environment
  - Immutable dataclasses: `TheaterConfig`, `Bounds`, `GridConfig`, `BlueForce`, `RedForce`

**Event Logging:**
- Format: JSONL (one JSON object per line)
- Path: `logs/events-{YYYY-MM-DD}.jsonl` (daily rotation)
- Writer: Async background task in `src/python/event_logger.py`
- Queue: Async queue (default 10,000 item limit; drops on overflow)
- Rotation: `rotate_logs()` keeps most recent 7 days (configurable)
- Content: Structured events with timestamp, event_type, and data fields
- Implementation: `event_logger.py` with `log_event()`, `start_logger()`, `stop_logger()`, `rotate_logs()`

**Simulation State (In-Memory):**
- `SimulationModel` at `src/python/sim_engine.py` — Manages UAV positions, target states, modes
- State: Mutable dictionaries for drones and targets; broadcast to clients each tick
- Persistence: No persistent database; state reset on backend restart
- Immutable outputs: Sensor fusion results (`FusionResult`, `SensorContribution`) in `src/python/sensor_fusion.py`

**Ontology/Schema (Immutable):**
- `src/python/schemas/ontology.py` — Pydantic models for all domain objects
- Models: `Detection`, `Track`, `ISRObserverOutput`, `TargetClassification`, `EngagementDecision`, `SensorSource`
- Serialization: JSON via Pydantic; schema also exported to `src/python/schemas/ontology.json`

**File Storage:**
- Logs: Local filesystem (`logs/` directory)
- Theater configs: Local filesystem (`theaters/` directory)
- No cloud storage or CDN integrations

**Caching:**
- Memory-based state in `SimulationModel` (no Redis)
- Zustand stores (client-side): `src/frontend-react/src/shared/store.ts` for dashboard state

## Authentication & Identity

**Auth Provider:**
- None — System is internal/trusted environment (C2 system)
- WebSocket connections identified by client type: `DASHBOARD` (frontend) or `SIMULATOR` (video feed)
- No user authentication or authorization checks
- Rate limiting: `MAX_WS_CONNECTIONS = 20`, `RATE_LIMIT_MAX_MESSAGES = 30/sec` (hardcoded in `src/python/api_main.py`)

**Client Identification:**
- WebSocket handshake includes `client_type` (DASHBOARD or SIMULATOR)
- No JWT, OAuth, or API keys for client access
- Connection tracking: `connections` dict keyed by client type in `api_main.py`

## Monitoring & Observability

**Error Tracking:**
- None — No external error tracking service (Sentry, Rollbar, etc.)

**Logs:**
- Structured logging via `structlog` 24.1.0+
- Output: Console (colored, JSON-formatted per environment)
- Event logging: JSONL files with daily rotation in `logs/events-{date}.jsonl`
- Log level: Configurable via `LOG_LEVEL` env var (default: `INFO`)
- Config: `src/python/logging_config.py` sets up structlog formatting

**Metrics:**
- No external metrics service (Prometheus, CloudWatch, etc.)
- Performance auditing: `src/python/agents/performance_auditor.py` tracks internal metrics

## CI/CD & Deployment

**Hosting:**
- Local development: FastAPI on `:8000`, frontend dev server on `:3000`
- Docker support: `Dockerfile` (not present in codebase; deployment TBD)
- No cloud hosting integration detected (AWS, GCP, Azure, Heroku)

**CI Pipeline:**
- Playwright E2E tests via GitHub Actions (inferred from `playwright.config.ts`)
- Test script: `npm run test:e2e` runs all tests in headless Chrome
- Test variants: `test:e2e:headed`, `test:e2e:ui`, `test:e2e:debug`, `test:e2e:live` (with real backend)

**Build:**
- Frontend: `npm run build` → TypeScript + Vite bundling
- Backend: Python modules loaded directly; no compilation
- Launcher: `./grid_sentinel.sh` starts all services (backend, frontend, simulator)

## Environment Configuration

**Required env vars:**
- `GEMINI_API_KEY` - Google Gemini API (primary LLM provider)
- `HOST` - Server bind address (optional; default: `0.0.0.0`)
- `PORT` - Server port (optional; default: `8000`)
- `SIMULATION_HZ` - Tick rate (optional; default: `10`)
- `DEFAULT_THEATER` - Theater to load (optional; default: `romania`)

**Optional env vars:**
- `OPENAI_API_KEY` - OpenAI fallback
- `ANTHROPIC_API_KEY` - Anthropic Claude fallback
- `LOG_LEVEL` - Logging level (optional; default: `INFO`)
- `WS_BACKEND_URL` - WebSocket backend URL for simulator clients (optional; default: `ws://localhost:8000/ws`)
- `DEMO_MODE` - Enable demo auto-pilot (optional; default: `false`)

**Secrets location:**
- `.env` file (git-ignored via `.gitignore`)
- Template: `.env.example` in root directory
- Loaded at startup via `config.py` (PydanticSettings)

**Demo Mode:**
- Enabled via `DEMO_MODE=true` environment variable
- Bypasses human-in-the-loop (HITL) for nominations, COAs, and engagement decisions
- Auto-pilot loop in `src/python/api_main.py.demo_autopilot()`

## Webhooks & Callbacks

**Incoming:**
- None detected — System does not expose inbound webhook endpoints

**Outgoing:**
- None detected — System does not call external webhooks

**WebSocket Communication:**
- Frontend ↔ Backend: `ws://localhost:8000/ws` (or configured via `WS_BACKEND_URL`)
- Client messages: `scan_area`, `follow_target`, `paint_target`, `intercept_target`, `cancel_track`, `move_drone`, `spike`, `approve_nomination`, `reject_nomination`, `authorize_coa`, `verify_target`
- Server broadcasts: Full simulation state (drones, targets, grid zones, theater bounds, assistant messages) each tick

**Video Streaming (Drone Simulator):**
- Drone camera feed: Base64 MJPEG frames sent via WebSocket
- Simulator client: `src/python/vision/video_simulator.py` sends OpenCV-rendered frames
- Integration: Frontend displays in PIP (Picture-in-Picture) component

## Geospatial Services

**Tile Server (CartoDB):**
- Tile URL: `https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`
- Used in: `src/frontend-react/src/hooks/useCesiumViewer.ts` and `DetailMapDialog.tsx`
- Type: Dark-themed map tiles for Cesium globe background

**Cesium Ion (Optional):**
- Not configured in current codebase
- Cesium loaded via CDN (handled by `vite-plugin-cesium`)

---

*Integration audit: 2026-03-20*
