---
tags: [grid_sentinel, blueprint, roadmap, maven_parity]
---
# Grid-Sentinel — Professional-Level Blueprint

*Generated 2026-05-06 · Companion to `docs/MAVEN_RESEARCH.md`*

## Premise

Grid-Sentinel is built on the same ideas as Palantir's Maven Smart System, but presented as a single-machine demo with hand-rolled components. The bones are good — 9 LangGraph agents, 4-state verification engine, multi-sensor fusion, swarm coordinator (Hungarian assignment), battlespace assessment, ROE engine, intel feed router, F2T2EA kill-chain tracker, 6 map modes, 3D pyrender renderer wired to the live SimulationModel, 1847 passing tests. The gap to "professional level" is mostly **integration and presentation**, not new algorithms.

This blueprint maps every named Maven capability onto either *we already have it (use it better)* or *we need to build it*, then sequences the work into four phases over the next ~6 weeks.

## The map: Maven feature → Grid-Sentinel today

| Maven capability | Grid-Sentinel today | Gap | Priority |
|---|---|---|---|
| Fused Map View (globe + sat + drone + SIGINT + roads) | Cesium globe + 6 map modes (`MapModeBar.tsx`) + 5 layer overlays | No per-INT layer toggle; no SIGINT/SAR overlays distinct from EO | **P0** |
| Detection Layer with stable identifiers across modalities | `Target.id` is stable; cross-modality fusion via `sensor_fusion.py:fuse_detections` | Stable IDs work but aren't *visualised* as the Maven-style numbered dot — operators today see icons, not the underlying track | **P0** |
| Kanban / Target Workbench | `FloatingStrikeBoard.tsx` (PENDING nominations only) + `KillChainRibbon` (per-phase counts) | No multi-column workbench — operators can't drag a target across `DETECTED → CLASSIFIED → VERIFIED → NOMINATED → AUTHORIZED → ENGAGED → BDA` | **P0** |
| AI Asset Tasking Recommender (which bomber, which munition) | `agents/ai_tasking_manager.py` now wired to `LLMAdapter` (committed `4d26b6f`) | No UI surface — recommendations live in WebSocket events but aren't presented as a ranked card list | **P0** |
| Imagery exploitation suite (AOI analysis, activity monitoring) | `pyrender_bridge.py` renders 3D from SimulationModel (committed `2c19a51`); `pattern_analyzer.py` exists but unused in UI | No "Area of Interest → activity timeline → pattern of life" UI loop | **P1** |
| LLM Model Hub (ChatGPT, Llama, Claude swappable per task) | `llm_adapter.py` does Gemini → Anthropic → Ollama → heuristic | No per-task model selection; the adapter can't hint "use reasoning model for COA, fast model for SITREP" via UI | **P1** |
| AIP-style natural-language operator chat | `tactical_assistant.py` exists, embedded in sim loop | No persistent chat panel that can hit *all* 9 agents (currently only TacticalAssistant gets a UI surface) | **P1** |
| Ontology layer (Foundry/Gotham unified) | `schemas/ontology.py` is a Pydantic file with ~30 models | Not really an *ontology* — no link types, action types, or dynamic security; entities are flat | **P2** |
| Cross-classification (3 security domains) | `rbac.py` JWT + 4 roles (OBSERVER/OPERATOR/COMMANDER/ADMIN) | Single classification only; no UNCLASS/CONFIDENTIAL/SECRET tiering on object-level | **P2** |
| Effects integration (AFATDS, JREAP, JADOCS, AMPS) | None | Need at least mock effector endpoints with realistic message schemas — the system stops at `engage_target` action | **P2** |
| Activity timeline / pattern of life | `pattern_analyzer.py` + `kill_chain_tracker.py` produce data | No timeline UI; `BottomTimelineDock` is sim-time scrub, not target activity history | **P1** |
| Multi-INT data sources (EO, SAR, SIGINT, MTI, FMV, geolocation) | `sensor_fusion.py` accepts EO_IR, SAR, SIGINT contributions; `sensor_model.py` Pd model | Only synthetic inputs — no ingest pipeline pretending to be ICEYE/Capella SAR or MQ-9 FMV | **P1** |
| Sensor-to-shooter latency dashboard | `metrics.py` Prometheus endpoint with histograms | No SLA dashboard tracking F2T2EA per-stage latency end-to-end | **P1** |
| Open / extensible third-party plug-in | LangGraph agent shape is consistent | No plug-in registry, no schema for adding a new agent without code edits | **P3** |
| Cloud + tactical edge (offline-capable) | Single-binary FastAPI on localhost | Not designed for disconnected operation; no checkpoint→sync flow | **P3** |
| Production scale / multi-user | `auth.py` + `rbac.py`; single-process | Not measured under load; no horizontal scaling story | **P3** |

