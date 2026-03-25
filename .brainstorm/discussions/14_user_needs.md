# User Needs Research: C2/Drone/Autonomy Systems
**Role:** User Needs Researcher
**Date:** 2026-03-20
**Scope:** Forums, GitHub issues, procurement docs, academic research on ATAK, QGroundControl, ArduPilot, PX4, JADC2, and related C2/drone/autonomy platforms

---

## Executive Summary

Across operator communities, procurement documents, and developer forums, a consistent pattern emerges: users want systems that are **transparent about what the AI is doing and why**, that give **granular, adjustable control over autonomy levels**, and that don't drown them in **cognitive overload from cluttered, disorganized interfaces**. The Palantir `/autopilot` feature lands squarely in the highest-demand territory — but only if it addresses trust calibration, explainability, and graceful failsafe behavior. Each finding below maps directly to a Palantir capability gap or opportunity.

---

## 1. C2 Operator Feature Requests (Most Frequent)

### 1.1 Intelligent Information Filtering
**Source:** TAK Product Center roadmap statements (tak.gov, 2024); RAND research on C2 situational awareness (RR2489); SAAB automated C2 systems documentation
**Pain Point:** Operators are overwhelmed by raw data from sensors, drones, and intel feeds. C2 maps are described as "cluttered beyond the needs of operators," with irrelevant information directly increasing cognitive workload and degrading mission performance.
**Frequency/Importance:** Identified as the #1 C2 challenge by RAND research and the stated priority of the TAK Product Center's next development cycle. Documented to cause "missed opportunities" and "operator fatigue."
**Palantir Address:** The `isr_priority.py` queue and `intel_feed.py` subscription model are the right architecture. The gap is exposing per-feed filter controls in the UI — operators need sliders/toggles to tune signal-to-noise in real time, not just subscribe to feed categories.

### 1.2 Collaborative Sensor Mesh / Every Node Contributes
**Source:** TAK Product Center future roadmap (civtak.org, 2024); JADC2 strategy document (DoD, 2022)
**Pain Point:** Operators want every device in the network — not just dedicated sensors — to contribute to collective intelligence. Current systems treat most nodes as consumers, not producers of sensor data.
**Frequency/Importance:** Explicitly named as a near-term TAK development priority. JADC2's entire "sense / make sense / act" framework depends on this.
**Palantir Address:** The `sensor_fusion.py` complementary fusion model supports this architecturally. Palantir could expose a sensor registration API so external feeds (phones, radios, partner drones) can contribute detections and be fused automatically.

### 1.3 Decision Speed: Seconds, Not Minutes
**Source:** CJADC2 strategy (DoD/DASD 2024); ATIS/RTI JADC2 analysis; Anduril $100M tactical data mesh award (December 2024)
**Pain Point:** Legacy C2 systems make decisions in minutes; modern threats require seconds. Sensor-to-shooter latency is the single most-cited procurement requirement in JADC2 RFPs.
**Frequency/Importance:** Congressional mandate-level priority. DoD awarded $100M specifically for low-latency tactical data mesh (Dec 2024). "Decision making in seconds vs. minutes" is the explicit stated goal.
**Palantir Address:** Palantir's 10Hz simulation loop and WebSocket architecture are already low-latency. The autopilot mode's value proposition should be framed around closing the sensor-to-decision loop autonomously when operator attention is elsewhere.

### 1.4 Multi-Level Autonomy Controls
**Source:** DoD Directive 3000.09 (2023 update); DARPA OFFSET program; academic research on "disciplined autonomy" (Small Wars Journal, Feb 2026)
**Pain Point:** Operators want a dial, not a switch. Binary MANUAL/AUTONOMOUS modes are inadequate. Users need per-asset, per-action autonomy controls — e.g., let UAV-3 autonomously FOLLOW but require human approval for PAINT.
**Frequency/Importance:** Cited in every major autonomy policy document since 2012. The 2023 Directive 3000.09 explicitly requires "appropriate levels of human judgment over the use of force." Practitioner articles (Small Wars Journal) describe "disciplined autonomy" as the operational standard.
**Palantir Address:** Palantir already has MANUAL/SUPERVISED/AUTONOMOUS plus per-drone autonomy overrides. The gap is granularity: per-action type autonomy (FOLLOW autonomously, require approval for ENGAGE) and time-bounded autonomy ("autonomous for next 10 minutes, then check in").

---

## 2. Drone Swarm Operator Pain Points

### 2.1 Cognitive Overload at Scale
**Source:** NASA cognitive walkthrough study on multi-drone delivery (AIAA 2021); PMC research on drone swarm piloting physiological data (2022); ScienceDirect interface design study (2024); SAGE journals C2 maps operator workload study (2018)
**Pain Point:** Operators reported high workload and "losing control" once managing 17+ UAVs simultaneously. "Attentional tunneling" causes operators to fixate on one asset while losing awareness of others. C2 maps are specifically called out as "overloaded with irrelevant information."
**Frequency/Importance:** Well-documented in peer-reviewed research. Consistent finding across NASA, NIH, and AIAA studies. The 17-UAV threshold is a hard empirical finding.
**Palantir Address:** The swarm coordinator handles assignment automatically. The UI gap is a dedicated "swarm health at a glance" view — one panel showing all UAVs with color-coded status, not individual cards that require scrolling. Consider a heat-ring overlay on the Cesium globe showing swarm distribution vs. coverage gaps.

