# Library & Integration Candidates for Palantir C2

**Scout**: Library & Integration Scout
**Date**: 2026-03-20
**Scope**: 25 candidates across 10 categories

---

## Summary

This document catalogs library candidates that could meaningfully enhance Palantir's capabilities across its four subsystems: FastAPI backend, React+Cesium frontend, LangGraph AI agents, and drone swarm simulation. Each entry includes integration effort (S=days, M=1-2 weeks, L=sprint+), license, and GitHub stars as a proxy for community health.

---

## 1. Geospatial / GIS

### 1.1 Turf.js
- **What it does**: Modular geospatial analysis in JavaScript — distances, bearings, buffering, intersections, Voronoi diagrams, route planning, isochrones.
- **Palantir fit**: Replaces hand-rolled geometry math in the frontend. Calculate coverage buffers around drones, compute shortest-path corridors for strike routing, generate threat ring polygons client-side without roundtripping to backend.
- **Integration effort**: S — drop into the React frontend as an npm package, call from Cesium entity hooks.
- **License**: MIT
- **Stars**: ~10,300

### 1.2 deck.gl
- **What it does**: WebGL2-accelerated visualization framework for large geospatial datasets — heatmaps, arc layers, scatter plots, hexagon aggregations, all GPU-rendered.
- **Palantir fit**: Cesium handles 3D globe; deck.gl adds 2D analytical overlays (density heatmaps of target activity, arc layers for comm links between drones, hexbin aggregation of threat events). Can run alongside Cesium via the `@deck.gl/cesium` integration layer.
- **Integration effort**: M — requires Cesium scene integration, new LayerPanel entries, TypeScript type wiring.
- **License**: MIT
- **Stars**: ~14,000

### 1.3 H3-js
- **What it does**: Uber's hexagonal geospatial indexing system. Assigns any lat/lon to a hex cell at configurable resolution. Enables efficient spatial queries, clustering, and coverage reporting.
- **Palantir fit**: Replace the current grid-zone system with H3 hex cells. Zone threat scoring, coverage gap detection, and swarm assignment can all use H3 indexing — giving consistent polygon shapes and efficient neighbor lookups. Also enables "area denial" zones as H3 compact sets.
- **Integration effort**: M — requires refactoring `battlespace_assessment.py` zone model and frontend `GridControls`.
- **License**: Apache-2.0
- **Stars**: ~1,030

### 1.4 Shapely (Python)
- **What it does**: Python library for manipulation and analysis of geometric objects (points, lines, polygons). Provides spatial predicates (contains, intersects, within), buffering, union/difference, convex hull.
- **Palantir fit**: Backend geometry for exclusion zones, no-fly corridors, engagement envelopes. Currently the backend does manual math for zone intersection; Shapely makes this declarative and correct. Also useful for sensor footprint modeling.
- **Integration effort**: S — pure Python, pip install. Slot into `sim_engine.py` and `battlespace_assessment.py`.
- **License**: BSD-3-Clause
- **Stars**: ~4,400

### 1.5 GeoPandas (Python)
- **What it does**: Extends Pandas with geospatial operations. Reads/writes GeoJSON, Shapefile, GeoPackage. Enables spatial joins, dissolves, and coordinate projections at dataframe scale.
- **Palantir fit**: Theater configuration and batch analytics. Load terrain data as GeoDataFrames, perform bulk spatial queries on target histories, export mission-debriefing shapefiles. Pairs with Shapely.
- **Integration effort**: M — adds a heavier dependency chain (GDAL). Most useful for offline analysis and theater-loader enhancements rather than the hot path.
- **License**: BSD-3-Clause
- **Stars**: ~5,100

---

## 2. Simulation

### 2.1 SimPy
- **What it does**: Process-based discrete-event simulation framework for Python. Models resources, queues, timeouts, and concurrent processes using generators.
- **Palantir fit**: Replace the current 10Hz asyncio loop with a proper DES engine for offline scenario replay, after-action review, and Monte Carlo analysis of engagement outcomes. Run thousands of simulation ticks offline to stress-test swarm coordinator logic without the WebSocket layer.
- **Integration effort**: M — parallel implementation alongside live `sim_engine.py`. The live sim stays async; SimPy powers batch/replay mode.
- **License**: MIT (via PyPI)
- **Stars**: N/A (hosted on GitLab; ~1,600 stars equivalent)

