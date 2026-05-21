---
tags: [grid_sentinel, documentation]
---
# Python Module Reference (non-agent)

| Module | Purpose |
|--------|---------|
| `sim_engine.py` | Physics simulation, UAV/target/enemy UAV management |
| `verification_engine.py` | Target verification state machine |
| `sensor_fusion.py` | Multi-sensor complementary fusion |
| `sensor_model.py` | Probabilistic detection model (Pd, RCS, weather) |
| `swarm_coordinator.py` | Multi-UAV task assignment with sensor-gap detection |
| `battlespace_assessment.py` | Threat clustering, coverage gaps, zone scoring |
| `isr_priority.py` | ISR priority queue builder |
| `intel_feed.py` | Subscription-filtered event broadcast |
| `pipeline.py` | F2T2EA kill chain orchestrator |
| `hitl_manager.py` | Two-gate HITL approval system |
| `theater_loader.py` | YAML theater configuration loader |
| `llm_adapter.py` | Multi-provider LLM fallback (Gemini → Anthropic → heuristic) |
| `event_logger.py` | Async JSONL event logging with daily rotation |
| `config.py` | Pydantic-settings env var management |
| `roe_engine.py` | Rules of Engagement engine with YAML config |
| `audit_trail.py` | Tamper-evident audit logging of all decisions |
| `hungarian_swarm.py` | Hungarian algorithm optimal UAV-target assignment |
| `persistence.py` | SQLite state persistence for mission restart |
| `auth.py` | WebSocket JWT authentication and token validation |
| `explainability.py` | AI decision explainability engine for recommendations |
| `autonomy_matrix.py` | Dynamic autonomy level management (MANUAL/SUPERVISED/AUTONOMOUS) |
| `confidence_gate.py` | Confidence-based decision gating for safety |
| `override_capture.py` | Human override recording and analysis |
| `aar_engine.py` | After Action Review engine for post-mission analysis |
| `kill_chain_tracker.py` | F2T2EA kill chain state tracker (Find→Fix→Track→Target→Engage→Assess) |
| `sim_controller.py` | Simulation pause/resume/speed control |
| `weather_engine.py` | Weather effects on sensor performance (rain, fog, wind) |
| `uav_logistics.py` | Fuel/ammo/maintenance tracking and constraints |
| `terrain_model.py` | Terrain elevation and line-of-sight computation |
| `rbac.py` | Role-based access control with JWT authentication |
| `llm_sanitizer.py` | LLM prompt injection defense |
| `report_generator.py` | JSON/CSV report generation |
| `checkpoint.py` | Mission checkpoint/restore functionality |
| `scenario_engine.py` | YAML scenario scripting engine |
| `forward_sim.py` | Clone sim + project forward for COA evaluation |
| `delta_compression.py` | WebSocket delta encoding for bandwidth reduction |
| `vectorized_detection.py` | NumPy vectorized detection loop (10-50x speedup) |
| `comms_sim.py` | Communication degradation simulation (FULL/CONTESTED/DENIED) |
| `cep_model.py` | CEP-based engagement outcomes (Rayleigh miss-distance model) |
| `dbscan_clustering.py` | DBSCAN clustering with persistent IDs |
| `sensor_weighting.py` | Dynamic per-sensor fitness based on weather/time/target |
| `lost_link.py` | Per-drone lost-link behavior (LOITER/RTB/SAFE_LAND/CONTINUE) |
| `uav_kinematics.py` | 3-DOF point-mass with wind, collision avoidance, PN guidance |
| `corridor_detection.py` | Douglas-Peucker path simplification + heading consistency |
| `metrics.py` | Prometheus metrics + F2T2EA SLA tracking (stage latency histograms, snapshots) |
| `tls_support.py` | TLS/SSL certificate configuration and origin validation for WebSocket |
| `audit_log.py` | Structured audit trail (events_for_target → activity timeline, postmortem AAR) |
| `two_person_concurrence.py` | FedRAMP-High two-operator concurrence gate (5min window, kinetic auth) |

## Beyond-Maven Agent Extensions

**Per-Model Tier Selection** — Operator can override agent tier (fast/default/reasoning) per query.

**Agents leveraging OntologyService (migrations in progress)**:
| Agent | Purpose | Status |
|-------|---------|--------|
| `synthesis_query_agent` | SITREP generation via typed ontology API | Migrated (iteration 20) |
| `isr_observer` | Detection tracking (6 handlers → OntologyService) | Migrated (iteration 20) |
| `strategy_analyst`, `tactical_planner`, `effectors_agent`, `pattern_analyzer` | Kill-chain agents | Migrated (iteration 20) |

**Reflective / Replay Agents** (registered in `agents/registry.py`):
| Agent | Purpose | Invoke |
|-------|---------|--------|
| `decision_replay` | Postmortem AAR — re-run engagement logic at seed=42 on past records | `/replay` |
| `self_critic` | Scan audit_log for COA churn, repeated rejections, escalation candidates | `/critic` |

**Vision Pipeline**:
| Module | Purpose |
|--------|---------|
| `vision/pyrender_bridge.py` | 3D camera rendering from drone gimbal (connects Grid-Sentinel sim state to pyrender) |

**Broadcast Filtering**:
- `api_main.py::_filter_for_persona` — Classification-tier filtering (UNCLASSIFIED/CUI/SECRET) applied to WebSocket payloads per operator persona