## The four phases

### Phase 1 — Operator Surface Parity (P0, 2 weeks)

**Goal:** when a defence-industry observer demos the app, every screen they see has a Maven-equivalent.

#### 1.1 Target Workbench (replaces `FloatingStrikeBoard` overlay)
- New React panel `src/frontend-react/src/panels/TargetWorkbench.tsx`
- Columns map exactly to verification + kill-chain states: **DETECTED · CLASSIFIED · VERIFIED · NOMINATED · AUTHORIZED · ENGAGING · BDA · COMPLETE**
- Each column shows a stack of TargetCards. Card body = stable ID, type icon, fused-confidence bar, contributing UAV badges, time-in-state countdown
- Drag-to-advance is forbidden by ROE for state advancement (driven by `verification_engine.py`); explicit Approve/Reject buttons in NOMINATED column tied to existing `approve_nomination` / `reject_nomination` WebSocket actions
- Right-click on a card → context menu with `paint`, `intercept`, `request_swarm`, `retask_sensors`
- This is the headline change — it's what makes the app *look* like Maven at a glance

#### 1.2 Stable-ID detection layer
- Render every Target as a numbered dot (the stable `Target.id`) on the Cesium globe in addition to the current type icon
- Number persists through state transitions, sensor handoffs, and re-acquisition — visible proof of cross-modality tracking
- Color-coded ring around the dot encodes verification state (red=DETECTED, yellow=CLASSIFIED, green=VERIFIED, white-flash=NOMINATED)
- New hook: `src/frontend-react/src/cesium/useCesiumDetectionLayer.ts`

#### 1.3 Per-INT layer toggles
- Promote the existing 6 map modes from "single-active mode" to **stacked toggleable layers**: each of EO, SAR, SIGINT, MTI is its own toggle alongside Coverage / Threat / Fusion / Swarm / Terrain
- New `src/frontend-react/src/overlays/IntelLayerPanel.tsx` with one row per INT type
- Each row: visible toggle, opacity slider, source dropdown (which sensor types feed it)
- Backend already produces per-sensor-type contributions in `sensor_contributions[]` — frontend just needs to filter

#### 1.4 Asset Tasking Recommender drawer
- New panel `src/frontend-react/src/panels/AssetTaskingDrawer.tsx`
- Triggered when operator selects a target: streams ranked recommendations from `ai_tasking_manager.evaluate_and_retask_async`
- Card shows: asset ID, type, distance, ETA, sensor match, confidence, *why-trace* (the existing `reasoning` field on `SensorTaskingOrder`)
- One-click *Task* button issues the existing `retask_sensors` WebSocket action

#### 1.5 Maven-style chrome
- Yellow target boxes, blue friendly-zone boxes — match exact Maven palette
- Vertical taskbar from `grid-sentinel-2` finally gets ported (per `GRID_SENTINEL_2_PORT_STATUS.md`) — File / View menus + ISR / Plan / Strike workspace tabs
- Header strip: classification banner ("UNCLASSIFIED // FOUO // DEMO") at top of every screen — instantly reads as professional defence software

**Phase 1 success criterion:** a side-by-side screenshot test — Maven AIP demo on the left, Grid-Sentinel on the right — and a layperson can't tell which is which from layout alone.

### Phase 2 — Decision Loop Depth (P1, 2 weeks)

**Goal:** the agents Grid-Sentinel already has show their work in the UI, and a single chat panel can drive any of them.

#### 2.1 Unified AIP-style chat panel
- Replace the existing TacticalAssistant single-stream panel with an *AIP Chat* panel that can route to any of the 9 agents
- Slash commands: `/isr`, `/strategy`, `/tactics`, `/effects`, `/pattern`, `/tasking`, `/battlespace`, `/sitrep`, `/audit`
- Free-text routing via `synthesis_query_agent.py` (already exists) which classifies the question and dispatches
- Every agent response renders in the chat with structured cards (not raw JSON) — link types `MENTIONS_TARGET`, `MENTIONS_ASSET`, `RECOMMENDS_COA` so chat content is clickable

#### 2.2 Activity timeline / pattern of life
- New panel `src/frontend-react/src/panels/ActivityTimeline.tsx`
- Per target: chronological band of detection events (sensor type + confidence), state transitions, COA history, BDA outcomes
- Reads from `kill_chain_tracker.py` + `audit_trail.py` (both already populated, currently invisible)
- Link from any TargetCard's "history" affordance

