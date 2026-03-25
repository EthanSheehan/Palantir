# 05 — Dependency Audit

## Python Dependencies (requirements.txt)

### Outdated & Deprecation Risks

| Dependency | Current Pin | Latest | Issue |
|-----------|------------|--------|-------|
| langgraph | >= 0.0.21 | 1.x | Very loose pin, 0.0.x is legacy |
| langchain-openai | >= 0.0.8 | 0.1.x+ | Legacy namespace |
| langchain-core | >= 0.1.33 | 0.2.x+ | Minor version behind |
| opencv-python | >= 4.8.0 | 4.10.x | Not critical but upgrade |
| pydantic | >= 2.0 | 2.5+ | Tighten lower bound |

### No Critical CVEs Detected
- requests 2.32.4: clean
- numpy 2.0.2: clean (major version jump from pin — verify compatibility)
- websockets 15.0.1: secure
- All LLM client libs actively maintained

## Frontend Dependencies (package.json)
- Stack is solid: React 18, Blueprint 5, Cesium, echarts, zustand
- No critical issues

## Missing Domain-Specific Libraries

| Library | Domain | Why It Matters | Priority |
|---------|--------|---------------|----------|
| **PostgreSQL/TimescaleDB** | Persistence | All state ephemeral — no replay, no audit | CRITICAL |
| **Redis** | Distributed state | Can't scale beyond single process | HIGH |
| **turf.js** | Geospatial analytics | Buffer zones, distances, bearing calculations | HIGH |
| **shapely** | Geometry operations | Zone calculations, coverage analysis | HIGH |
| **OpenTelemetry** | Observability | No distributed tracing for agents | MEDIUM |
| **h3-py** | Hexagonal indexing | Could optimize threat clustering | LOW |
| **MQTT (paho-mqtt)** | Pub/sub | WebSocket single-point-of-failure | MEDIUM |

## Missing Dev Dependencies

| Tool | Status | Recommendation |
|------|--------|---------------|
| Pre-commit hooks | Missing | Add .pre-commit-config.yaml |
| black + isort | Missing | Python formatting |
| flake8/pylint | Missing | Python linting |
| mypy | Missing | Python type checking |
| ESLint + Prettier | Missing | Frontend linting |
| Jest/Vitest | Missing | Frontend unit tests |
| Docker | Missing | Dockerfile + docker-compose |
| pyproject.toml | Missing | Replace loose requirements.txt |

## Build/Install Assessment

| Aspect | Status |
|--------|--------|
| venv setup | Good — ./venv/ + requirements.txt |
| Native deps (opencv) | C++ compilation required; works |
| Frontend build | Excellent — Vite + esbuild |
| Docker | **Missing** — needs Dockerfile + compose |
| Lock files | package-lock.json exists; Python pins are loose |

## Recommendations (Prioritized)

**Tier 1 — Critical:**
1. PostgreSQL + TimescaleDB for persistence
2. pyproject.toml with proper pinning
3. Pre-commit hooks (black, flake8, mypy)
4. Dockerfile + docker-compose
5. Redis for distributed state

**Tier 2 — Important:**
6. turf.js for frontend geospatial
7. shapely for backend geometry
8. OpenTelemetry instrumentation
9. ESLint + Prettier
10. mypy integration

**Tier 3 — Nice-to-have:**
11. h3-py for hexagonal clustering
12. gRPC if multi-service later
13. Helm charts for cloud deployment

## Version Pinning Recommendations

```
langgraph>=1.0.0,<2.0.0
langchain-openai>=0.1.0,<1.0.0
langchain-core>=0.2.0,<1.0.0
anthropic>=0.50.0,<1.0.0
opencv-python>=4.10.0,<5.0.0
pydantic>=2.5.0,<3.0.0
```
