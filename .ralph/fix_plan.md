---
tags: [grid_sentinel, ralph]
---
# Ralph Fix Plan — Beyond-Maven push

Maven-parity wave 1 (`2e9b4c2`) and wave 2 wiring (`ba05357`) are landed:
ClassificationBanner, TargetWorkbench, stable-ID detection layer, IntelLayerPanel,
AssetTaskingDrawer, AIPChatPanel, ModelHubBadge, VerticalTaskbar,
ActivityTimeline, SLADashboard, agent registry, multi-INT simulator,
AFATDS/JREAP/JADOCS/AMPS effector stubs, WebSocket→DOM event bridge, per-INT
filter consumed by Cesium. Test floor: 1860 passed, 6 skipped.

**Mission:** exceed Maven in every functionality. Pick one task per loop.
Search first — the codebase has more than you'd guess.

---

## P0 — Replace agent heuristics with real LLM-driven agents

The 9 agents in `src/python/agents/registry.py` ship with heuristic baseline
handlers so the AIPChatPanel works out of the box. Each one needs to graduate
to a real `LLMAdapter`-driven implementation that consults
`schemas/ontology.py` for typed I/O. Test gate: existing heuristic test must
keep passing as the fallback (LLM unavailable).

- [ ] Wire `agents/isr_observer.py` to `LLMAdapter.complete_structured` for
      cross-INT track correlation. Keep the existing heuristic as fallback.
      Update `agents/registry.py::_isr_observer` to delegate to the real
      agent when sim+adapter are available.
- [ ] Wire `agents/strategy_analyst.py` similarly — ROE evaluation +
      priority scoring through LLM with schema validation.
- [ ] Wire `agents/tactical_planner.py` — multi-COA generation. The agent
      already exists; replace the registry stub with the real call.
- [ ] Wire `agents/pattern_analyzer.py` — activity-window analysis from
      target.position_history. Surface result as a `PatternFinding` dataclass.
- [ ] Wire `agents/battlespace_manager.py` — threat-ring + map-layer tasking.
- [ ] Wire `agents/synthesis_query_agent.py` — already most-developed; just
      delete the heuristic stub once the real agent's schema validates.
- [ ] Wire `agents/performance_auditor.py` — has skeleton; route via registry.

## P0 — Real activity-history backend (replace synthetic events)

`websocket_handlers._handle_get_target_history` synthesises events. Replace
with real reads.

- [ ] Add `audit_log.events_for_target(target_id, since_ms=None)` returning
      a sorted list of `{timestamp_ms, kind, label, detail, source}`.
- [ ] Update `_handle_get_target_history` to query `audit_log` first, only
      synthesising the "current state" sentinel as a fallback.
- [ ] Hook `verification_engine` state transitions into `audit_log` so each
      DETECTED→CLASSIFIED→VERIFIED→NOMINATED step is persisted.
- [ ] Hook `effectors_agent.execute_engagement` so engagement + effector_ack
      ride into `audit_log` as ENGAGEMENT/BDA events.

## P0 — Real SLA metrics from sim_engine

`_handle_get_sla_snapshot` produces synthetic samples. The real metrics live
in `metrics.py` (Prometheus histograms).

- [ ] Add `metrics.sla_snapshot()` returning per-stage `{median_ms, p95_ms,
      p99_ms, samples, threshold_ms}` from existing histogram buckets.
- [ ] Update the WebSocket handler to call it; keep synthesiser as fallback
      when buckets are empty.
- [ ] Wire `kill_chain_tracker` state-transition timing into the histograms
      so F2T2EA stage latency becomes observable end-to-end.

## P0 — Per-task LLM model selection

`LLMAdapter.complete()` already takes a `model_hint` ("fast"/"reasoning"/
"default"). Wire it into agents and the UI.

- [ ] Add a `model_hint` parameter to `agents/registry.AgentHandler` so each
      handler can request its preferred tier (tactical_planner=reasoning,
      synthesis_query_agent=fast).
- [ ] Extend `_handle_agent_query` to read `payload.get("model_hint")` and
      pass through.
- [ ] Add a model-tier picker dropdown in `AIPChatPanel.tsx` (auto / fast /
      reasoning) wired to `model_hint` on send.
- [ ] Update `ModelHubBadge` to show *which tier* answered the most recent
      query (e.g. "gemini-2.5-pro · reasoning").

## P0 — pyrender as a real SIMULATOR client

`vision/pyrender_bridge.py` renders SimulationModel state but isn't a
WebSocket client yet. Make it stream MJPEG into api_main like
`video_simulator.py` does.

