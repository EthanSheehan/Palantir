# Palantir Swarm Upgrade — Project Definition

## Goal
Transform Palantir from individual-UAV operation into a coordinated drone swarm C2 system with multi-sensor fusion, automated target verification, battlespace assessment, and a professional React+Blueprint UI.

## Scope
- 10 phases (Stage 0-9)
- ~8,000 new/changed lines (6,100 original + React migration)
- Full frontend migration to React + TypeScript + Blueprint
- 7 new Python backend modules
- Apache ECharts for tactical charts
- Event logging infrastructure

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend framework | React 18 + TypeScript + Blueprint v6 | Professional C2 UI components, dark theme, data tables, maintainable at scale |
| Build tool | Vite | Fast HMR, ESM native, CesiumJS plugin available |
| Charting | Apache ECharts (echarts-for-react) | Active maintenance, real-time streaming, heatmaps, waterfall, WebGL |
| Cesium integration | resium or custom React wrapper | Keep Cesium for 3D globe, wrap in React component |
| State management | Zustand (lightweight) | Simpler than Redux, works with WebSocket push model |
| Sensor fusion algorithm | Complementary: `1 - product(1 - ci)` | Simple, correct, no tuning params |
| UAV sensor model | Multi-sensor (some UAVs carry 2+ sensors) | Enables richer fusion without requiring more UAVs |
| Sensor assignment | Random distribution at spawn | EO_IR 50%, SAR 30%, SIGINT 20% |
| Persistence | Event log to disk (JSONL) | Audit trail, no full replay |
| Palantir repos | Blueprint only (selective) | Conjure/AtlasDB/Plottable don't fit |
| Autonomy model | 3-tier (MANUAL/SUPERVISED/AUTONOMOUS) | Military C2 human-in-the-loop requirement |

## Success Criteria
- [ ] Multi-sensor fusion: 3 UAVs on target → fused confidence visible
- [ ] Verification pipeline: DETECTED→CLASSIFIED→VERIFIED with visual stepper
- [ ] Swarm: system auto-dispatches complementary sensors
- [ ] Assessment: threat clusters, coverage gaps on map
- [ ] Professional UI: Blueprint components, dark theme, responsive panels
- [ ] All existing functionality preserved (demo autopilot, strike board, all modes)
- [ ] `./palantir.sh --demo` runs end-to-end with new features
