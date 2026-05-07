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

- [x] All 9 chat-handlers now route through `_ask_llm(ctx, system, user,
      model_hint, max_tokens)` with per-agent system prompts, falling back
      to the original heuristic when no LLM is reachable. Commit `6c2fc04`.
- [ ] **Future** — graduate the LangGraph-style agents themselves
      (`isr_observer.evaluate_tracks`, `strategy_analyst.evaluate_target`,
      `tactical_planner.generate_coas_llm`, etc.) to schema-validated
      LLMAdapter calls. The registry-handler bridge already does
      free-form chat; this is about the typed pipeline path.

## P0 — Real activity-history backend (replace synthetic events)

- [x] `audit_log.events_for_target(target_id, since_ms, limit)` returning
      `{timestamp, kind, label, detail, source}`. Commit `8ce96ae`.
- [x] `_handle_get_target_history` reads audit_log; current-state sentinel
      from sim still appended.
- [x] `sim_engine.tick()` audit-logs every state transition with from/to,
      target_type, fused_confidence, sensor_count.
- [x] `effectors_agent.execute_engagement` audit-logs `effector_dispatched`
      (mission_id, latency_ms, NATO message ID) and `engagement_executed`.

## P0 — Real SLA metrics from sim_engine

`_handle_get_sla_snapshot` produces synthetic samples. The real metrics live
in `metrics.py` (Prometheus histograms).

- [x] `metrics.record_stage_latency(stage, duration_ms)` + bounded ring
      buffer (240 samples/stage). Commit `2c3a96f`.
- [x] `metrics.sla_snapshot()` returns per-stage median/p95/p99 with
      SLA_THRESHOLDS_MS constants (FIND=2s … ASSESS=25s).
- [x] `_handle_get_sla_snapshot` prefers real metrics; warm-up synthesises;
      `source` field flags state.
- [x] `sim_engine.tick()` records FIND/FIX/TRACK/TARGET on verification
      transitions; `effectors_agent` records ENGAGE from ack latency.

## P0 — Per-task LLM model selection

`LLMAdapter.complete()` already takes a `model_hint` ("fast"/"reasoning"/
"default"). Wire it into agents and the UI.

- [x] Per-agent default tier set in `_ask_llm` calls (fast for ISR/pattern/
      synthesis/effectors/auditor, default for strategy/battlespace,
      reasoning for tactical/critic). Commit `92eea5c`.
- [x] `_handle_agent_query` reads `payload.model_hint` from {auto/fast/
      default/reasoning}, validates, stashes on ctx for the registry.
- [x] `AIPChatPanel.tsx` HTMLSelect dropdown above input row.
- [x] `ModelHubBadge` listens for AGENT_RESPONSE and renders the tier of
      the most-recent answer ("gemini-2.5-pro · reasoning").

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

- [x] `Persona` type (UNCLASSIFIED|CUI|SECRET) in store + WS `set_persona`
      action validates + stores on `clients[ws]["persona"]`. Commit `ca46a27`.
- [x] `ClassificationBanner` reactive to `persona` field (live colour swap,
      caveat substitution NOFORN for SECRET).
- [x] `PersonaSwitcher` in VerticalTaskbar bottom (cycles UNCLASS→CUI→SECRET).
- [ ] **Future** — actually filter outbound state-broadcast by per-client
      persona so a SECRET-only field disappears for an UNCLASS persona.
      Plumbing is in place; just needs the broadcast-side filter.

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

- [x] **Verification confidence sparkline** in TargetCard (60-tick SVG
      polyline + ▲/▼/· trend arrow). Commit `449bace`.
- [ ] **Swarm explainability overlay** on Cesium (cost-matrix tooltip).
- [x] **ROE clause attribution** — `evaluate_with_attribution` returns
      matched rule; `coa_authorized` audit-log records `roe_rule_name`;
      ActivityTimeline renders "ROE-<rule>: <decision> · COA <id>".
- [x] **Decision replay** as `decision_replay` agent + `/replay` slash-command.
      Commit `181db40`.
      AUTHORIZED engagement from `audit_log` and re-runs `effectors_agent`
      with the same RNG seed for postmortem analysis.