### 2.2 Mesa
- **What it does**: Agent-based modeling framework for Python. Provides a scheduler, grid environments, agent step() methods, and built-in data collection. Used widely in academic ABM research.
- **Palantir fit**: Prototype adversarial behaviors for enemy UAVs (RECON, ATTACK, JAMMING, EVADING). Mesa's agent model maps cleanly onto Palantir's UAV mode state machine. Also useful for testing swarm emergent behaviors in isolation before integrating with the live sim.
- **Integration effort**: M — standalone Mesa simulation that mirrors `sim_engine.py` logic for research/testing purposes.
- **License**: Apache-2.0
- **Stars**: ~3,500

### 2.3 Gymnasium / PettingZoo
- **What it does**: Gymnasium is the standard single-agent RL environment API (successor to OpenAI Gym). PettingZoo extends this to multi-agent environments with the AECEnv and ParallelEnv interfaces.
- **Palantir fit**: Wrap the Palantir simulation as a PettingZoo environment to train autonomous swarm coordination policies via reinforcement learning. Each drone is an agent; the observation space is sensor fusion state; the action space maps to existing WebSocket commands. Enables training a policy that outperforms the current greedy `swarm_coordinator.py`.
- **Integration effort**: L — wrapping the sim as a PettingZoo env requires careful observation/action space design, reward shaping, and decoupling from WebSocket. High payoff for autopilot autonomy.
- **License**: MIT (Gymnasium), NOASSERTION/MIT (PettingZoo)
- **Stars**: ~11,600 (Gymnasium), ~3,400 (PettingZoo)

---

## 3. Sensor Fusion

### 3.1 FilterPy
- **What it does**: Python Kalman filtering library. Implements standard KF, Extended KF, Unscented KF, particle filters, H-infinity filter, and smoothers.
- **Palantir fit**: Replace the current `1 - ∏(1-ci)` complementary fusion formula with proper Kalman-based track fusion. Fuse position estimates from EO/IR, SAR, and SIGINT sensors into a single best-estimate track with uncertainty bounds. Directly upgrades `sensor_fusion.py`. UKF handles the nonlinear sensor models naturally.
- **Integration effort**: M — refactor `sensor_fusion.py` to maintain per-target KF state. The `FusionResult` dataclass gains a covariance field. Existing tests will need updates.
- **License**: MIT
- **Stars**: ~3,800

### 3.2 Stone Soup
- **What it does**: UK DSTL-developed target tracking framework. Provides detectors, data associators (GNN, JPDA, MHT), initiators, deleters, and a track manager pipeline. Built for multi-target tracking in defence applications.
- **Palantir fit**: This is the closest off-the-shelf system to what Palantir's verification engine is trying to be. Stone Soup's Track → Detection association directly maps to Palantir's target state machine. Its JPDA (Joint Probabilistic Data Association) handles the multiple-sensor-to-multiple-target ambiguity that the current system resolves heuristically. High strategic value for the sensor fusion subsystem.
- **Integration effort**: L — significant refactor of `verification_engine.py` and `sensor_fusion.py`. Worth evaluating as a phased migration.
- **License**: MIT
- **Stars**: ~570

### 3.3 SciPy (Signal Processing)
- **What it does**: `scipy.signal` provides digital filters, FFT, convolution, and spectral analysis. `scipy.spatial` provides KD-trees, Delaunay triangulation, and spatial data structures.
- **Palantir fit**: Two immediate uses: (1) `scipy.signal` for processing raw SIGINT RF data in the SigintDisplay — apply bandpass filters, compute spectrograms, detect emitter peaks. (2) `scipy.spatial.KDTree` for O(log n) nearest-neighbor queries in target clustering, replacing the current O(n²) threat cluster loop in `battlespace_assessment.py`.
- **Integration effort**: S — already likely transitively present via numpy. Direct import and use in hot paths.
- **License**: BSD-3-Clause
- **Stars**: ~14,600

---

## 4. AI / Multi-Agent Frameworks

