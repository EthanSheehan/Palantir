# Technology Stack

**Analysis Date:** 2026-03-19

## Languages

**Primary:**
- Python 3.10+ - Backend FastAPI server, multi-agent orchestration, simulation engine
- TypeScript 5.9+ - Frontend React components, E2E tests
- JavaScript (ES6) - Frontend framework
- YAML - Theater configuration and scenario definitions

**Secondary:**
- JSON - API communication, WebSocket protocol, ontology serialization

## Runtime

**Environment:**
- Python 3.10+ with virtual environment at `./venv/`
- Node.js (TypeScript/JavaScript toolchain)
- Browser environment (WebGL via Cesium)

**Package Manager:**
- Python: pip (with requirements.txt)
- Node/npm: npm (with package-lock.json)
- Lockfile: Present for both ecosystems

## Frameworks

**Backend:**
- FastAPI 0.109.0+ - HTTP + WebSocket server (`src/python/api_main.py`)
- Uvicorn 0.27.0+ - ASGI application server
- LangChain/LangGraph 0.0.21+ - Multi-agent orchestration framework
- Pydantic 2.0+ - Data validation and serialization
- Pydantic-Settings 2.0+ - Environment configuration management

**Frontend:**
- React 18.3.1 - UI framework
- Vite 5.4.0+ - Build tool and dev server
- TypeScript 5.5.0+ - Type safety
- Cesium 1.114.0+ - 3D geospatial visualization
- ECharts 5.5.0+ - Data visualization and analytics
- Blueprint.js 5.13.0+ - UI component library
- Zustand 4.5.0 - State management

**Testing:**
- Playwright 1.58.2+ - E2E browser testing
- pytest with pytest-asyncio 0.23.0+ - Python unit/integration tests
- ts-node 10.9.2+ - TypeScript execution for tests

## Key Dependencies

**Critical (Backend):**
- structlog 24.1.0+ - Structured logging
- websockets 12.0+ - WebSocket protocol support
- numpy 1.24.0+ - Scientific computing for simulation
- opencv-python 4.8.0+ - Computer vision (drone video processing)
- requests 2.31.0+ - HTTP client
- PyYAML 6.0+ - YAML theater configuration parsing

**LLM Providers:**
- anthropic 0.40.0+ - Claude API integration
- google-genai 1.0.0+ - Gemini API integration
- ollama 0.4.0+ - Local LLM support (Llama 3.2/3.3 models)

**Infrastructure:**
- python-dotenv 1.0.0+ - Environment variable loading
- Playwright dev dependency for E2E testing

## Configuration

**Environment:**
- Loaded via `src/python/config.py` (PalantirSettings class)
- `.env` file with python-dotenv (see `.env.example`)
- Key configs required:
  - `OPENAI_API_KEY` (optional - for agent LLM features)
  - `ANTHROPIC_API_KEY` (optional - Claude support)
  - `GEMINI_API_KEY` (primary LLM provider)
  - `HOST`, `PORT` (server binding)
  - `SIMULATION_HZ` (tick rate, default 10)
  - `DEFAULT_THEATER` (romania/south_china_sea/baltic)
  - `WS_BACKEND_URL` (WebSocket URL for simulator clients)
  - `DEMO_MODE` (boolean, enables auto-pilot)

**Build (Frontend):**
- `src/frontend-react/vite.config.ts` - Vite configuration with Cesium plugin
- Dev proxy: `/api/*` → `http://localhost:8000`
- Dev WebSocket proxy: `/ws` → `ws://localhost:8000`
- Build output: `src/frontend-react/dist/`

**Build (Backend):**
- `src/python/logging_config.py` - Structured logging setup
- No compiled artifacts (pure Python)

## Platform Requirements

**Development:**
- Python 3.10+, pip, venv
- Node.js (npm package manager)
- System packages: opencv-python build dependencies (gcc, libsm6, libxext6)
- GPU not required (CPU-based simulation + Canvas-based WebGL rendering)

**Production:**
- Deployment target: Single-machine Linux/macOS/Windows
- WebSocket support (10Hz state broadcast, JSON payloads ~50-100KB)
- No containerization required (bare metal Python/Node execution)
- Frontend: Static files served by Vite build output (dist/)
- Backend: FastAPI/Uvicorn on port 8000

---

*Stack analysis: 2026-03-19*