- [ ] New `src/python/vision/pyrender_simulator.py` that wraps
      `GridSentinelRenderer`, identifies as `SIMULATOR` via DashboardConnector,
      requests state broadcasts, renders from drone[0]'s POV, encodes color
      as JPEG, streams as `DRONE_FEED` per drone at 5 Hz.
- [ ] Add a `--3d` flag to `grid-sentinel.sh` that launches it instead of
      (or alongside) `vision/video_simulator.py`.
- [ ] Make the gimbal target follow `uav.primary_target_id` so the camera
      stays on whatever the operator selected.

## P1 — Multi-classification persona switching

Maven runs one classification per deployment. We do all three at once.

- [ ] Add `classification: "UNCLASSIFIED" | "CUI" | "SECRET-NF"` to
      `schemas/ontology.py` Target / UAV / Engagement.
- [ ] Add `WS:set_persona` action that toggles the operator's clearance
      between UNCLASS / CUI / SECRET-NF; backend filters broadcast state
      accordingly.
- [ ] Update `ClassificationBanner` to read the active persona from the
      store and render with the matching color (UNCLASS green, CUI purple,
      SECRET red).
- [ ] Demo affordance: add a persona-switcher in the VerticalTaskbar bottom
      label so a stakeholder can flip personas during a screen-share and
      watch fields appear/disappear.

## P1 — Real ontology layer (Foundry/Gotham-style)

Refactor `schemas/ontology.py` from a flat Pydantic file into a real
ontology — object types + link types + action types + dynamic security.

- [ ] Add `ontology/object_types.py` with metadata for each object type
      (UAV, Target, Sensor, Munition, Effector, Theater, Mission,
      Engagement) including classification tier and audit policy.
- [ ] Add `ontology/link_types.py` with `UAV-tracks-Target`,
      `Sensor-contributes-to-Target`, `Effector-engages-Target`,
      `Engagement-results-in-BDA`, etc.
- [ ] Add `ontology/action_types.py` with `nominate(Target)`,
      `authorize(COA)`, `engage(Target, Munition)`, `retask(Sensor, AOI)`.
- [ ] Add `ontology_service.OntologyService` that exposes
      `get(object_type, id)`, `links(object_type, id, link_type)`,
      `apply(action_type, **kwargs)` and persists action audit trail.
- [ ] Migrate one agent (start with `synthesis_query_agent`) to read from
      `OntologyService` instead of `sim.targets/uavs` directly. Confirm
      tests still pass.

## P1 — Beyond-Maven differentiators

These are things Maven does *not* do that we can showcase.

- [ ] **Verification confidence sparkline.** Each TargetCard shows fused
      confidence as a static bar; add a 60-tick rolling sparkline under it
      so you can see whether confidence is climbing or decaying. Read from
      a new `target.confidence_history: deque(maxlen=60)`.
- [ ] **Swarm explainability overlay.** When a UAV is auto-tasked by
      `swarm_coordinator`, render a faint cyan line on the Cesium globe
      from UAV → assigned target with a tooltip showing the cost-matrix
      score and the alternatives that lost. Reuses `useCesiumSwarmLines`.
- [ ] **ROE clause attribution.** When an engagement is rejected by
      `roe_engine`, the ActivityTimeline event must cite the specific
      clause (e.g. "ROE-3.2.1: PID required for SAM strike") not just
      "rejected".
- [ ] **Decision replay.** Add a `DecisionReplayPanel` that takes any
      AUTHORIZED engagement from `audit_log` and re-runs `effectors_agent`
      with the same RNG seed for postmortem analysis.
