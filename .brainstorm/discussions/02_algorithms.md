# 02 — Algorithm & Fidelity Analysis

## 20 Algorithms Documented

### Fidelity Gap Summary (Priority Ranked)

| Priority | Area | Current | Gap | Next Level |
|----------|------|---------|-----|-----------|
| HIGH | Sensor detection | `(range/max_range)²` proxy | Not radar range eq. Pd too generous at range | Proper `SNR ∝ P_t G² λ² σ / R⁴` (Nathanson) |
| HIGH | ISR observer | No track correlation in heuristic | Duplicate tracks, inflated counts | GNN data association + Kalman filter |
| HIGH | Effectors | Binary hit/miss, 70/30 split | No CEP, no warhead model | JMEMs tables, Gaussian miss distance |
| HIGH | Verification | Hand-tuned thresholds | Not empirically grounded | Bayesian belief state per target |
| MEDIUM | Sensor fusion | `1-∏(1-ci)` independence | Overestimates when sensors correlated | Dempster-Shafer or covariance intersection |
| MEDIUM | Swarm coordinator | Greedy, every 5s | Suboptimal assignment | Hungarian algorithm or auction |
| MEDIUM | Target behavior | Shoot-and-scoot teleports | Breaks tracking continuity | Road-network patrol, BDI agents |
| MEDIUM | Zone balancer | Proportional controller | Oscillation, ignores threats | MPC with threat-weighted zones |
| LOW | UAV kinematics | 2D, empirical orbit mixing | No wind, collision avoidance | 3-DOF point-mass + PN guidance |
| LOW | Corridor detection | Total displacement only | Patrol loops flagged as corridors | Douglas-Peucker + Hough transform |
| LOW | Threat clustering | Anchor-based single-pass | Not DBSCAN, edge artifacts | DBSCAN/OPTICS + persistent IDs |

### Key Algorithm Details

**1. Sensor Detection (sensor_model.py):** Sigmoid-squashed SNR proxy. Range term `1-(r/r_max)²`, RCS aspect modulation `0.3+1.2sin²(θ)`, weather penalty. No terrain masking, no 1/R⁴, no clutter model. 36 unit tests.

**2. Sensor Fusion (sensor_fusion.py):** Complementary `1-∏(1-ci)` with max-within-type dedup. Pure functions, frozen dataclasses. No temporal decay, no disagreement handling. 13 tests.

**3. Verification Engine (verification_engine.py):** Linear state chain DETECTED→CLASSIFIED→VERIFIED with per-type thresholds and regression timeouts. DEMO_FAST halves times. Pure function O(1). 27 tests.

**4. UAV Physics (sim_engine.py):** 2D geographic coordinates, MAX_TURN_RATE 3°/s, blended tangential/radial orbit tracking (0.3/0.7 mixing), INTERCEPT at 1.5× speed. No collision avoidance, RTB is placeholder. No dedicated tests.

**5. Target Behavior (sim_engine.py):** 4 archetypes — stationary, shoot-and-scoot (teleport), patrol (random waypoints), ambush (flee on proximity). Emit toggle 0.5%/tick. No formation, no doctrine. No specific tests.

**6. Swarm Coordinator (swarm_coordinator.py):** Greedy assignment O(T×gaps×U) every 50 ticks. Priority = threat_weight × (1-confidence). Sensor gap detection. 120s task expiry. Idle floor = 2. 13 tests.

**7. Battlespace Assessment (battlespace_assessment.py):** Anchor-based clustering with Jarvis march convex hull. Coverage gaps = zones with 0 UAVs. Zone scoring = additive confidence. Corridor detection = displacement threshold. All threaded. 21 tests.

**8. ISR Priority (isr_priority.py):** urgency = threat_w × verification_gap × (0.5 + 0.5×time_factor). Top 3 IDLE UAVs with missing sensor types. 31 tests.

**9. Strategy Analyst (agents/):** Heuristic: lookup priority by type, NOMINATE if ≥7. Always roe_compliant=True. LLM: full prompt with target JSON.

**10. Tactical Planner (agents/):** 3 COAs (fastest/highest-Pk/lowest-cost). Composite = 0.4×Pk + 0.3/time + 0.3/risk. Haversine distance. ZERO tests.

**11. Effectors (agents/):** modified_Pk = base + state_bonus. Binary roll. 70/30 DESTROYED/DAMAGED. BDA confidence hardcoded. 27 tests.

**12. Demo Autopilot (api_main.py):** Fixed 5/4/5s delays. Auto-approve all PENDING. Select coas[0]. Enemy intercept at confidence>0.7. ZERO tests.

**13. Sim Main Loop (sim_engine.py tick()):** 14-step fixed-timestep at 10Hz. Detection O(U×T×S) brute force. Wall-clock dt capped at 0.1s. Confidence fade 0.95×/tick.

### Algorithms With Zero Tests
- UAV kinematics / orbit tracking
- Target behavior models
- Demo autopilot loop
- Tactical planner COA generation (442 lines)
- F2T2EA pipeline orchestration
- Zone-grid macro-flow balancer