#### 2.3 Per-task model selection
- Extend `LLMAdapter.complete` and `complete_structured` to accept an explicit `model_hint` *and* a `provider_pref` parameter — UI surfaces a model picker per agent (default = "auto")
- New panel `src/frontend-react/src/components/ModelHubBadge.tsx` — header chip showing `gemini-2.0-flash · ANT-fallback · OL-tertiary` so the operator sees which provider answered
- "Why this model" tooltip explains the routing decision

#### 2.4 Sensor-to-shooter SLA dashboard
- New panel `src/frontend-react/src/panels/SLADashboard.tsx`
- Six histograms (one per F2T2EA stage) sourced from existing `metrics.py` Prometheus output
- Live KPI cards: median F-to-A time, p95 verification time, p99 nomination-to-authorise time
- Threshold alerts (configurable) flag SLA breach via `intel_feed.py` CRITICAL channel

#### 2.5 Multi-INT ingest mocks
- New module `src/python/vision/multi_int_simulator.py` — synthesises plausible SAR / SIGINT / MTI streams alongside the existing EO video
- Each INT stream tagged with realistic provenance (`source_kind="ICEYE-X-band"`, `source_kind="SIGINT-RFEMITTER-S-band"`)
- Frontend per-INT toggles (Phase 1) finally have real per-INT data behind them

### Phase 3 — Ontology and Effects (P2, 2–3 weeks)

#### 3.1 Real ontology layer
- Refactor `schemas/ontology.py` from a flat Pydantic file into a true ontology:
  - **Object types**: UAV, Target, Sensor, Munition, Effector, Theater, Mission, Engagement
  - **Link types**: `UAV-tracks-Target`, `Sensor-contributes-to-Target`, `Effector-engages-Target`, `Engagement-results-in-BDA`
  - **Action types**: `nominate(Target)`, `authorize(COA)`, `engage(Target, Munition)`, `retask(Sensor, AOI)`
  - **Dynamic security**: per-property classification tags
- Backed by SQLite for provenance / object history (the existing `persistence.py` already gives us SQLite — extend its schema)
- Single `OntologyService` class in `src/python/ontology_service.py` becomes the source of truth all panels and agents bind against

#### 3.2 Mock effector endpoints
- New module `src/python/effectors/` with submodules `afatds_stub.py`, `jreap_stub.py`, `jadocs_stub.py`, `amps_stub.py`
- Each accepts a realistic message schema, logs the simulated dispatch, returns acknowledgement payload
- `effectors_agent.py` (already exists, currently produces synthetic engagement) routes through these so the demo shows "fire mission transmitted to AFATDS at 14:22:03Z, ack received 14:22:03.4Z"

#### 3.3 Classification tiering
- Object-level classification tags (`UNCLASS`, `CUI`, `SECRET-NF`)
- WebSocket broadcast filters by client-token classification (extends existing `intel_feed.py` subscription model)
- Frontend dims / hides higher-classification fields per logged-in role
- Demo mode: switch between operator personas to show the same map filtered three ways

#### 3.4 Plug-in agent registry
- `src/python/agents/registry.py` — declarative agent registration (`@register_agent("synthesis_query")`)
- New agents drop into `src/python/agents/<name>.py` and appear in the AIP chat panel automatically with no UI code change

### Phase 4 — Production realism (P3, when needed)

These are the things that turn a great demo into something a defence buyer would deploy. Don't do them unless someone is paying.

- Apollo-equivalent disconnected/edge deployment (offline checkpoint → sync flow)
- TITAN-equivalent hardware bring-up (rugged-laptop reference image, low-bandwidth comms profile)
- DISA IL-5/IL-6 hardening (FIPS-140, FedRAMP High posture)
- Horizontal scaling under WebSocket load test
- AsyncAPI spec versioning + backward-compat tests
- Real DEM/satellite tiles for Romania theater (replace Swiss-Alps backdrop in `pyrender_bridge.py`)

## Sequencing notes

**Critical path through Phase 1:** Target Workbench (1.1) → Stable-ID Detection Layer (1.2) → Asset Tasking Drawer (1.4). Items 1.3 and 1.5 can land in parallel.

**Don't start Phase 2 before Phase 1.** The chat panel and timeline both *consume* the target stable IDs and column states from Phase 1. Building them first creates rework.

**Ontology refactor (Phase 3.1) is the single biggest internal change.** It will touch every agent. Plan for ~3 days of integration churn after the merge — sequence tests can pre-run the new ontology schema in CI before flipping the switch.

