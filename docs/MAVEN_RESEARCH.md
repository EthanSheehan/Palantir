---
tags: [grid_sentinel, research, maven, palantir, competitive_analysis]
---
# Palantir Maven Smart System — Research Report

*Generated 2026-05-06 · Sources: 18 · Confidence: High on history/architecture, Medium on UI internals (most operator screens are classified)*

## Executive summary

Palantir's **Maven Smart System (MSS)** is the de-facto reference design for AI-assisted Combined Joint All-Domain Command & Control (CJADC2). It consolidated **nine separate DoD targeting tools** into one platform, ingests data from **179 real-time intelligence feeds** at CENTCOM, and has **~25,000 active US users** as of March 2026 ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven), [DefenseScoop](https://defensescoop.com/2026/04/03/palantir-maven-feinberg-directive/)). The kill-chain time it targets — `743 minutes (2020) → <1 minute (2024)`, scaling to **5,000 targets/day** with LLMs — is the bar Grid-Sentinel is implicitly chasing.

The system maps cleanly onto the **OODA loop**: Observe (multi-INT sensor fusion), Orient (computer-vision classification with stable identifiers), Decide (Kanban-style Target Workbench + COA generation), Act (asset-tasking recommender + direct-to-weapons messaging) — with **mandatory human approval** between Decide and Act ([Spatial Intelligence](https://www.spatialintelligence.ai/p/inside-palantirs-maven-smart-system)).

## 1. What the operator actually sees

The most concrete UI description we have is from the Spatial Intelligence walkthrough, which Palantir's CAIO summarized as *"left click, right click, left click — magically, it becomes a detection."* Named UI components:

| Component | Function |
|---|---|
| **Fused Map View** | Globe-based display layering satellite feeds, drone streams, SIGINT, road networks, prior map data ([Spatial Intelligence](https://www.spatialintelligence.ai/p/inside-palantirs-maven-smart-system)) |
| **Detection Layer** | Ground-level dots; each gets a *stable identifier number that follows it across modalities* (CV → SAR → SIGINT) |
| **Kanban Board** | Vertical columns per team process; target detections nominate into it for processing |
| **Target Workbench** | Operators approve/disapprove, sequence targets by priority, message directly to weapons systems ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven)) |
| **AI Asset Tasking Recommender** | Proposes which bomber/munition for which target — optimised on time-to-target, fuel, munitions, distance |
| **Imagery exploitation suite** | "View all imagery associated with an Area of Interest, conduct comprehensive analysis and activity monitoring" ([army.mil](https://www.army.mil/article/283473)) |
| **AIP chat** | Natural-language query bar; the original AIP demo was an operator asking the assistant to identify enemy forces and generate COAs ([ResearchGate](https://www.researchgate.net/figure/Palantir-AIP-interface-a-a-Source-Video-screenshot-from-Palantir-Palantir-AIP-for_fig4_381034070)) |

Color conventions on the map: **yellow-outlined boxes = potential targets, blue boxes = friendly forces / restricted zones** ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven)).

## 2. What's underneath

### 2.1 Multi-INT data sources fused

- Keyhole-class spy satellites
- Synthetic-aperture radar from ICEYE and Capella Space
- Wide-area motion imagery (Gorgon Stare, ARGUS-IS)
- MQ-9 Reaper full-motion video
- SIGINT / RF emissions
- RQ-180 stealth recon feeds
- Geolocation metadata, IP/geotags, comms intercepts ([Spatial Intelligence](https://www.spatialintelligence.ai/p/inside-palantirs-maven-smart-system))

CENTCOM's deployment integrates **179 real-time feeds** ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven)).

### 2.2 The ontology layer

MSS standardises heterogeneous data through an **ontology layer** — Palantir's signature primitive ([Palantir Docs](https://www.palantir.com/docs/foundry/ontology/core-concepts)). Three layers:

- **Semantic**: object types (Person, Vehicle, Sensor, Target), properties, link types ("Vehicle is operated by Organization")
- **Kinetic**: actions and functions that mutate object state
- **Dynamic security**: object-level access control across classification tiers

The Ontology Metadata Service (OMS) is the single source of truth that Foundry datasets, Gotham investigations, AIP agents, and the Maven UI all bind against ([Palantir Docs](https://www.palantir.com/docs/foundry/ontology/overview)).

### 2.3 AI/ML stack

- **Computer vision** trained on 4M+ labeled military-asset images — drives the "Detection Layer"
- **LLM model hub** — multiple models swappable per task: ChatGPT, Llama, and (until March 2026) Anthropic Claude under "Claude Gov" at IL6 / FedRAMP High ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven))
- **Sensor fusion** for cross-modal track correlation under low-bandwidth tactical-network constraints (BAS-T programme)
- **Course-of-action generation** — Hadean's *dominAI* tool integrates with Maven to *generate, simulate, and compare* multiple COAs ([executivegov.com](https://www.executivegov.com/articles/palantir-marine-corps-mss-c2-contract-award))

### 2.4 Effects integration

Maven does **4 of 6 kill-chain steps**: identify, locate, filter lawful targets, prioritise. Final assignment + firing remain human ([Wikipedia](https://en.wikipedia.org/wiki/Project_Maven)). It transmits firing decisions directly to:

- **AFATDS** — Advanced Field Artillery Tactical Data System
- **JREAP** — Joint Range Extension Application Protocol (weapons routing)
- Air Operations Centers
- **JADOCS** — Joint Automated Deep Operations Coordination System
- **AMPS** — Aviation Mission Planning System

## 3. Scale, performance, deployment

| Metric | Value | Source |
|---|---|---|
| US users (Mar 2026) | ~25,000 | [Wikipedia](https://en.wikipedia.org/wiki/Project_Maven) |
| Service tools served | 35 across 3 classification domains | [DefenseScoop](https://defensescoop.com/2026/04/03/palantir-maven-feinberg-directive/) |
| Targeting time | 743 min (2020) → <1 min (2024) | [Wikipedia](https://en.wikipedia.org/wiki/Project_Maven) |
| Daily target throughput | ~1,000 (CV only) → 5,000 (with LLM) | [Wikipedia](https://en.wikipedia.org/wiki/Project_Maven) |
| Iran 2026 D-1 strikes | 1,000+ targets first day | [IBTimes](https://www.ibtimes.com/palantirs-ai-powers-us-strikes-iran-war-speeding-kill-chain-first-major-ai-driven-conflict-3800993) |
| Contract ceiling | $1.3B through 2029 | [Palantir IR](https://investors.palantir.com/news-details/2024/Palantir-Expands-Maven-Smart-System-AIML-Capabilities-to-Military-Services/) |
| Classification | DISA Impact Level 5–6, FedRAMP High | [Wikipedia](https://en.wikipedia.org/wiki/Project_Maven) |
| Geographic deployment | INDOPACOM, EUCOM, CENTCOM, NORAD/NORTHCOM, SPACECOM, TRANSCOM, AFRICOM, Joint Staff, NATO ACO | [Wikipedia](https://en.wikipedia.org/wiki/Project_Maven) |

## 4. TITAN — the hardware tier

Where MSS is the software, **TITAN (Tactical Intelligence Targeting Access Node)** is the Army's mobile ground station that runs it. Palantir won $178.4M for 10 prototypes (5 Advanced + 5 Basic) integrating Anduril, L3Harris, Northrop, Pacific Defense, SNC ([Palantir](https://www.palantir.com/titan/)). The pattern: **single software stack runs from cloud to tactical edge, on whatever the comms link allows**.

## 5. Adjacent products in the stack

| Product | Role |
|---|---|
| **Gotham** | Investigation / link analysis UI; same ontology, different lens |
| **Foundry** | Data integration & analytics platform |
| **AIP** | LLM/agent layer (AIP Logic, AIP Chatbot Studio, AIP Evals) ([Palantir Docs](https://www.palantir.com/docs/foundry/aip/overview)) |
| **Apollo** | Continuous deployment to disconnected/classified environments |
| **Lattice Mesh (Anduril)** | Tactical sensor data ingest, joint Dec 2024 announcement |

The architecture is **open and extensible** — third-party tools plug in via the ontology and AIP rather than monolithic integration.

## 6. Sources

1. [Project Maven — Wikipedia](https://en.wikipedia.org/wiki/Project_Maven)
2. [Inside Palantir's Maven Smart System — Spatial Intelligence](https://www.spatialintelligence.ai/p/inside-palantirs-maven-smart-system) — best UI-level walkthrough
3. [Maven Smart System: Innovating for the Alliance — Palantir Blog](https://blog.palantir.com/maven-smart-system-innovating-for-the-alliance-5ebc31709eea)
4. [Feinberg's Maven directive — DefenseScoop](https://defensescoop.com/2026/04/03/palantir-maven-feinberg-directive/)
5. [Palantir MAVEN Replaced 9 DoD Systems — abhs.in](https://www.abhs.in/blog/palantir-maven-smart-system-ai-kill-chain-dod-deployment-2026)
6. [Pentagon Expands Use of Palantir AI — Military.com](https://www.military.com/feature/2026/03/22/pentagon-expands-palantirs-role-ai-contract.html)
7. [Maven Smart System — Missile Defense Advocacy](https://www.missiledefenseadvocacy.org/maven-smart-system/)
8. [Maven AI Powers US Iran Strikes — IBTimes](https://www.ibtimes.com/palantirs-ai-powers-us-strikes-iran-war-speeding-kill-chain-first-major-ai-driven-conflict-3800993)
9. [TITAN — Palantir](https://www.palantir.com/titan/)
10. [Army Selects Palantir for TITAN — Palantir IR](https://investors.palantir.com/news-details/2024/Army-Selects-Palantir-to-Deliver-TITAN-Next-Generation-Deep-Sensing-Capability-in-Prototype-Maturation-Phase/)
11. [Gotham — Palantir](https://www.palantir.com/platforms/gotham/)
12. [AIP Overview — Palantir Docs](https://www.palantir.com/docs/foundry/aip/overview)
13. [AIP for Defense — Palantir](https://www.palantir.com/platforms/aip/defense/)
14. [Ontology Core Concepts — Palantir Docs](https://www.palantir.com/docs/foundry/ontology/core-concepts)
15. [Foundry-Gotham Type Mapping — Palantir Docs](https://www.palantir.com/docs/foundry/object-link-types/enable-gotham-integration)
16. [Marine Corps MSS Contract — ExecutiveGov](https://www.executivegov.com/articles/palantir-marine-corps-mss-c2-contract-award)
17. [Contracting personnel use AI — army.mil](https://www.army.mil/article/283473/contracting_personnel_use_ai_maven_smart_system_simulation_during_warfighter_exercise)
18. [Signals of a New Revolution — Global Security Review](https://globalsecurityreview.com/signals-of-a-new-revolution-maven-smart-system-and-the-ai-rma-horizon/)

## Methodology

Eight web search queries spanning architecture, UI, kill-chain workflow, sensor fusion, COA generation, TITAN, AIP, and ontology. Two key sources fully scraped (Spatial Intelligence article + Wikipedia). Several Palantir blog/marketing pages 403'd or redirected — UI internals are largely classified, so the operator-screen description is the best public detail available.

## Acknowledged gaps

- **No public screenshots of MSS at production fidelity** — every public image is the AIP demo or marketing video.
- **Track-correlation algorithm specifics** are proprietary; published descriptions are at the "data fusion produces a common operational picture" level.
- **Internal API surface between MSS and AFATDS/JREAP** is classified.
- **Latency under contested comms** — claimed as "low-bandwidth tactical network capable" but no hard numbers public.
