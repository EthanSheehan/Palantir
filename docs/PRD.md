# PRD: Project "Antigravity" – Multi-Agent Decision-Centric C2 System

## 1. Executive Summary
Project **Antigravity** is a high-fidelity recreation of the multi-domain Command and Control (C2) capabilities demonstrated in the Palantir "Maven Smart System" showcase. The system pivots from traditional "data-centric" surveillance to a **"decision-centric"** orchestration model, utilizing specialized AI agents to automate the F2T2EA (Find, Fix, Track, Target, Engage, Assess) kill chain.

---

## 2. Core Philosophy: The Decision-Centric Approach
Following the CDAO 2.0 rubric, every agentic workflow in Antigravity must address these nine pillars:
1.  **Decision Focus:** Identify the specific tactical decision (e.g., "Should we engage this TEL?").
2.  **Legacy Comparison:** Define how this decision is currently made (manual screen-monitoring).
3.  **Acceleration Target:** Pinpoint which phase of the kill chain is being compressed.
4.  **Data Requirements:** Specify the minimal viable data needed for high-confidence action.
5.  **Ingestion Path:** Determine how data arrives (API, satellite stream, or sensor link).
6.  **Human Interaction:** Design the HITL (Human-in-the-Loop) interface for final approval.
7.  **Labor Reduction:** Quantify the reduction in "eyes-on-glass" time.
8.  **Success Metrics:** Define clear KPIs (e.g., "Target destroyed with zero collateral").
9.  **Iteration Plan:** Establish a feedback loop where post-strike data improves future agent logic.

---

## 3. Multi-Agent System (MAS) Architecture

### 3.1 Agent Personas & Responsibilities

| Agent Name | Role | Core Capability |
| :--- | :--- | :--- |
| **ISR Observer** | Sensor Fusion | Consolidates disparate feeds (UAV, satellite, SIGINT) into a unified Common Operational Picture (COP). |
| **Strategy Analyst** | Decision Support | Evaluates detections against Rules of Engagement (ROE) and nominates targets to the "Strike Board". |
| **Tactical Planner** | COA Generation | Generates Courses of Action (COAs) by matching targets to effectors (munitions, aircraft, units). |
| **Effectors Agent** | Execution & BDA | Manages technical handshakes for tasking and performs Battle Damage Assessment (BDA) post-strike. |

### 3.2 Technical Requirements
* **Abstraction Layer:** Agents must interact with a "Smart System" middleware that translates high-level commands into specific hardware/legacy software protocols.
* **Ontology Mapping:** All data must be mapped to a shared, extensible data ontology to ensure the "Observer" and "Planner" share a consistent world-view.
* **Reasoning Traces:** Every recommendation must include a "Why" trace (e.g., "Asset Stryker-1 selected due to 4m 23s arrival time and 98% probability of kill").

---

## 4. User Experience & HITL
* **Single Visualization Tool:** A unified map interface allowing users to toggle between different types of data (satellite, computer vision, tactical graphics).
* **The "Action" Menu:** A simplified UI for the commander: **Reject, Retask, or Approve**.
* **Real-time Feedback:** Visual confirmation of task execution and status (e.g., "Task Executed" and "Target Destroyed").

---

## 5. Success Metrics (The "Maven" Standard)
* **Latency:** Reduce the end-to-end kill chain from hours/days to seconds/minutes.
* **Consolidation:** Replace 8-9 disparate monitoring systems with a single agent-orchestrated interface.
* **Evolvability:** The system must get better every day based on the "Process Improvement Flywheel".

---

## 6. Implementation Roadmap

### Phase 1: Data Ingestion & Ontology (Weeks 1-4)
* Build the abstraction layer for multi-source data.
* Establish the common data format for agent communication.

### Phase 2: Autonomous Detection & Strategy (Weeks 5-8)
* Deploy the **ISR Observer** to identify targets.
* Implement the **Strategy Analyst** to filter and nominate targets.

### Phase 3: Tactical Orchestration (Weeks 9-12)
* Integrate the **Tactical Planner** for COA generation.
* Finalize the **Effectors Agent** for execution and BDA.

---