### 4.1 CrewAI
- **What it does**: Framework for orchestrating role-playing autonomous AI agents. Defines Agents with roles, goals, and backstories; Tasks with descriptions and expected output; Crews that execute task graphs.
- **Palantir fit**: The nine LangGraph/LangChain agents could be expressed as a CrewAI crew, potentially with simpler wiring. More practically, CrewAI's human-in-the-loop callbacks align with Palantir's two-gate HITL system. Evaluate as an alternative orchestration layer for the kill chain pipeline if LangGraph proves brittle.
- **Integration effort**: L — full rewrite of `pipeline.py` and the nine agent modules. Evaluate as a parallel prototype, not a drop-in.
- **License**: MIT
- **Stars**: ~46,700

### 4.2 AutoGen (Microsoft)
- **What it does**: Multi-agent conversation framework. Agents exchange messages, tools are registered per-agent, and complex multi-step tasks emerge from agent dialogue. Supports human-in-the-loop via `UserProxyAgent`.
- **Palantir fit**: AutoGen's `UserProxyAgent` is architecturally similar to Palantir's HITL manager — it can pause agent execution and wait for human approval. Also useful for the `synthesis_query_agent.py` — AutoGen's conversational multi-agent pattern handles ambiguous NL queries better than single-shot chains.
- **Integration effort**: M — targeted integration for specific agents (HITL, synthesis query) rather than full replacement. AutoGen v0.4+ (the "agentchat" API) is stable.
- **License**: CC-BY-4.0 (docs) / MIT (code)
- **Stars**: ~55,900

### 4.3 smolagents (HuggingFace)
- **What it does**: Minimal agent library where agents think and act in Python code rather than JSON. Tight HuggingFace model integration, multi-step tool use, very low overhead.
- **Palantir fit**: `llm_adapter.py` already has a Gemini → Anthropic → heuristic fallback chain. smolagents could slot in as a lightweight local-model path (running on-device Qwen or Llama via HuggingFace) when API keys are unavailable — enabling fully air-gapped operation.
- **Integration effort**: M — add as a fourth fallback tier in `llm_adapter.py` with a local model download step.
- **License**: Apache-2.0
- **Stars**: ~26,200

---

## 5. Real-Time Messaging & State Persistence

### 5.1 Valkey / Redis (via redis-py)
- **What it does**: Valkey is the BSD-licensed Redis fork maintained by the Linux Foundation. redis-py is the Python client. Together they provide sub-millisecond key-value storage, pub/sub messaging, sorted sets, streams (Kafka-lite), and persistence.
- **Palantir fit**: The current architecture holds all simulation state in-memory in `api_main.py`. Redis/Valkey solves three problems: (1) state persistence across backend restarts without losing track history, (2) horizontal scaling — multiple backend instances sharing state, (3) pub/sub to replace the manual `intel_feed.py` broadcast with a proper channel system. The WebSocket layer subscribes to Redis channels rather than polling Python objects.
- **Integration effort**: M — requires running Redis/Valkey as a sidecar service, refactoring `SimulationModel` state to be Redis-backed, and updating `intel_feed.py` to use pub/sub channels.
- **License**: NOASSERTION (Valkey — BSD-3), MIT (redis-py)
- **Stars**: ~25,200 (Valkey), ~13,500 (redis-py)

### 5.2 paho-mqtt
- **What it does**: Python MQTT client implementing the MQTT 3.1/5.0 pub/sub protocol. Lightweight, designed for IoT/edge devices with unreliable connectivity.
- **Palantir fit**: Real drone integration path. When connecting actual UAV hardware, MQTT is the dominant telemetry protocol (used by ArduPilot, PX4 MAVLink bridges, DJI enterprise). paho-mqtt would let Palantir subscribe to real drone telemetry topics and publish commands — replacing the simulator WebSocket with real hardware data. Also enables a mesh topology where multiple Palantir instances share target tracks across a network.
- **Integration effort**: M — new `mqtt_bridge.py` module that translates MQTT telemetry to the internal simulation state format. Drone simulator remains for offline use.
- **License**: EPL-2.0 / EDL-1.0 (dual)
- **Stars**: ~2,400

### 5.3 kafka-python
- **What it does**: Python client for Apache Kafka. Enables high-throughput, fault-tolerant event streaming with consumer groups, offset management, and guaranteed delivery.
- **Palantir fit**: For large-scale deployments (multiple theaters, persistent mission logging), Kafka replaces the current JSONL event logger with a durable, replayable event stream. Every simulation tick becomes a Kafka message; analysts can replay any mission from its Kafka offset. Also enables real-time analytics pipelines on top of mission data.
- **Integration effort**: L — requires Kafka infrastructure, refactoring `event_logger.py`, and defining a schema (Avro/Protobuf). High operational overhead. Evaluate only for production deployment, not development.
- **License**: Apache-2.0
- **Stars**: ~5,900