### 2.2 Operator Override Rate and Trust
**Source:** Academic research on federated learning for swarm autonomy (cited 22% override rate in field trials); RAND inadvertent escalation research (2024/2025)
**Pain Point:** 22% of autonomous actions were overridden by operators in field trials, suggesting either over-triggering of autonomy or lack of operator trust in AI decisions. RAND found that autonomous system speed led to inadvertent escalation in wargames.
**Frequency/Importance:** 22% override rate is operationally significant — one in five autonomous actions is rejected. RAND's escalation finding is cited in Congressional briefings.
**Palantir Address:** Track override rate as a first-class metric in the UI. When an operator rejects an AI action, prompt for a brief reason code (wrong target / wrong timing / policy violation). Feed this back into the `TacticalAssistant` weighting. Display "AI recommendation acceptance rate" on the ASSESS tab to help operators calibrate trust.

### 2.3 Communication Loss / Signal Degradation Behavior
**Source:** PX4 Autopilot GitHub issue #12381 (RC loss failsafe bug, 300+ views); ArduPilot advanced failsafe docs; DoD autonomous weapons operational risk (CNAS 2016)
**Pain Point:** When signal is lost, operators need predictable, configurable failsafe behavior. A documented PX4 bug caused vehicles to fall rather than trigger failsafe because RF modules kept sending PPM even when signal was actually lost. More broadly, "autonomy protocols can activate during signal loss, leading to unintended engagements."
**Frequency/Importance:** Safety-critical. The PX4 GitHub issue is a canary for a class of bugs across all autopilot platforms. DoD policy requires tested, predictable behavior under comms degradation.
**Palantir Address:** Palantir's demo autopilot loop doesn't model comms degradation. The `/autopilot` feature should expose a configurable "lost-link behavior" per drone: LOITER / RTB / CONTINUE_MISSION / SAFE_LAND. This is a procurement-table-stakes feature.

### 2.4 Deconfliction and Collision Avoidance Transparency
**Source:** MDPI collision avoidance research (2025, 25/4/1141); Airbus/Quantum Systems formation flight demo (Aug 2024); Swarmer platform documentation (getswarmer.com)
**Pain Point:** Operators trust swarm deconfliction less when it's a black box. When drones maneuver to avoid each other, operators want to see why — which drone triggered the avoidance, what the predicted conflict was, what was done.
**Frequency/Importance:** Emerging requirement as swarms scale to 50+ assets. Commercial platforms (Swarmer) now advertise "single operator controls thousands of drones without collisions" as a primary feature.
**Palantir Address:** Add a "deconfliction event" log to the Intel Feed. When the swarm coordinator re-assigns a task or the physics engine triggers an avoidance maneuver, emit a structured event: "UAV-2 rerouted to avoid UAV-5, ETA to task +12s." Surface this in the ASSETS tab timeline.

---

## 3. Military Simulation User Complaints

### 3.1 Latency Between Data and Display
**Source:** RAND RR2489 (C2 and situational awareness); Operation Lethal Eagle after-action findings (cited by Rancher Government blog, 2024); SAAB automated C2 analysis
**Pain Point:** "Reliance on legacy infrastructure creates significant operational risks, including communication delays." Map data latency of up to 45 minutes caused collateral damage near civilian infrastructure in 18% of cases in field exercises. Display refresh rates that lag behind the simulation degrade operator confidence.
**Frequency/Importance:** Directly cited in after-action reports from real exercises. 45-minute latency is catastrophic; even multi-second lag erodes trust.
**Palantir Address:** Palantir's 10Hz WebSocket loop with direct Cesium entity updates is architecturally correct. The risk is frontend rendering stalls under load (many entities, complex overlays). Add a latency indicator in the UI header showing WebSocket message age — operators should always know how fresh their picture is.

### 3.2 Scenario Reset and State Management
**Source:** QGroundControl GitHub issue #8192 (multiple missions state isolation); ArduPilot community forum patterns; general simulation user feedback patterns
**Pain Point:** Simulation users can't quickly reset to a known state, restart scenarios, or save/restore mid-exercise snapshots. When something goes wrong in a simulation, the only option is a full restart.
**Frequency/Importance:** Common complaint in every simulation platform. Exercise controllers and researchers need this constantly.
**Palantir Address:** Palantir has a `reset` WebSocket action and `SET_SCENARIO` command. The gap is a scenario snapshot/restore feature — save the full simulation state to a JSON blob, restore it later. Critical for research reproducibility and exercise replay.

