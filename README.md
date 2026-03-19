# AMS v0.2 (Grid 11) — Autonomous Mission System

Real-time UAV fleet management platform built around a macro-grid demand/supply rebalancing model over Romania. Combines a 3D Cesium.js geospatial viewer with a domain-driven FastAPI backend, connected via dual WebSocket channels. Runs as a PyQt5 desktop application.

## Quick Start

### Option A: Desktop App (recommended)

```bash
python start.py
```

Launches backend (FastAPI on port 8012), frontend (HTTP server on port 8093), and opens a PyQt5 desktop window.

### Option B: Development (separate terminals)

```bash
# Terminal 1 — Backend
cd backend && python main.py
# Runs FastAPI on http://localhost:8012

# Terminal 2 — Frontend
cd frontend && python -m http.server 8093
# Open http://localhost:8093 in your browser
```

## Architecture

| Layer | Technology | Port |
|-------|-----------|------|
| Desktop wrapper | PyQt5 + QWebEngineView | — |
| 3D Map / UI | Cesium.js 1.114, vanilla JS, HTML/CSS | 8093 |
| HTTP API | FastAPI (Python) | 8012 |
| WebSocket (legacy) | `/ws/stream` — 10Hz sim state broadcast | 8012 |
| WebSocket (events) | `/ws/events` — domain event stream | 8012 |
| Database | SQLite (`ams.db`) | — |
| Simulation | 20 UAVs, Romania macro-grid | — |

## Features

- **3D Globe**: Cesium.js with CartoDB dark basemap, terrain, and cinematic lighting
- **Macro-Grid Visualization**: Real-time zone imbalance coloring (red=shortage, blue=surplus)
- **UAV Fleet**: 20 simulated drones with idle/serving/repositioning modes
- **Waypoint Control**: Click-to-set waypoints via map interaction tools
- **Mission Management**: Create, approve, and monitor missions with state machine lifecycle
- **Timeline**: Canvas-based swimlane timeline with scrubbing and replay
- **Satellite Lens**: Secondary Cesium viewer for close-up drone inspection
- **Alerts**: Auto-generated alerts from domain events with severity levels
- **Multi-UAV Selection**: Shift+click and drag-drop selection

## Documentation

See `docs/` for detailed specifications:
- `SYSTEM_ARCHITECTURE.md` — Complete technical reference
- `architecture.md` — High-level architectural principles
- `domain_model.md` — Entity definitions and relationships
- `state_machines.md` — State transition diagrams
- `event_catalog.md` — Domain event types and payloads
- `api_contract.md` — REST and WebSocket API specification
- `desktop_host_spec.md` — Desktop app lifecycle specification

## Dependencies

- Python 3.10+
- PyQt5 + PyQtWebEngine
- FastAPI + uvicorn
- pydantic
- Cesium.js 1.114 (loaded from CDN)