- [ ] **Reflective AI.** New agent `agents/self_critic.py` that periodically
      reviews its own COA history from `audit_log` and emits findings to
      the INTEL feed (e.g. "tactical_planner has produced 4 COAs against
      target #0042 in 90s; consider escalation").
- [x] **Cross-theater scaling** — `_handle_set_scenario` rebuilds the live
      SimulationModel in-place when the theater changes; VerticalTaskbar
      File menu "Switch theater" submenu fires `SET_SCENARIO`. Commit `d673418`.
- [x] **Reflective AI** — `self_critic` agent with `/critic` slash-command.
      Detects COA churn ≥3 + repeated rejections ≥2 from audit_log.

## P1 — Visual polish to exceed Maven aesthetic

Maven's UI is utilitarian. Ours can be sleeker.

- [x] Card entrance animation (`gs-card-enter` keyframe, 140ms ease-out
      fade-up) on TargetCards. Commit `39313ca`.
- [ ] Cesium target dot ring pulse on state advance (CSS keyframe ready;
      needs JS class toggle on Target.state change).
- [ ] AIPChatPanel typewriter render for agent responses ≤600 chars.
- [ ] SLADashboard: real samples → sparkline cards that flash on breach
      (real-data path is wired in iteration 3; visual treatment pending).
- [x] Dark theme contrast pass — bumped #475569 → #64748b across all six
      Maven-parity panels.
- [x] `src/frontend-react/src/styles/glass.css` with `.gs-glass`,
      `.gs-glass-tinted`, `.gs-card-enter`, `.gs-state-pulse-ring` and
      `:root` CSS variables. Applied to TargetWorkbench, AIPChatPanel
      (tinted), AssetTaskingDrawer, ActivityTimeline, SLADashboard.

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

- [x] **AsyncAPI spec** in `docs/asyncapi.yaml` updated for all 6 new
      actions. Total messages now 52. Commit `7a6c5c6`.
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

- The codebase is dense. Search-first really matters: `audit_log.py` exists
  (not `audit_trail.py` despite the docstring); `metrics.py` already
  implements Prometheus histograms; `roe_engine.evaluate` returns enum-only
  (added `evaluate_with_attribution` for clause attribution).
- Verification state transitions in `sim_engine.tick()` are the ideal hook
  for both audit logging *and* SLA stage timing — one site, two
  observability features.
- `clients[ws]` is a free-form dict; persona / classification can ride on
  it without schema changes. Useful for future per-client filtering.
- LLM tier override via `ctx._operator_model_hint` is a clean pattern —
  agents keep their preferred tier, operator can punch through.
- `evaluate_and_retask_async` requires the operator to keep the venv up.
  Without API keys, the heuristic still answers — visible in the
  ModelHubBadge "HEURISTIC" chip.

## Completed

- [x] Maven-parity wave 1 — surface chrome, panels, agent registry, effector stubs (`2e9b4c2`)
- [x] Maven-parity wave 2 — wire panels to live data, multi-INT into sim_engine.tick(), per-INT filter, effectors_agent dispatch (`ba05357`)
- [x] Audit reports (`docs/MAVEN_RESEARCH.md`, `docs/PROFESSIONAL_LEVEL_BLUEPRINT.md`, `docs/UPGRADE_AUDIT.md`, `docs/ISAAC_SIM_AUDIT.md`)
- [x] Stage 7 LLM integration — `ai_tasking_manager.evaluate_and_retask_async` via LLMAdapter (`4d26b6f`)
- [x] pyrender pipeline + Grid-Sentinel SimulationModel bridge (`2c19a51`)
- [x] PyOpenGL pin fix for Python 3.13+ (`9d77c3a`)
- [x] **Beyond-Maven push, iterations 1-16:**
  - i1 `6c2fc04` — registry → LLMAdapter routing with heuristic fallback
  - i2 `8ce96ae` — real activity-history (audit_log.events_for_target + sim_engine + effectors hooks)
  - i3 `2c3a96f` — real SLA metrics (record_stage_latency + sla_snapshot + sim hooks)
  - i4 `92eea5c` — per-task LLM model tier picker (UI + backend)
  - i5 `ca46a27` — multi-classification persona switching
  - i6 `449bace` — confidence sparkline + ROE clause attribution
  - i7 `39313ca` — visual polish (glass.css, card-enter, WCAG AA)
  - i8 `d673418` — cross-theater hot-swap + reflective AI agent
  - i9 `181db40` — decision_replay agent for postmortem AAR
  - i10 `7a6c5c6` — AsyncAPI + CLAUDE.md sync
  - i11 `1ba9c5d` — fix_plan close-out + learnings log
  - i12 `f8e7783` — pulse on state advance + typewriter chat + swarm cost-matrix attribution
  - i13 `a6f39e9` — per-persona broadcast filter (UNCLASS drops CUI+SECRET fields)
  - i14 `6200858` — Foundry/Gotham-style ontology layer (object_types + link_types + action_types + OntologyService)
  - i15 `d3a1b0e` — CI matrix (py 3.11/3.12/3.13 + frontend build + contracts gate) + DISA IL-5/6 posture audit
  - i16 `a1a2715` — synthesis_query_agent migrated to OntologyService (first agent off direct sim access)
- Test floor risen from 1860 → 1897 over the push. 0 regressions.

## Outstanding (highest leverage first, smallest blast radius first)

- [ ] Cesium swarm-line tooltip showing the cost-matrix explanation
      (backend serializes the data already; frontend just needs the
      hover render).
- [ ] Migrate the next agent off direct sim access — `pattern_analyzer`
      is the cleanest target since it already takes a sector argument.
- [ ] Real Romania DEM tiles for the pyrender bridge (one shell command +
      checkin per theater).
- [ ] Two-person concurrence on AUTONOMOUS engagement (closes the
      FedRAMP High gap from `docs/SECURITY_POSTURE.md`).
- [ ] `pip-audit` / `npm audit --audit-level high` / `trivy fs` jobs in
      `.github/workflows/test.yml`.
- [ ] Playwright visual regression goldens for TargetWorkbench /
      AssetTaskingDrawer / AIPChatPanel / SLADashboard.
- [ ] Edge-replication checkpoint sync (Apollo equivalent) — defer to a
      funded round.
