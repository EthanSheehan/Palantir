# External Integrations

**Analysis Date:** 2026-03-19

## APIs & External Services

**LLM Providers (Chain: Gemini → Claude → Ollama → Heuristic Fallback):**
- Google Gemini (gemini-2.0-flash) - Primary LLM provider
  - SDK: `google-genai` (pip)
  - Auth: `GEMINI_API_KEY` environment variable
  - Used by: `src/python/llm_adapter.py` for all agent reasoning
  - Models: "gemini-2.0-flash" (fast/default), "gemini-2.5-pro-preview-06-05" (reasoning)

- Anthropic Claude - Secondary LLM provider
  - SDK: `anthropic` (pip)
  - Auth: `ANTHROPIC_API_KEY` environment variable
  - Models: "claude-haiku-4-5-20251001" (fast), "claude-sonnet-4-6" (default/reasoning)
  - Fallback if Gemini unavailable

- Ollama (Local) - Tertiary provider (no API keys needed)
  - SDK: `ollama` (pip)
  - Endpoint: `http://localhost:11434` (configurable)
  - Models: llama3.2:8b (fast/default), llama3.3:70b (reasoning)
  - Fallback if both cloud providers unavailable

**Provider Chain Logic (`src/python/llm_adapter.py`):**
1. Check GEMINI_API_KEY → probe google-genai SDK
2. If unavailable, check ANTHROPIC_API_KEY → probe anthropic SDK
3. If unavailable, probe Ollama at localhost:11434
4. If all fail, use heuristic fallback (rule-based responses)

## Data Storage

**No Persistent Database:**
- Simulation state is ephemeral (in-memory only)
- All data structures live in `SimulationModel` (`src/python/sim_engine.py`)
- Theater configs loaded from YAML files: `theaters/romania.yaml`, `theaters/south_china_sea.yaml`, `theaters/baltic.yaml`
- Ontology schemas defined in `src/python/schemas/ontology.py` (Pydantic models, JSON serializable)

**File Storage:**
- Local filesystem only for theater configuration and logs
- No cloud storage integration
- Video frames from simulator stored temporarily in memory for WebSocket transmission (base64 MJPEG)

**Caching:**
- None. Frontend state managed via Zustand store (`src/frontend-react/src/store/SimulationStore.ts`)
- COA caching at message level via `setCachedCoas(entry_id, coas)` for HITL workflow

## Authentication & Identity

**Auth Provider:**
- None. System is not multi-user.
- No authentication layer required
- WebSocket clients identified by type only: `DASHBOARD` (frontend) vs `SIMULATOR` (drone simulator)

**Client Identification (`src/python/api_main.py`):**
- WebSocket clients send `IDENTIFY` message with `client_type` field
- Types: "DASHBOARD" (Cesium UI), "SIMULATOR" (video feed source)
- No user accounts, API keys, or session tokens

## Monitoring & Observability

**Error Tracking:**
- None (Sentry, Rollbar, etc. not integrated)
- Server-side errors logged to console via structlog

**Logs:**
- **Backend:** Structured logging via `structlog` 24.1.0+
  - Config: `src/python/logging_config.py`
  - Format: JSON (machine-readable)
  - Level: Configurable via `LOG_LEVEL` env var (default: INFO)
  - Sent to: stdout/stderr

- **Frontend:** Browser console only
  - No remote logging integration
  - React/Vite development warnings and errors to console

- **Event Logger:** `src/python/event_logger.py` provides low-level event capture for testing/audit trails

## CI/CD & Deployment

**Hosting:**
- Single-machine deployment (no cloud-specific integrations)
- Self-hosted via FastAPI/Uvicorn on port 8000
- Frontend built to static files (Vite), served by browser directly

**CI Pipeline:**
- GitHub Actions (implied by playwright.config.ts CI detection)
- Playwright tests run with environment detection: `process.env.CI` triggers webServer config
- Test reporters: HTML (Playwright), JUnit XML (CI integration)

**Build Process:**
- Backend: No compilation needed (pure Python)
- Frontend: `npm run build` → Vite → `src/frontend-react/dist/` (static files)
- Launch: `./palantir.sh` orchestrates backend + frontend + simulator

## Environment Configuration

**Required env vars (from `.env.example`):**
- `OPENAI_API_KEY` - Optional (deprecated, not actively used)
- `ANTHROPIC_API_KEY` - Optional (falls back to Gemini if not set)
- `GEMINI_API_KEY` - Recommended (primary LLM)
- `HOST` - Server bind address (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `SIMULATION_HZ` - Tick rate in Hz (default: 10)
- `DEFAULT_THEATER` - Initial scenario (romania/south_china_sea/baltic)
- `WS_BACKEND_URL` - WebSocket URL for simulator clients
- `DEMO_MODE` - Boolean flag (true = auto-pilot mode)

**Secrets location:**
- `.env` file (git-ignored, not committed)
- Environment variables loaded at process startup
- Validation: `PalantirSettings` raises `ValidationError` if required keys missing

## Webhooks & Callbacks

**Incoming:**
- WebSocket: Frontend sends JSON actions to `ws://localhost:8000/ws`
  - Actions: `spike`, `move_drone`, `intercept_target`, `follow_target`, `paint_target`, `cancel_track`, `approve_nomination`, `reject_nomination`, `authorize_coa`, `switch_theater`
  - Rate limiting: 30 msgs/sec per client with 1-sec window

- REST API: Theater management
  - `GET /api/theaters` - List available theaters
  - `POST /api/theater` - Switch theater (`{"theater": "romania"}`)

**Outgoing:**
- WebSocket: Backend broadcasts state to all DASHBOARD clients
  - Message type: `state` with full simulation snapshot (drones, targets, grid zones)
  - Message type: `ASSISTANT_MESSAGE` with tactical recommendations
  - Message type: `HITL_UPDATE` with COA options during nomination workflow
  - Frequency: 10 Hz (simulator tick rate)

---

*Integration audit: 2026-03-19*