### 3.3 Theater Configuration Complexity
**Source:** DARPA OFFSET program documentation; general C2 simulation researcher feedback patterns
**Pain Point:** Configuring a new theater (terrain, boundaries, threat types, ROE) requires deep system knowledge. Researchers want to rapidly prototype new scenarios without touching core code.
**Frequency/Importance:** High for research testbed use case. DARPA programs explicitly require configurable simulation environments.
**Palantir Address:** Palantir's YAML theater system (`theaters/`) is the right approach. The gap is a UI-level theater editor — drag-and-drop zone boundaries, point-and-click threat placement, exportable YAML. Makes Palantir usable as a testbed by non-developers.

---

## 4. ATAK/TAK Feature Requests and Pain Points

### 4.1 Sparse and Inconsistent SDK Documentation
**Source:** CloudRF ATAK plugin development blog; LearnATAK community documentation project (toyon.github.io); RIIS plugin tutorial series (2024); CivTAK developer forums
**Pain Point:** "The documentation for the ATAK SDK is rather sparse," motivating community documentation projects. Developers encounter build failures (plugintemplate compilation failures reported in issue #100), TLS certificate debugging complexity, and Java-only constraints where Python/web developers would prefer language-agnostic APIs.
**Frequency/Importance:** ATAK closed its GitHub source in May 2025, moving to internal GitLab — worsening the documentation gap and community trust.
**Palantir Address:** Palantir's WebSocket API is language-agnostic (curl, Python, JS all work). This is a direct competitive advantage over ATAK. Publish a clean API reference doc and OpenAPI spec. Make Palantir the platform that developers can actually build on without a security clearance review.

### 4.2 Government Approval Bottleneck for Plugins
**Source:** CloudRF ATAK blog; ATAK plugin signing documentation (RIIS, 2024); Defencebay analysis of ATAK closure (2025)
**Pain Point:** Every ATAK plugin requires US Government security/cryptographic review before production deployment. This kills commercial development velocity and blocks rapid capability fielding.
**Frequency/Importance:** Called out by every third-party ATAK developer as the primary friction point. The 2025 source closure made this worse.
**Palantir Address:** Palantir is open-source with no approval gate. This is a significant differentiator for research institutions, allied partners, and rapid prototyping teams. Make this explicit in documentation and marketing.

### 4.3 TAK Plugin Architecture Inflexibility
**Source:** CloudRF "How not to write a TAK plugin" analysis; community proposals for network-API-based plugins
**Pain Point:** Plugins are Java JARs tied to the Android app lifecycle. Developers propose "a more agile plugin architecture based on standard network APIs which doesn't prescribe a programming language or even an OS."
**Frequency/Importance:** Consistent developer complaint. The proposed solution (network APIs) is exactly what modern platforms use.
**Palantir Address:** Palantir's WebSocket + REST API architecture is the answer to this complaint. Any language, any platform. Consider publishing a plugin SDK guide showing how to build Palantir extensions in Python, JavaScript, or Go.

---

## 5. AI/Autonomy Researcher Needs from C2 Testbeds

### 5.1 Reproducible, Instrumented Scenarios
**Source:** DARPA XAI program retrospective (AAAI Magazine); academic research on C2 simulation testbeds (ScienceDirect, 2025); DARPA OFFSET program requirements
**Pain Point:** Researchers need to run the same scenario 100 times with controlled variations, instrument every AI decision with metadata, and export complete logs for analysis. Most C2 platforms are built for operators, not researchers.
**Frequency/Importance:** Every academic paper citing drone/C2 simulation describes building a custom testbed because existing platforms are too opaque.
**Palantir Address:** Palantir's `event_logger.py` with JSONL daily rotation is the right foundation. The gap is a "research mode" that: (1) logs every AI agent decision with full reasoning chain, (2) exposes a seed/replay mechanism for scenario reproducibility, (3) provides a metrics export endpoint (target detection latency, verification time, false positive rate).

### 5.2 Adjustable Autonomy for Ablation Studies
**Source:** Knight Columbia autonomy levels framework (July 2025); UK AISI Autonomous Systems Evaluation Standard; arxiv autonomy measurement paper (2025)
**Pain Point:** Researchers need to run the same scenario at different autonomy levels and measure outcomes. Current systems don't support programmatic autonomy level control mid-scenario or expose autonomy as a continuous variable.
**Frequency/Importance:** Foundational requirement for any HRI or autonomy research program. Multiple 2025 papers explicitly call for this capability.
**Palantir Address:** Palantir's three-level autonomy system (MANUAL/SUPERVISED/AUTONOMOUS) can be exposed as a WebSocket-controllable parameter. Add a `/set_autonomy_level` API that accepts a level AND a scope (global / per-drone / per-action-type). This makes Palantir directly usable for academic research.

### 5.3 Explainable AI Outputs with Measurable Trust Metrics
**Source:** DARPA XAI program (DARPA.mil); Springer article on XAI in military domain (2024); SPIE paper on bias/explainability for military AI (2024); UN Disarmament dialogue key takeaways (2025)
**Pain Point:** "Military AI-systems being explainable in principle may not imply that operators and handlers can understand the explanations." Researchers need systems that measure operator trust calibration, not just output explanations. Over-trust (automation bias) is as dangerous as under-trust.
**Frequency/Importance:** DARPA XAI has been running since 2016 and is still the top unresolved problem in military AI. UN 2025 dialogues cited it as the #1 blocker for autonomous weapons governance.
**Palantir Address:** Surface the `TacticalAssistant` reasoning chain in the UI — not just the recommendation, but the top 3 factors driving it (e.g., "Target classified TEL: high confidence based on EO detection (0.91) + SAR correlation (0.87) + movement pattern match (0.79)"). Add a "why did the AI do that?" button on any AI-generated action.

---

## 6. Developer Frustrations Building on C2 Platforms

### 6.1 No Stable, Versioned API Contract
**Source:** General C2 platform developer feedback; ATAK closure pattern analysis; QGroundControl plugin ecosystem fragility
**Pain Point:** When underlying C2 platforms update, integrations break silently. Developers need stable, versioned API contracts with deprecation warnings and changelogs.
**Frequency/Importance:** Universal developer complaint across ATAK, QGC, and Mission Planner ecosystems.
**Palantir Address:** Palantir's WebSocket message format is implicit/unversioned. Add a `protocol_version` field to all WebSocket messages. Publish a changelog. Consider a versioned REST API alongside WebSocket for integrations that need stability over latency.

### 6.2 No Multi-Vehicle Simulation Scaling
**Source:** QGroundControl GitHub issue #7225 (8-vehicle limit, multiple upvotes); QGC issue #7193 (parameter loading fails for 2nd+ vehicles); QGC issue #6864 (multi-vehicle mission start failure)
**Pain Point:** QGC cannot handle more than 8 vehicles. Users working on 15-30 vehicle swarms report missions not isolated between vehicles, parameter loading failures, and inability to start missions simultaneously.
**Frequency/Importance:** Repeatedly filed as critical issues. Research paper explicitly published to address QGC's multi-vehicle limitations (PMC/Sensors 2018).
**Palantir Address:** Palantir has no hard vehicle count limit. This is a strong differentiator. Validate and publicize performance benchmarks (e.g., "tested with 50 concurrent UAVs at 10Hz"). Add a swarm-size stress test to the demo mode.

### 6.3 Closed Ecosystem Lock-In
**Source:** ATAK GitHub closure (May 2025, Defencebay); TAK plugin approval bottleneck; Mission Planner Windows-only constraints
**Pain Point:** Proprietary platforms trap integrators. When ATAK moved to private GitLab in 2025, commercial developers and allies were cut off from tracking API changes. Mission Planner's Windows dependency blocks Linux-native server deployments.
**Frequency/Importance:** ATAK's 2025 closure generated significant community backlash. This is now a strategic risk for any organization building on TAK.
**Palantir Address:** Palantir's open-source, cross-platform (Python/FastAPI + React) stack is immune to this risk. Actively position against ATAK lock-in: "open API, runs anywhere, no government approval required."

---

## 7. Accessibility and Usability Issues

### 7.1 Color-Blind Accessibility in Threat/Status Displays
**Source:** HMI design research (Center for Operator Performance); A11Y Collective color blind guidelines; Smashing Magazine accessibility analysis; OSU color guidelines
**Pain Point:** Military displays heavily rely on red/green color coding for threat levels, status, and alerts. Approximately 8% of men have red-green color blindness, which in a 10-person ops center statistically affects at least one operator.
**Frequency/Importance:** Legal accessibility requirement in many procurement contexts. Known to cause operational errors in high-stress environments.
**Palantir Address:** Palantir's Blueprint dark theme uses color coding throughout. Add shape + icon redundancy alongside color (e.g., threat icons that differ by shape, not just color). Add an accessibility mode toggle. This is a low-cost change with procurement-table-stakes implications.

### 7.2 NVIS-Compatible Night Operations Display
**Source:** Grayhill NVIS interface design guide; DITHD military monitor specifications; Bytron aviation EFB day/night mode analysis; MIL-STD-3009
**Pain Point:** Ground control stations and C2 displays used in forward operating environments must be compatible with Night Vision Image Systems (NVIS). Bright, high-luminance displays destroy night adaptation and "bloom" under NVGs. Military standard MIL-STD-3009 specifies controlled luminance levels for cockpit/GCS displays.
**Frequency/Importance:** Procurement requirement for any system used in tactical forward environments. Missing from virtually all commercial drone GCS software.
**Palantir Address:** Add a "Night Operations Mode" to the Palantir frontend: reduced luminance, green-dominant palette, disable all white backgrounds. This is a keyboard shortcut (N key, similar to existing 1-6 map mode shortcuts) and a CSS theme switch. High signal value in defense procurement contexts.

### 7.3 Information Hierarchy and Clutter Management
**Source:** SAGE journals C2 maps operator workload study (2018); ScienceDirect interface design cognitive workload study (2024); PMC intelligent filter for C2 maps study (2023); NIH UAV swarm interaction framework (2025)
**Pain Point:** "Command and control maps are overloaded with irrelevant information." "Clutter and irrelevant information increase operators' workloads." The research finding is consistent: layered, task-centered design with a top-down information hierarchy significantly reduces cognitive load. The "enhanced" interface (layered, task-centered) yielded the lowest operator cognitive workload in controlled studies.
**Frequency/Importance:** Multiple peer-reviewed studies with measurable workload reductions (NASA-TLX scores). Directly applicable to Palantir's Cesium globe which renders all entities simultaneously.
**Palantir Address:** Palantir's LayerPanel is the right concept. Extend it with a "task focus mode" that auto-hides irrelevant entities based on current operator task (e.g., if doing BDA assessment, suppress SEARCH-mode drone tracks and show only strike history and assessment overlays). Add per-layer opacity controls, not just toggle.

---

## 8. Defense Procurement Requirements for Autonomous C2

### 8.1 Meaningful Human Control at Every Lethal Decision
**Source:** DoD Directive 3000.09 (2023 revision); CJADC2 ICD (October 2024, 12 core capabilities); Congressional Research Service IF11150; UN Disarmament dialogues (2025)
**Pain Point/Requirement:** All DoD autonomous weapon systems must maintain "appropriate levels of human judgment over the use of force." The 2023 revision of 3000.09 introduced "transparency, auditability, and explainability" as explicit requirements. Every lethal action must have a documented human in/on/over the loop.
**Frequency/Importance:** Statutory requirement. No compliant autonomous weapon system can bypass this. The October 2024 CJADC2 ICD formalized 12 capability functions, all including human oversight provisions.
**Palantir Address:** Palantir's two-gate HITL manager is the right architecture. The compliance gap is documentation: the system needs to log, for every engage/authorize action, the autonomy level at time of decision, the human who approved (or the rule that permitted autonomous action), and the sensor evidence that triggered the nomination. This audit log is a procurement deliverable.

### 8.2 Robust Failsafe and Degraded Operations Behavior
**Source:** DoD Directive 3000.09 training requirements; CNAS autonomous weapons operational risk paper (2016, still cited); PX4 RC loss failsafe bugs; ArduPilot GCS failsafe documentation gaps
**Pain Point/Requirement:** DoD requires that operators understand system behavior under degraded conditions and that systems have tested, predictable failsafe responses. Field evidence shows this is routinely underdeveloped: RF modules masking signal loss, autonomous protocols activating unexpectedly during comms degradation.
**Frequency/Importance:** Safety-critical and procurement-required. The CNAS paper on autonomous weapons operational risk is still cited in 2025 policy documents.
**Palantir Address:** Palantir's demo autopilot doesn't model comms loss. Add: (1) per-drone configurable lost-link behavior (LOITER/RTB/SAFE_LAND/CONTINUE), (2) a comms degradation simulator in the test harness that drops WebSocket messages at configurable rates, (3) UI indicator showing last-seen time for each drone.

### 8.3 Interoperability with Existing C2 Ecosystems
**Source:** CJADC2 strategy ("connect incompatible legacy systems and tactical networks"); Lockheed Martin CJADC2 interoperability factory demo (2025); Pentagon bridging solutions focus (DefenseScoop, 2023)
**Pain Point/Requirement:** The entire JADC2 program exists because current systems don't talk to each other. Procurement documents universally require open data standards, API interoperability, and compatibility with NATO STANAG and CoT (Cursor on Target) formats.
**Frequency/Importance:** JADC2 is a $multi-billion program. Interoperability is the single largest line item.
**Palantir Address:** Palantir speaks its own WebSocket protocol. Add CoT (Cursor on Target) XML output so Palantir targets appear on ATAK/WinTAK. Add a STANAG 4586 adapter stub. Even basic CoT support would make Palantir interoperable with the entire TAK ecosystem without requiring ATAK plugins.

---

## 9. Autonomy Feature Requests (Most Requested)

### 9.1 Adjustable Autonomy Per Asset Per Action Type
**Source:** Knight Columbia autonomy levels framework (5 levels: operator/collaborator/consultant/approver/observer); "Disciplined Autonomy" (Small Wars Journal, Feb 2026); DoD Directive 3000.09; academic HRI research
**Pain Point:** "Autonomy isn't just a byproduct of capability — it's a design decision." Users want to set autonomy at the action type level: allow FOLLOW autonomously, require approval for PAINT, always require HITL for AUTHORIZE. Current systems offer global modes only.
**Frequency/Importance:** Cited in DoD policy, academic research (multiple 2025 papers), and practitioner literature (Small Wars Journal). The 5-level framework from Columbia is being cited in 2025 autonomy governance discussions.
**Palantir Address:** Extend Palantir's autonomy model from [MANUAL/SUPERVISED/AUTONOMOUS] to a per-action matrix. Each action type (FOLLOW, PAINT, INTERCEPT, AUTHORIZE_COA, ENGAGE) gets an independent autonomy level. Store this as a policy object, not a mode. Time-bounded autonomy grants ("auto for 15 min") are also requested.

### 9.2 Transparent AI Reasoning ("Why Did It Do That?")
**Source:** DARPA XAI program; Springer XAI in military domain (2024); SPIE bias/explainability paper (2024); DoD 3000.09 transparency requirement; operator trust research
**Pain Point:** "Over-trust, automation bias, and degraded vigilance may lead users to defer excessively to system outputs, particularly when interfaces convey unwarranted certainty." Users need to understand AI recommendations to calibrate trust correctly — not just see the recommendation, but see the evidence and confidence behind it.
**Frequency/Importance:** The #1 open research problem in military AI per DARPA XAI program (running since 2016). Explicitly required by DoD 3000.09 ("why-did-you-do-that" button).
**Palantir Address:** Every `TacticalAssistant` recommendation should carry a structured rationale: action, top-3 evidence factors with confidence scores, ROE rule satisfied, and alternatives considered. Surface this in a "reasoning panel" that expands on click. This is the most impactful single feature for operator trust.

### 9.3 Override Mechanisms with Feedback Capture
**Source:** Field trial data (22% override rate); RAND escalation research; DoD 3000.09 operator control requirements; academic HRI literature
**Pain Point:** Overrides happen constantly (22% rate) but the system learns nothing from them. Operators want their corrections to improve future AI behavior, and they want visibility into how often they're correcting the AI.
**Frequency/Importance:** 22% override rate in field trials is high signal. Every override represents an alignment failure between AI and operator intent.
**Palantir Address:** When an operator overrides an AI recommendation, present a 3-option reason code: [Wrong Target / Wrong Timing / Policy/ROE Violation]. Log with timestamp. Display rolling acceptance rate on ASSESS tab. Feed reason codes into `llm_adapter.py` prompt context so the AI learns operator preferences within-session.

### 9.4 Time-Bounded and Conditional Autonomy Grants
**Source:** "Disciplined Autonomy" framework (Small Wars Journal, Feb 2026); academic autonomy delegation research; operator interviews in multi-UAV management studies
**Pain Point:** Operators want to say "be autonomous for the next 10 minutes while I handle this, then check in" or "be autonomous unless you detect a MANPADS, then wait for me." Binary autonomy modes force operators to choose between too much and too little.
**Frequency/Importance:** Emerging requirement in 2025-2026 practitioner literature. Not yet in most platforms. High differentiation value.
**Palantir Address:** Add autonomy grant parameters to the `set_autonomy_level` WebSocket action: `duration_seconds` (auto-reverts after timeout) and `exception_conditions` (list of target types or events that trigger a pause-and-ask). Display active autonomy grants with countdown timers in the ASSETS tab.

---

## 10. Common Autopilot/Autonomous Mode Complaints

### 10.1 Unpredictable Behavior at Mode Boundaries
**Source:** PX4 RC loss failsafe bug (#12381); ArduPilot advanced failsafe documentation gaps; CNAS autonomous weapons operational risk; RAND inadvertent escalation research
**Pain Point:** Systems behave unexpectedly when transitioning between autonomy modes, especially under stress (comms degradation, sensor failure, operator distraction). "Autonomy protocols can activate during signal loss, leading to unintended engagements." Mode transitions need to be explicit, confirmed, and reversible.
**Frequency/Importance:** Safety-critical failure mode with documented real-world incidents. RAND found autonomous speed led to inadvertent escalation in wargames.
**Palantir Address:** Palantir's `approve_transition` / `reject_transition` system is the right pattern. Extend it: every autonomy mode transition above SUPERVISED should require an explicit acknowledgment toast (not just a background state change). Display mode transition history in a timeline per drone. Never silently escalate autonomy level.

### 10.2 No Audit Trail for Autonomous Actions
**Source:** DoD 3000.09 auditability requirement; Congressional CRS report IF11150; CJADC2 ICD (October 2024); accountability research on autonomous weapons
**Pain Point:** "Delegating lethal force decisions to algorithms raises accountability questions." Procurement and legal requirements demand a complete, tamper-evident audit trail of every autonomous action: what triggered it, what the system state was, what human oversight was applied.
**Frequency/Importance:** Statutory requirement for DoD fielding. No autonomous weapon system can be deployed without this.
**Palantir Address:** Palantir's `event_logger.py` captures events but not structured audit records. Add an `audit_log` table/stream with: timestamp, action type, autonomy level at time, triggering sensor evidence (with confidence), human override status (approved/rejected/timeout), and operator identity. Expose via a read-only REST endpoint.

### 10.3 "Black Box" Autonomous Decisions
**Source:** DARPA XAI retrospective (AAAI Magazine); military XAI research; operator survey data showing trust drops when explanations are absent; UN 2025 disarmament dialogues
**Pain Point:** When autopilot makes a decision, operators don't know if it was rule-based, ML-based, or a heuristic fallback. This ambiguity destroys trust calibration. "Operators and handlers cannot understand the explanations or make reliable predictions."
**Frequency/Importance:** UN 2025 dialogues cited this as the #1 blocker for autonomous weapons governance. DARPA has spent 10+ years on this problem.
**Palantir Address:** Palantir uses `llm_adapter.py` with Gemini → Anthropic → heuristic fallback. The fallback path especially is a black box. Label every AI output with its source: [AI: Gemini-2.0] or [Heuristic: Rule 7 - SAM threat threshold] or [Human Override]. Different visual treatment (icon/color) for each source type. Operators should never mistake a heuristic for an AI recommendation.

### 10.4 Insufficient Pre-Autonomy Briefing
**Source:** DoD 3000.09 training requirement ("adequate training, tactics, techniques, and procedures periodically reviewed"); operator workload research; DARPA OFFSET lessons learned
**Pain Point:** Before engaging autonomous mode, operators don't know what the system will do in edge cases. They engage autopilot and are surprised by behaviors they didn't anticipate.
**Frequency/Importance:** DoD requires this by policy. In practice, most systems (including commercial) provide no pre-autonomy briefing.
**Palantir Address:** When activating autonomous mode (AUTONOMOUS level), present a one-screen "autonomy briefing": what the system will do autonomously, what it will ask permission for, what triggers auto-reversion to SUPERVISED, and current active ROE rules. Require explicit acknowledgment. This is a 2-hour implementation with major compliance value.

---

## Cross-Cutting Themes and Priority Ranking

| # | Theme | Frequency | Impact | Palantir Effort | Priority |
|---|-------|-----------|--------|-----------------|----------|
| 1 | Transparent AI reasoning ("why did it do that?") | Very High | Critical | Medium | P0 |
| 2 | Adjustable per-action autonomy controls | Very High | Critical | Medium | P0 |
| 3 | Complete audit trail for autonomous actions | High | Critical | Low | P0 |
| 4 | Lost-link/failsafe behavior configuration | High | Critical | Medium | P0 |
| 5 | Cognitive overload / information filtering UI | Very High | High | High | P1 |
| 6 | Override capture + AI learning from corrections | High | High | Medium | P1 |
| 7 | Pre-autonomy briefing screen | Medium | High | Low | P1 |
| 8 | Night operations display mode (NVIS) | Medium | High | Low | P1 |
| 9 | CoT/ATAK interoperability | High | High | High | P2 |
| 10 | Scenario snapshot/restore for research | Medium | Medium | Medium | P2 |
| 11 | Time-bounded autonomy grants | Medium | Medium | Medium | P2 |
| 12 | Color-blind accessibility | Low | Medium | Low | P2 |
| 13 | Deconfliction event log | Medium | Medium | Low | P2 |
| 14 | Research mode (reproducible scenarios + metrics export) | Medium | Medium | High | P3 |
| 15 | Swarm health at-a-glance panel | High | Medium | Medium | P3 |

---

## Sources

- [TAK.gov](https://tak.gov/) — TAK Product Center official site
- [CivTAK ATAK Plugin Development Tutorial (2024)](https://www.civtak.org/2024/12/04/atak-plugin-development-tutorial/)
- [ATAK/TAK Open Source Code Closure 2025 — Defencebay](https://defencebay.com/en/zamkniecie-otwartego-kodu-atak-tak-w-2025)
- [Evolution and future of TAK — Breaking Defense (2025)](https://breakingdefense.com/2025/11/evolution-and-future-of-the-tactical-assault-kit-for-soldiers-and-special-operators/)
- [QGroundControl GitHub Issues](https://github.com/mavlink/qgroundcontrol/issues)
- [QGC Multi-Vehicle Support Issue #7225](https://github.com/mavlink/qgroundcontrol/issues/7225)
- [QGC Mission Planning Improvements Issue #10310](https://github.com/mavlink/qgroundcontrol/issues/10310)
- [Extending QGroundControl for Automated Mission Planning — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6068744/)
- [L3 low-bandwidth high-autonomy drone swarm — Defense One (Feb 2025)](https://www.defenseone.com/technology/2025/02/l3-unveils-new-low-bandwidth-high-autonomy-drone-swam-tech/402859/)
- [FPV Drone Swarms in Asymmetric Warfare — Science Publishing Group (2025)](https://www.sciencepublishinggroup.com/article/10.11648/j.advances.20250603.12)
- [Disciplined Autonomy — Small Wars Journal (Feb 2026)](https://smallwarsjournal.com/2026/02/11/disciplined-autonomy/)
- [Operator on the Loop — Daily Sabah](https://www.dailysabah.com/opinion/op-ed/next-in-aerial-autonomous-weapons-operator-on-the-loop-but-not-in-it)
- [DoD Directive 3000.09 — Exploring the 2023 U.S. Directive on Autonomy — CEBRI](https://cebri.org/revista/en/artigo/114/exploring-the-2023-us-directive-on-autonomy-in-weapon-systems)
- [JADC2 Wikipedia](https://en.wikipedia.org/wiki/Joint_All-Domain_Command_and_Control)
- [JADC2 Strategy Summary PDF — DoD](https://media.defense.gov/2022/Mar/17/2002958406/-1/-1/1/SUMMARY-OF-THE-JOINT-ALL-DOMAIN-COMMAND-AND-CONTROL-STRATEGY.PDF)
- [Reimagining Military C2 in the Age of AI — SCSP (Dec 2024)](https://www.scsp.ai/wp-content/uploads/2024/12/DPS-Reimagining-Military-C2-in-the-Age-of-AI.pdf)
- [GAO Defense C2 Report GAO-25-106454](https://www.gao.gov/assets/gao-25-106454.pdf)
- [CJADC2 Progress in 2025 — GovConWire](https://www.govconwire.com/articles/cjadc2-progress-areas-beginning-2025-dod)
- [RAND Improving C2 and Situational Awareness RR2489](https://www.rand.org/pubs/research_reports/RR2489.html)
- [Operator Workload in UAV C2 Maps — SAGE Journals (2018)](https://journals.sagepub.com/doi/10.1177/1541931218621243)
- [Intelligent Filter for C2 Maps — PMC (2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10626988/)
- [Towards Human-Centered UAV Swarm Interaction — ScienceDirect (2025)](https://www.sciencedirect.com/article/pii/S3050741325000291)
- [Effect of Interface Design on Cognitive Workload in UAV Control — ScienceDirect (2024)](https://www.sciencedirect.com/article/abs/pii/S1071581924000715)
- [NASA Cognitive Walkthrough of Multiple Drone Delivery Ops — NTRS (2021)](https://ntrs.nasa.gov/api/citations/20210018022/downloads/Cognitive%20Walkthrough%20of%20Multi-Drone%20Delivery%20Ops.Smith%20et%20al.AIAA.2021.pdf)
- [Supervised Classification of Operator Functional State — PMC (2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8772640/)
- [Adaptive Human-Robot Interactions for Multiple UAVs — MDPI Robotics (2021)](https://www.mdpi.com/2218-6581/10/1/12)
- [Collision Avoidance Mechanism for Drone Swarms — MDPI Sensors (2025)](https://www.mdpi.com/1424-8220/25/4/1141)
- [AI Drone Swarm Coordination 20 Advances — Yenra (2025)](https://yenra.com/ai20/drone-swarm-coordination/)
- [Swarmer — Combat-driven collaborative autonomy](https://getswarmer.com/)
- [Explainable AI in Military Domain — Springer (2024)](https://link.springer.com/article/10.1007/s10676-024-09762-w)
- [DARPA XAI Program](https://www.darpa.mil/research/programs/explainable-artificial-intelligence)
- [DARPA XAI Retrospective — Wiley Applied AI Letters (2021)](https://onlinelibrary.wiley.com/doi/full/10.1002/ail2.61)
- [Bias, Explainability, Transparency for AI Military Systems — SPIE (2024)](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/13054/1305406/Bias-explainability-transparency-and-trust-for-AI-enabled-military-systems/10.1117/12.3012949.short)
- [UN Military AI Peace & Security Dialogues 2025](https://disarmament.unoda.org/en/updates/key-takeaways-military-ai-peace-security-dialogues-2025)
- [Levels of Autonomy for AI Agents — Knight Columbia (2025)](https://knightcolumbia.org/content/levels-of-autonomy-for-ai-agents-1)
- [UK AISI Autonomous Systems Evaluation Standard](https://ukgovernmentbeis.github.io/as-evaluation-standard/)
- [Measuring AI Agent Autonomy — arxiv (2025)](https://arxiv.org/html/2502.15212v1)
- [PX4 RC Loss Failsafe Bug #12381](https://github.com/PX4/PX4-Autopilot/issues/12381)
- [CNAS Autonomous Weapons Operational Risk (2016)](https://s3.amazonaws.com/files.cnas.org/documents/CNAS_Autonomous-weapons-operational-risk.pdf)
- [Defense Primer: Lethal Autonomous Weapon Systems — CRS IF11150](https://www.congress.gov/crs-product/IF11150)
- [Human-in-the-Loop: Safety Mechanism or Safety Theater?](https://markmcneilly.substack.com/p/human-in-the-loop-safety-mechanism)
- [NVIS-Compatible Interfaces for Tactical Systems — Grayhill](https://grayhill.com/blog/seeing-in-the-dark-designing-nvis-compatible-operator-interfaces-for-tactical-systems/)
- [MIL-STD-3009 NVIS Standard](https://www.appliedavionics.com/pdf/MIL-STD-3009.pdf)
- [HMI Background Color — Center for Operator Performance](https://centerforoperatorperformance.org/projects/background-color-hmi)
- [How not to write a TAK plugin — CloudRF](https://cloudrf.com/how-not-to-write-a-tak-plugin/)
- [Snipers Hide ATAK Discussion Forum](https://www.snipershide.com/shooting/threads/atak-anyone-using-worth-using.7014716/)
- [LearnATAK Documentation — Toyon](https://toyon.github.io/LearnATAK/docs/setup/atak_plugin/)
- [WebTAK Socket Disconnected Issue #51 — TAK-Product-Center/Server](https://github.com/TAK-Product-Center/Server/issues/51)
- [Command-agent: LLM-based warfare simulation — ScienceDirect (2025)](https://www.sciencedirect.com/science/article/pii/S2214914725002776)
- [ArduPilot Swarming Documentation](https://ardupilot.org/planner/docs/swarming.html)
- [Defense Paper Reimagining Military C2 — SCSP (Dec 2024)](https://www.scsp.ai/wp-content/uploads/2024/12/DPS-Reimagining-Military-C2-in-the-Age-of-AI.pdf)
