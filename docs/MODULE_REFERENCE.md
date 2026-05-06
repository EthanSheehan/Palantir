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
| `metrics.py` | Prometheus text format metrics endpoint (`/metrics`) |
| `tls_support.py` | TLS/SSL certificate configuration and origin validation for WebSocket |