---

## 6. Advanced Visualization

### 6.1 kepler.gl
- **What it does**: Uber's open-source geospatial analysis tool for large datasets. React component with GPU-rendered layers (arc, heatmap, grid, hex, trip animation), time playback, and filtering UI.
- **Palantir fit**: After-action review and mission analytics dashboard. Load a mission's JSONL event log into kepler.gl to visualize drone tracks, target movement, and engagement timelines with time scrubbing. Not for the live operational view (Cesium does that), but for the post-mission ASSESS tab.
- **Integration effort**: M — embed the `KeplerGl` React component in a new "REPLAY" tab. Feed it the parsed event log. No backend changes needed.
- **License**: MIT
- **Stars**: ~11,700

### 6.2 Plotly / Dash
- **What it does**: Plotly is an interactive graphing library (Python + JS). Dash is a Python web framework for building analytical dashboards on top of Plotly without writing JavaScript.
- **Palantir fit**: Performance Auditor agent currently generates text reports. A Dash dashboard would give it interactive charts: kill chain latency over time, sensor fusion confidence distributions, swarm efficiency metrics, HITL approval rates. Could run as a separate analytics service on a different port.
- **Integration effort**: M — standalone Dash app reading from the JSONL event log. Decoupled from the main FastAPI backend.
- **License**: MIT
- **Stars**: ~18,400 (plotly.py), ~24,500 (Dash)

---

## 7. Military / C2 Standard Protocols

