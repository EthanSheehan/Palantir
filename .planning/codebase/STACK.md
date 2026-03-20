# Technology Stack

**Analysis Date:** 2026-03-20

## Languages

**Primary:**
- Python 3.9.6 - FastAPI backend, AI agents, simulation engine
- TypeScript 5.5.0 - React frontend, E2E tests, configuration
- JavaScript (ES modules) - Node.js package management

**Secondary:**
- YAML - Theater configuration files (`theaters/*.yaml`)
- JSONL - Event logging (async daily-rotated logs)

## Runtime

**Environment:**
- Python 3.9.6 (backend environment via `./venv/`)
- Node.js v25.8.1 (frontend tooling and dependencies)

**Package Manager:**
- npm 11.11.0
- pip (via Python venv at `./venv/`)
- Lockfile: `package-lock.json` (present), `requirements.txt` pinned

## Frameworks

**Core Backend:**
- FastAPI 0.109.0+ - RESTful API and WebSocket server at `:8000`
- Uvicorn 0.27.0+ - ASGI server running 10Hz simulation loop

**Frontend:**
- React 18.3.1 - Component-based UI with TypeScript
- Vite 5.4.0 - Build bundler and dev server (`:3000` in development)
- Zustand 4.5.0 - Lightweight client state management

**Geospatial:**
- Cesium 1.114.0 - 3D mapping, visualization, entity tracking (globe, entities, camera)
- vite-plugin-cesium 1.2.23 - Webpack configuration for Cesium CDN loading

**UI Components:**
- Blueprint.js 5.13.0+ (`@blueprintjs/core`, `@blueprintjs/icons`, `@blueprintjs/select`) - Dark-theme component library
- ECharts 5.5.0 - Chart and visualization library
- echarts-for-react 3.0.2 - React wrapper for ECharts

**Agent & LLM Framework:**
- LangGraph 0.0.21+ - Multi-agent orchestration framework
- LangChain 0.1.33+ - Agent tools and utilities (OpenAI integration)
- Structlog 24.1.0+ - Structured logging with JSON output

**Testing:**
- Playwright 1.58.2 - E2E browser testing (headless Chrome, WebGL mode)
- pytest-asyncio 0.23.0+ - Async test execution for Python
- TypeScript 5.9.3 - Type checking and compilation

**Build/Dev:**
- TypeScript 5.9.3 (root) + 5.5.0 (frontend) - Compilation and type safety
- ts-node 10.9.2 - TypeScript execution for Node
- @types/node 25.5.0 - Node.js type definitions

## Key Dependencies

**Critical:**
- FastAPI 0.109.0+ - REST/WebSocket framework; no substitutes in Python
- React 18.3.1 - UI component library; strategic choice for interactive dashboards
- Cesium 1.114.0 - 3D geospatial rendering; required for globe visualization
- LangGraph 0.0.21+ - Multi-agent state management and routing
- Pydantic 2.0+ - Data validation and schema definition (ontology)

**Infrastructure:**
- websockets 12.0+ - WebSocket client/server communication (simulated clients)
- requests 2.31.0+ - HTTP client (test data synthesis, external probes)
- numpy 1.24.0+ - Numerical/physics calculations (UAV position, sensor models)
- opencv-python 4.8.0+ - Computer vision for drone video simulation

**AI/LLM:**
- langchain-openai 0.0.8+ - OpenAI API client (fallback if Gemini/Anthropic unavailable)
- anthropic 0.40.0+ - Anthropic Claude API (agent reasoning)
- google-genai 1.0.0+ - Google Gemini API (primary LLM provider)
- ollama 0.4.0+ - Local LLM inference (fallback when no cloud API available)

**Configuration & Logging:**
- pydantic-settings 2.0+ - Environment-based configuration with validation
- python-dotenv 1.0.0+ - `.env` file loading
- PyYAML 6.0+ - YAML parsing for theater configuration files

## Configuration

**Environment:**
- `.env` file (git-ignored) — Required for API keys and server configuration
- `config.py` at `src/python/config.py` — Pydantic BaseSettings for validation
- Environment variables:
  - `OPENAI_API_KEY` - OpenAI LLM (optional fallback)
  - `ANTHROPIC_API_KEY` - Anthropic Claude (optional)
  - `GEMINI_API_KEY` - Google Gemini (primary provider)
  - `HOST` - Server bind address (default: `0.0.0.0`)
  - `PORT` - Server port (default: `8000`)
  - `LOG_LEVEL` - Logging verbosity (default: `INFO`)
  - `SIMULATION_HZ` - Tick rate (default: `10`)
  - `WS_BACKEND_URL` - WebSocket backend URL for simulator clients
  - `DEMO_MODE` - Enable auto-pilot mode (default: `false`)

**Build:**
- `tsconfig.json` (root) — TypeScript configuration
- `src/frontend-react/tsconfig.json` — Frontend TypeScript config
- `src/frontend-react/vite.config.ts` — Vite build config with React plugin
- `playwright.config.ts` - E2E test configuration (Chrome with WebGL)
- `.prettierrc` (Cesium dependency; frontend uses Prettier for formatting)

**Theater Configuration:**
- YAML files at `theaters/*.yaml` (romania.yaml, baltic.yaml, south_china_sea.yaml)
- Loaded by `src/python/theater_loader.py` at startup
- Contains bounds, grid, UAV config, red force units, environment, enemy UAVs

## Platform Requirements

**Development:**
- Python 3.9+ virtual environment
- Node.js v14+ (tested on v25.8.1)
- npm v6+ (tested on 11.11.0)
- MacOS/Linux/Windows with git

**Production:**
- Python 3.9+ runtime (with pip dependencies installed)
- Node.js for frontend build (can be removed post-build)
- WebSocket-capable HTTP server (FastAPI handles this via Uvicorn)
- 2+ GB RAM for simulation + browser rendering

**Browser Requirements (Frontend):**
- Chrome/Chromium with WebGL support
- Modern JavaScript (ES2020+)
- Cesium requires WebGL 2.0

---

*Stack analysis: 2026-03-20*