## What we already have that Maven doesn't have to

This list matters for differentiation pitches:

- **Explicit 4-state verification machine** with per-target-type thresholds (`verification_engine.py:6-32`). Maven blends classify+verify; we surface them.
- **Hungarian-algorithm swarm assignment** (`hungarian_swarm.py`). Maven uses heuristic asset tasking.
- **Battlespace assessment** with threat clusters, coverage gaps, movement corridors as a single immutable result (`battlespace_assessment.py:111-117`). Maven shows raw intel; we show *assessed* intel.
- **6 named map modes** with keyboard shortcuts 1–6 (`MapModeBar.tsx:7-12`).
- **NVIS / colorblind / shape-redundancy accessibility** modes (`CLAUDE.md` accessibility section).
- **F2T2EA Kill Chain Ribbon** persistent across the top of every workspace (`KillChainRibbon`).
- **NVIDIA-free 3D renderer** wired to live `SimulationModel` (`vision/pyrender_bridge.py`) — runs on a 2015 Intel MacBook Air with no CUDA.
- **1847-test coverage** with property-based tests (`test_verification_property.py`) and Hypothesis. Defence software notoriously under-tested.

## Files this blueprint will create / modify

```
src/frontend-react/src/panels/TargetWorkbench.tsx                     [NEW, P0]
src/frontend-react/src/panels/AssetTaskingDrawer.tsx                  [NEW, P0]
src/frontend-react/src/panels/ActivityTimeline.tsx                    [NEW, P1]
src/frontend-react/src/panels/SLADashboard.tsx                        [NEW, P1]
src/frontend-react/src/cesium/useCesiumDetectionLayer.ts              [NEW, P0]
src/frontend-react/src/overlays/IntelLayerPanel.tsx                   [NEW, P0]
src/frontend-react/src/overlays/AIPChatPanel.tsx                      [NEW, P1]
src/frontend-react/src/components/ModelHubBadge.tsx                   [NEW, P1]
src/frontend-react/src/overlays/ClassificationBanner.tsx              [NEW, P0]
src/frontend-react/src/components/VerticalTaskbar.tsx                 [PORT from grid-sentinel-2, P0]
src/python/ontology_service.py                                        [NEW, P2]
src/python/agents/registry.py                                         [NEW, P2]
src/python/effectors/{afatds,jreap,jadocs,amps}_stub.py               [NEW, P2]
src/python/vision/multi_int_simulator.py                              [NEW, P1]
src/python/schemas/ontology.py                                        [REFACTOR, P2]
src/python/api_main.py                                                [extend WS handlers for new actions]
src/python/sim_engine.py                                              [emit per-INT contribution events]
docs/SCREEN_PARITY_AUDIT.md                                           [NEW Phase 1 deliverable: side-by-side screenshots]
```

## Estimated effort

| Phase | Wall-clock | Backend churn | Frontend churn |
|---|---|---|---|
| 1 — Operator surface parity | 2 weeks | low (mostly UI) | high (5 new panels + chrome) |
| 2 — Decision loop depth | 2 weeks | medium (multi-INT mocks, model hint) | medium (chat + timeline + SLA) |
| 3 — Ontology and effects | 2–3 weeks | high (ontology refactor + effectors) | low (panels rebind to new types) |
| 4 — Production realism | as needed | very high | low |

## Test discipline

Every phase keeps the existing 1847-test floor green and adds new tests:

- Phase 1 — Playwright visual-regression tests for each new panel; goldens in `tests/screenshots/`
- Phase 2 — agent routing tests confirm `/sitrep` actually invokes `synthesis_query_agent`; latency-histogram tests confirm metrics flow end-to-end
- Phase 3 — ontology migration tests, effector ack-roundtrip tests, classification-filter tests proving SECRET-only fields don't leak to OBSERVER tokens

## Pitfalls to avoid

- **Don't replace Cesium.** It's already the right primitive — the same one Maven and most defence dashboards use. The work is in *how* we render onto it, not what we render with.
- **Don't reach for a real Foundry or Gotham SDK clone.** The point is to be *visually and conceptually* indistinguishable from the operator's perspective, not to re-implement Palantir's platform. Fake it convincingly.
- **Don't build effectors for real.** Mock them. The realism is in the message schemas and timing, not in actually controlling munitions. (Obvious but worth saying.)
- **Don't break the 2015-Mac compatibility.** The pyrender bridge is a competitive advantage *because* it runs without CUDA. Any new vision feature must pass `--cpu`-style fallback tests.