### 7.1 open-dis-python
- **What it does**: Python implementation of IEEE 1278.1 Distributed Interactive Simulation (DIS) protocol v7. DIS is the NATO standard for interoperability between simulation systems — defines PDU formats for entity state, fire, detonation, designator (laser painting), and more.
- **Palantir fit**: Interoperability with other military simulation systems (VBS3, JSAF, OneSAF, AFSIM). If Palantir needs to participate in a joint exercise or integrate with an existing simulation federation, DIS is the lingua franca. The `paint_target` WebSocket action maps to DIS DesignatorPDU; `intercept_target` maps to FirePDU.
- **Integration effort**: L — requires a DIS gateway module translating internal state to PDUs and vice versa. Low priority unless joint-exercise use case is confirmed.
- **License**: BSD-2-Clause
- **Stars**: ~71 (small but it's the only Python DIS v7 implementation)

### 7.2 PyTAK (Cursor on Target)
- **What it does**: Python package for Team Awareness Kit (TAK) integration. Implements the Cursor on Target (CoT) XML protocol used by ATAK, WinTAK, and iTAK military apps. Sends/receives SA tracks, chat, files over TCP/UDP/TLS.
- **Palantir fit**: TAK is the dominant situational awareness platform used by US and allied military forces. PyTAK lets Palantir broadcast target tracks as CoT events to ATAK clients in the field — operators with Android phones see Palantir-detected targets on their ATAK map in real time. `VERIFIED` targets map to CoT `a-h-G` (hostile ground) events; drones map to `a-f-A-M-F-Q` (friendly air UAV).
- **Integration effort**: M — new `cot_bridge.py` that translates `SimulationModel` state to CoT XML and publishes via PyTAK's async writer. Enables real-world TAK ecosystem integration.
- **License**: Apache-2.0
- **Stars**: ~227 (niche but purpose-built)

### 7.3 FreeTAKServer
- **What it does**: Open-source TAK server compatible with ATAK, WinTAK, and iTAK. Handles CoT routing, chat, GeoChat, video streaming links, and data packages between TAK clients.
- **Palantir fit**: Run FreeTAKServer alongside Palantir so that ATAK field users receive Palantir tracks without needing direct network access to the Palantir backend. Palantir publishes via PyTAK → FreeTAKServer → ATAK clients. Also provides a federation protocol for connecting multiple Palantir instances.
- **Integration effort**: M — Docker sidecar deployment, configure PyTAK to point at FreeTAKServer. Pairs with PyTAK above.
- **License**: EPL-2.0
- **Stars**: ~890

---

## 8. Video / Real Drone Feeds

### 8.1 aiortc
- **What it does**: WebRTC and ORTC implementation for Python using asyncio. Implements ICE, DTLS, SRTP, and data channels. Enables peer-to-peer video/audio streaming from Python servers.
- **Palantir fit**: The current drone feed system uses base64-encoded MJPEG frames over WebSocket — high latency, high CPU overhead, no adaptive bitrate. aiortc replaces this with proper WebRTC: the video simulator (or real drone) streams H.264 via WebRTC directly to the React frontend's PIP camera panels. Sub-200ms latency, hardware encode/decode, adaptive quality. This is the architecture used by real drone GCS systems.
- **Integration effort**: L — requires replacing `video_simulator.py`'s frame-push model with a WebRTC offer/answer signaling flow, adding STUN/TURN for NAT traversal, and updating the React camera components to use RTCPeerConnection instead of WebSocket image decode.
- **License**: BSD-3-Clause
- **Stars**: ~5,000

### 8.2 mediasoup
- **What it does**: Selective Forwarding Unit (SFU) for WebRTC — routes media streams between participants without decoding/re-encoding. Node.js server with a Python client library.
- **Palantir fit**: When multiple operators need to watch the same drone feed simultaneously, mediasoup routes the stream to all subscribers without re-encoding on the Palantir backend. More scalable than aiortc for multi-operator deployments. The React frontend uses mediasoup-client to subscribe to drone streams.
- **Integration effort**: L — requires a Node.js mediasoup server process, Python signaling integration, and React client updates. Overkill for single-operator demos; justified for multi-operator production deployments.
- **License**: ISC
- **Stars**: ~7,200

---

## 9. Testing

### 9.1 Playwright
- **What it does**: Microsoft's end-to-end browser testing framework. Tests Chromium, Firefox, and WebKit with a single async API. Supports network mocking, screenshots, video recording, and tracing.
- **Palantir fit**: E2E tests for the React+Cesium frontend are currently absent. Playwright tests can validate the full stack: WebSocket connects, Cesium globe renders, drone tracks update, HITL toasts appear and can be approved/rejected, COA panels populate. Can record test traces for debugging failed CI runs.
- **Integration effort**: M — requires setting up Playwright config, writing page object models for the main tabs, and running the full stack in a CI environment (Docker compose the backend + frontend).
- **License**: Apache-2.0
- **Stars**: ~84,600

### 9.2 Locust
- **What it does**: Python load testing framework. Users define behavior as Python classes; Locust spawns thousands of simulated users and reports throughput, latency percentiles, and failure rates via a web UI.
- **Palantir fit**: Load test the FastAPI WebSocket server. Simulate 50+ simultaneous DASHBOARD clients all receiving 10Hz simulation ticks, plus multiple SIMULATOR clients pushing video frames. Identify the throughput ceiling before the backend becomes the bottleneck. Also stress-tests the intel feed subscription system.
- **Integration effort**: S — write a Locust file with WebSocket user classes, run against the backend. No code changes to the main system.
- **License**: MIT
- **Stars**: ~27,600

### 9.3 Hypothesis
- **What it does**: Property-based testing library for Python. Instead of writing specific test cases, you define properties that should always hold. Hypothesis generates thousands of inputs to find counterexamples.
- **Palantir fit**: Test invariants in the pure-function simulation modules. Examples: "sensor fusion confidence is always in [0, 1]", "verification state never regresses from VERIFIED to DETECTED without an explicit timeout", "swarm assignment never assigns a drone to two targets simultaneously". These are hard to catch with example-based tests but trivial to express as Hypothesis properties.
- **Integration effort**: S — add Hypothesis decorators to existing `pytest` test files. No production code changes.
- **License**: NOASSERTION (MPL-2.0)
- **Stars**: ~8,500

---

## 10. DevOps / Deployment

### 10.1 Docker Compose
- **What it does**: Define and run multi-container Docker applications via a single `docker-compose.yml`. Manages service dependencies, networking, volumes, and health checks.
- **Palantir fit**: Currently `palantir.sh` launches processes directly. A `docker-compose.yml` would containerize: FastAPI backend, React+Vite frontend, video simulator, (optionally) Redis/Valkey, FreeTAKServer. Single `docker compose up` starts the full stack. Enables reproducible deployments on any host with Docker installed.
- **Integration effort**: M — write Dockerfiles for Python backend and Node frontend, write `docker-compose.yml`, handle volume mounts for `.env` and event logs. The `.brainstorm` sessions suggest this was planned.
- **License**: Apache-2.0
- **Stars**: ~37,200

### 10.2 Pulumi
- **What it does**: Infrastructure as Code using real programming languages (Python, TypeScript, Go). Provisions cloud resources (EC2, ECS, S3, VPCs) and Kubernetes clusters programmatically with state management and drift detection.
- **Palantir fit**: If Palantir deploys to cloud (AWS GovCloud, Azure Government) for real-world use, Pulumi provisions the infrastructure in Python — matching the team's primary language. Define the VPC, ECS task definitions for each container, and load balancer in the same codebase as the application.
- **Integration effort**: L — requires cloud account setup, IAM configuration, and writing Pulumi stacks. Low priority until cloud deployment is needed.
- **License**: Apache-2.0
- **Stars**: ~24,900

---

## Priority Matrix

| # | Library | Category | Effort | Impact | Recommend |
|---|---------|----------|--------|--------|-----------|
| 1 | **FilterPy** | Sensor Fusion | M | High | Upgrade `sensor_fusion.py` to Kalman tracks |
| 2 | **PyTAK + FreeTAKServer** | Military/C2 | M | High | Real-world TAK ecosystem integration |
| 3 | **Turf.js** | Geospatial | S | High | Replace frontend geometry math immediately |
| 4 | **Shapely** | Geospatial | S | High | Backend zone/engagement envelope geometry |
| 5 | **Playwright** | Testing | M | High | First E2E test coverage for the frontend |
| 6 | **Hypothesis** | Testing | S | Med | Property tests for pure-function sim modules |
| 7 | **Locust** | Testing | S | Med | WebSocket load ceiling characterization |
| 8 | **Valkey/Redis** | Real-time | M | High | State persistence + proper pub/sub |
| 9 | **paho-mqtt** | Real-time | M | High | Real drone hardware integration path |
| 10 | **H3-js** | Geospatial | M | Med | Hex grid replaces current zone system |
| 11 | **Stone Soup** | Sensor Fusion | L | High | Multi-target tracking framework (DSTL) |
| 12 | **PettingZoo** | Simulation | L | High | RL training environment for swarm policy |
| 13 | **aiortc** | Video | L | Med | Real WebRTC for drone feeds |
| 14 | **deck.gl** | Visualization | M | Med | GPU heatmaps alongside Cesium |
| 15 | **kepler.gl** | Visualization | M | Med | Post-mission replay/ASSESS analytics |
| 16 | **AutoGen** | AI/ML | M | Med | HITL agent + NL query improvement |
| 17 | **smolagents** | AI/ML | M | Med | Air-gapped local model fallback |
| 18 | **Docker Compose** | DevOps | M | High | Reproducible full-stack deployment |
| 19 | **SciPy** | Sensor Fusion | S | Med | KD-tree clustering, SIGINT signal processing |
| 20 | **Mesa** | Simulation | M | Med | Adversarial enemy UAV behavior prototyping |
| 21 | **open-dis-python** | Military/C2 | L | Low | DIS interoperability (joint exercises only) |
| 22 | **CrewAI** | AI/ML | L | Low | Agent framework alternative (evaluate only) |
| 23 | **Plotly/Dash** | Visualization | M | Low | Standalone analytics dashboard |
| 24 | **mediasoup** | Video | L | Low | Multi-operator video routing (production only) |
| 25 | **Pulumi** | DevOps | L | Low | Cloud IaC (post-Docker Compose) |

---

## Quick Wins (implement this sprint)

1. **`pip install shapely`** — drop into `battlespace_assessment.py` for polygon intersection math. No API changes.
2. **`npm install @turf/turf`** — use in Cesium entity hooks for bearing calculations and buffer generation. Replaces ~200 lines of inline trig.
3. **`pip install hypothesis`** — add 10-15 property tests to `test_sensor_fusion.py` and `test_verification_engine.py`. No production changes.
4. **`pip install filterpy`** — prototype UKF track fusion in a new `test_kalman_fusion.py` before committing to refactor.

---

*All star counts as of 2026-03-20. Effort estimates assume a single engineer familiar with the Palantir codebase.*
