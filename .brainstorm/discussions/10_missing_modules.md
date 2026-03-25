# 10 — Missing Modules Analysis

## Priority Stack for Autonomous Operations

| Rank | Module | Why Critical for /autopilot |
|------|--------|---------------------------|
| 1 | ROE Engine | Safety constraint — current LLM evaluation is non-deterministic |
| 2 | Persistence Layer | Mission continuity, audit trail, crash recovery |
| 3 | AI Explainability | Accountability for every autonomous decision |
| 4 | AAR Engine | Primary feedback loop for tuning autonomous thresholds |
| 5 | Scenario Scripting | Reproducible testing of autonomous decision paths |
| 6 | Logistics Module | Resource constraints forcing real triage decisions |
| 7 | Sim Fidelity Controls | Fast-forward/inject for developer testing velocity |
| 8 | Terrain Analysis | Sensor coverage realism with LOS |
| 9 | Weather Engine | Activates existing EnvironmentConditions infrastructure |
| 10 | EW Module | Contested spectrum realism |
| 11 | Comms Simulation | Graceful degradation testing |
| 12 | Export/Reporting | Deliverable mission reports |
| 13 | Mission Planning | Pre-mission intent injection |
| 14 | Multi-User/RBAC | Multi-station deployment |
| 15 | Plugin System | Extension interface for new capabilities |

## Module Details

### 1. ROE Engine
Formal rule-based ROE evaluation replacing non-deterministic LLM strategy analyst. Declarative rules: target type + zone + autonomy level + collateral → permitted/denied/escalate. Deterministic compliance layer with LLM advisory — ROE engine has veto power in AUTONOMOUS mode.

**Interfaces:** `ROERule`, `ROEEngine.evaluate()`, `ROEDecision`, `ROEChangeLog`

### 2. Persistence Layer
SQLite (local) / PostgreSQL (multi-user). Serialize simulation state on transitions. Mission recording as time-indexed snapshots. Leverages existing frozen dataclasses in hitl_manager.

**Interfaces:** `MissionStore`, `StrikeArchive`, `EventIndex`, WS actions: `load_mission`, `save_checkpoint`

### 3. AI Explainability Layer
Structured reasoning trace per decision: input features, weight breakdown, alternatives rejected, confidence. The `reasoning_trace` field exists on StrikeBoardEntry but is a plain LLM string.

**Interfaces:** `DecisionExplanation`, `ExplainabilityStore`, Frontend: "Why?" button on HITL entries

### 4. After-Action Review (AAR)
Variable-speed replay (1x-50x), decision timeline, AI vs operator comparison, structured AAR report export.

**Interfaces:** `AAREngine`, `DecisionTimeline`, `AARExporter`, Frontend: AAR tab with timeline scrubber

### 5. Scenario Scripting
YAML exercise scripts — inject events at T+N, spawn targets, trigger weather, simulate comms degradation. The difference between demo mode and training mode.

**Interfaces:** `ScenarioLoader`, `ScenarioPlayer`, event types: `SpawnTarget`, `SetWeather`, `DegradeComms`, etc.

### 6. Logistics Module
Fuel, ammunition, maintenance per UAV. Fuel depletes by speed/mode, ammo decrements on engagement, thresholds trigger RTB.

**Interfaces:** `UAVLogistics`, `LogisticsManager`, swarm coordinator filters by fuel threshold

### 7. Simulation Fidelity Controls
Time compression (1x-50x), pause/resume, event injection mid-sim.

**Interfaces:** `SimController`, WS action: `sim_control`, Frontend: speed selector + pause/play

### 8. Terrain Analysis
LOS calculations using DEM, dead zone identification, route optimization for UAV paths.

**Interfaces:** `TerrainModel.los()`, `DeadZoneMap`, `RouteOptimizer`, integration with sensor_model

### 9. Weather/Environment Engine
Dynamic weather fronts, precipitation events, visibility degradation. Activates existing `EnvironmentConditions` dataclass which currently sits at static defaults.

**Interfaces:** `WeatherState`, `WeatherEngine.tick()`, scenario scripting integration

### 10. Electronic Warfare Module
Jamming effects on sensors, GPS spoofing, comms degradation. Enemy `JAMMING` type already exists.

**Interfaces:** `JammerModel`, `EWEnvironment`, integration with sensor_fusion weights

### 11. Communication Simulation
Model degraded comms: latency, packet loss, bandwidth throttling per link.

**Interfaces:** `CommsLink`, `CommsSimulator`, presets: FULL/CONTESTED/DENIED/RECONNECT

### 12. Export/Reporting
Mission reports in PDF/CSV/JSON. Target summaries, engagement outcomes, AI decision audit.

**Interfaces:** `ReportGenerator`, `MissionReport`, `PDFExporter`, `CSVExporter`

### 13. Mission Planning Interface
Drag-and-drop pre-planning: patrol routes, search zones, UAV assignments, initial autonomy.

**Interfaces:** `MissionPlan`, `MissionPlanLoader`, Frontend: PLAN mode on Cesium map

### 14. Multi-User/RBAC
Role-based access: Commander, Analyst, Sensor Operator, Administrator. JWT auth on WebSocket.

**Interfaces:** `UserSession`, `RBACGate`, permission table per action, Frontend: login screen

### 15. Plugin/Extension System
Extension interface for new sensor types, target types, agent capabilities without modifying core.

**Interfaces:** `SensorPlugin`, `TargetPlugin`, `AgentPlugin`, `PluginRegistry`