- [ ] **Reflective AI.** New agent `agents/self_critic.py` that periodically
      reviews its own COA history from `audit_log` and emits findings to
      the INTEL feed (e.g. "tactical_planner has produced 4 COAs against
      target #0042 in 90s; consider escalation").
- [ ] **Cross-theater scaling.** Add a theater dropdown that hot-swaps the
      SimulationModel theater (Romania → South China Sea → Baltic) without
      restart. Theaters already exist in `theaters/*.yaml`.

## P1 — Visual polish to exceed Maven aesthetic

Maven's UI is utilitarian. Ours can be sleeker.

- [ ] Add subtle Framer Motion entrance animations to TargetCards as they
      enter each kanban column. 120ms ease-out, no slide.
- [ ] Cesium target dots: pulse the ring when state advances (animation on
      class change). Already partially done for NOMINATED — extend to every
      transition.
- [ ] AIPChatPanel: typewriter-style render of agent responses (50ms per
      char) so streaming feels alive. Skip when content > 600 chars.
- [ ] SLADashboard: replace synthetic histograms with sparkline-on-card
      that flashes red on threshold breach.
- [ ] Dark theme contrast pass: audit Blueprint dark theme against WCAG AA;
      bump muted text from #475569 to #64748b where it fails.
- [ ] Add `src/frontend-react/src/styles/glass.css` with a glass-morphism
      utility class (`.gs-glass`) and apply to the new panels' chrome.

## P1 — Real Romania DEM / satellite tiles for pyrender backdrop

`unreal_to_isaac_target_tracking_2/no_synterra_attempt/terrain_mesh.obj` is
the Swiss Alps. Romania theater renders use it as backdrop via
`pyrender_bridge`. Replace with Romania.

- [ ] Run `build_terrain_mesh.py --lat 44.5 --lon 26.0 --dem <romania DEM>
      --sat <romania sat>` to produce a Bucharest-area terrain. Commit the
      mesh + texture under `theaters/romania/terrain/`.
- [ ] Update `pyrender_bridge` to load per-theater terrain — pick by
      `sim.theater_name`. Fall back to Swiss Alps when not present.
- [ ] Same exercise for South China Sea and Baltic when DEM data is
      available; document in `docs/THEATER_TERRAIN.md`.

## P2 — Operational depth

- [ ] **Network partition simulation.** Add a `comms_degraded_zone` config
      to theater YAML. When a UAV enters one, its detections are delayed by
      `latency_ms` and confidence damped by `degradation_factor`. Expose
      via `IntelLayerPanel` "comms" toggle.
- [ ] **Sensor failure injection.** New WebSocket action `inject_failure`
      that disables a UAV's sensor for N ticks. Useful for AAR exercises.
- [ ] **Adversary modeling.** Promote `enemy_uav.behavior` from a string to
      a Markov-chain state machine; expose to UI as a behavior badge on
      EnemyUAV cards.
- [ ] **Track-pattern detection.** Pattern_analyzer should detect known
      tactics (RF emitter convoy, SAM lurking-on-emit, etc.) and surface as
      `INTEL_FEED` events with classification.

## P2 — Production realism

- [ ] **AsyncAPI spec** in `docs/asyncapi.yaml` updated for the 6 new
      actions: `agent_query`, `get_provider_status`, `get_target_history`,
      `get_sla_snapshot`, `request_tasking_recommendations`, `set_persona`.
- [ ] **Playwright visual goldens.** Add `tests/visual/` with Playwright
      screenshots of TargetWorkbench, AssetTaskingDrawer, AIPChatPanel,
      SLADashboard at canonical sim states. CI compares against goldens.
- [ ] **Apollo-equivalent CD.** GitHub Actions matrix that builds the
      frontend, runs pytest, runs Playwright, packages a single static
      bundle. No live network.
- [ ] **DISA IL-5/6 posture audit.** New `docs/SECURITY_POSTURE.md` listing
      what we already meet (auth.py JWT, rbac.py, llm_sanitizer.py,
      tls_support.py) and what we'd need (FIPS-140 crypto, FedRAMP High
      controls).

## P3 — Stretch / weeks-of-work

- [ ] Edge-replication checkpoint sync (Apollo equivalent) — `persistence.py`
      already does SQLite checkpoints; bolt a delta-sync protocol on top.
- [ ] Horizontal scaling under load test — wire k6 or Locust to the
      WebSocket and document degradation curves.
- [ ] Multi-theater concurrent simulation in one process (one
      SimulationModel per theater + isolated WebSocket namespaces).

---

## Notes / discoveries (Ralph appends as it learns)

_(empty)_

## Completed

- [x] Maven-parity wave 1 — surface chrome, panels, agent registry, effector stubs (`2e9b4c2`)
- [x] Maven-parity wave 2 — wire panels to live data, multi-INT into sim_engine.tick(), per-INT filter, effectors_agent dispatch (`ba05357`)
- [x] Audit reports (`docs/MAVEN_RESEARCH.md`, `docs/PROFESSIONAL_LEVEL_BLUEPRINT.md`, `docs/UPGRADE_AUDIT.md`, `docs/ISAAC_SIM_AUDIT.md`)
- [x] Stage 7 LLM integration — `ai_tasking_manager.evaluate_and_retask_async` via LLMAdapter (`4d26b6f`)
- [x] pyrender pipeline + Grid-Sentinel SimulationModel bridge (`2c19a51`)
- [x] PyOpenGL pin fix for Python 3.13+ (`9d77c3a`)
