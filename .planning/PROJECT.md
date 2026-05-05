# Grid-Sentinel — Project Definition

## What This Is

A decision-centric AI-assisted Command & Control (C2) system that automates the F2T2EA kill chain using multi-agent AI orchestration, coordinated drone swarm operations with multi-sensor fusion, a physics-based tactical simulator, and a professional React+Blueprint+Cesium 3D geospatial frontend.

## Core Value

Automated kill chain acceleration through sensor fusion and swarm coordination — from detection to engagement with human-in-the-loop oversight at every gate.

## Requirements

### Validated

- ✓ Multi-sensor fusion (complementary `1 - product(1 - ci)`) — v1.0
- ✓ Target verification pipeline (DETECTED→CLASSIFIED→VERIFIED→NOMINATED) — v1.0
- ✓ Drone modes & autonomy (SUPPORT/VERIFY/OVERWATCH/BDA + 3-tier) — v1.0
- ✓ Swarm coordination (auto-dispatch complementary sensors) — v1.0
- ✓ Information feeds (INTEL/SENSOR/COMMAND + subscription routing) — v1.0
- ✓ Battlespace assessment (clustering, coverage gaps, corridors) — v1.0
- ✓ Adaptive ISR (priority queue + threat-adaptive coverage) — v1.0
- ✓ Map modes (6 views + layer toggles + camera presets) — v1.0
- ✓ Drone feed upgrade (EO/SAR/SIGINT + PIP/SPLIT/QUAD) — v1.0
- ✓ Event logging (JSONL, daily rotation) — v1.0
- ✓ React + Blueprint + CesiumJS migration — v1.0
- ✓ 10Hz simulation loop maintained — v1.0
- ✓ Demo autopilot end-to-end — v1.0

### Active

(None — next milestone not yet planned)

### Out of Scope

- Mobile app — desktop C2 workstation focus
- Offline mode — real-time WebSocket architecture
- Full sim replay — event log sufficient for audit
- Conjure/AtlasDB/Plottable — Blueprint-only adoption from Grid-Sentinel repos

## Context

Shipped v1.0 with ~57K LOC Python + ~41K LOC TypeScript/React.
Tech stack: FastAPI, React 18, TypeScript, Blueprint v6, CesiumJS, Zustand, Vite, ECharts, LangGraph/LangChain.
11 phases executed across 222 commits in 6 days.
Theater-configurable via YAML (Romania, South China Sea, Baltic).

## Key Decisions

| Decision | Choice | Outcome |
|----------|--------|---------|
| Frontend framework | React 18 + TypeScript + Blueprint v6 | ✓ Good — professional C2 UI, dark theme, maintainable |
| Cesium integration | Custom ref-based hooks (not resium) | ✓ Good — SampledPositionProperty, GroundPrimitive work correctly |
| State management | Zustand v4 | ✓ Good — simple, works with 10Hz WebSocket push |
| Build tool | Vite | ✓ Good — fast HMR, CesiumJS plugin works |
| Charting | Apache ECharts | ✓ Good — waterfall, heatmap, dark theme |
| Fusion algorithm | Complementary: `1 - product(1 - ci)` | ✓ Good — simple, correct, no tuning params |
| Autonomy model | 3-tier (MANUAL/SUPERVISED/AUTONOMOUS) | ✓ Good — military C2 HITL requirement met |
| No StrictMode | Cesium Viewer double-mount breaks | ✓ Good — necessary workaround |
| Event bridge | Window custom events (grid_sentinel:send, etc.) | ✓ Good — Cesium→React bridge without prop drilling |
| Enemy UAV IDs | Start at 1000 | ✓ Good — no collision with target/UAV IDs |

## Constraints

- Single-machine deployment (laptop demo)
- OpenAI API key required for LangChain agents
- CesiumJS ion token for terrain/imagery
- No StrictMode (Cesium incompatibility)

---
*Last updated: 2026-03-20 after v1.0 milestone*
