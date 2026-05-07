---
tags: [grid_sentinel, beyond_maven, run_history]
---
# Beyond-Maven Push — Run History

*Last updated 2026-05-07*

This is the operational log for the autonomous-loop iteration sweep that
took Grid-Sentinel from "Maven-parity prototype" to "beyond-Maven across
every named differentiator in `docs/PROFESSIONAL_LEVEL_BLUEPRINT.md`."

## Test floor over time

| Iteration | Tests passing | Δ |
|---|---|---|
| Baseline (post `2e9b4c2` Maven-parity wave 1) | 1860 | — |
| i1 — agent registry → LLMAdapter | 1860 | 0 |
| i2 — real activity-history backend | 1860 | 0 |
| i3 — real F2T2EA SLA metrics | 1867 | +7 |
| i4 — per-task LLM model selection | 1867 | 0 |
| i5 — multi-classification persona | 1867 | 0 |
| i6 — confidence sparkline + ROE attribution | 1867 | 0 |
| i7 — visual polish wave | 1867 | 0 |
| i8 — theater hot-swap + reflective AI | 1869 | +2 |
| i9 — decision_replay agent | 1872 | +3 |
| i10 — AsyncAPI + CLAUDE.md sync | 1872 | 0 |
| i11 — fix_plan close-out | 1872 | 0 |
| i12 — pulse + typewriter + swarm explainability | 1872 | 0 |
| i13 — per-persona broadcast filter | 1876 | +4 |
| i14 — Foundry-style ontology layer | 1895 | +19 |
| i15 — CI matrix + IL-5/6 posture | 1895 | 0 |
| i16 — synthesis_query agent migrated | 1897 | +2 |
| i17 — Cesium swarm-line tooltip | 1897 | 0 |
| i18 — two-person concurrence backend | 1911 | +14 |
| i19 — security CI scans | 1911 | 0 |
| i20 — 7 chat handlers ontology-migrated | 1911 | 0 |
| i21 — TwoPersonConcurrencePanel UI | 1911 | 0 |
| i22 — README + run-history docs | 1911 | 0 |

**Net: +51 tests, 0 regressions across 22 commits.**

## Commit history

| # | Commit | Title |
|---|--------|-------|
| 1 | `6c2fc04` | feat(agents): registry handlers route through LLMAdapter |
| 2 | `8ce96ae` | feat(history): real activity-history backend |
| 3 | `2c3a96f` | feat(metrics): real F2T2EA SLA metrics |
| 4 | `92eea5c` | feat(ui): per-task LLM model tier selection |
| 5 | `ca46a27` | feat(persona): multi-classification persona switching |
| 6 | `449bace` | feat(diff): confidence sparkline + ROE attribution |
| 7 | `39313ca` | feat(ui): visual polish wave (glass.css, WCAG, animations) |
| 8 | `d673418` | feat(theater+critic): cross-theater hot-swap + reflective AI |
| 9 | `181db40` | feat(replay): decision_replay agent |
| 10 | `7a6c5c6` | docs: AsyncAPI + CLAUDE.md sync |
| 11 | `1ba9c5d` | chore(ralph): close out fix_plan iterations 1-10 |
| 12 | `f8e7783` | feat(ui+swarm): pulse + typewriter + swarm explainability |
| 13 | `a6f39e9` | feat(persona): per-persona broadcast filter |
| 14 | `6200858` | feat(ontology): Foundry/Gotham-style ontology layer |
| 15 | `d3a1b0e` | chore(ci+docs): CI matrix + DISA IL-5/6 posture audit |
| 16 | `a1a2715` | feat(ontology): synthesis_query_agent migrated to OntologyService |
| 17 | `f8b3002` | feat(swarm): Cesium swarm-line InfoBox tooltips |
| 18 | `4cb4386` | feat(security): two-person concurrence backend |
| 19 | `32b5221` | chore(ci): security scan workflow (pip-audit + bandit + trufflehog) |
| 20 | `d10a3dd` | feat(ontology): migrate remaining 6 chat handlers to OntologyService |
| 21 | `650c28d` | feat(ui): TwoPersonConcurrencePanel UI |
| 22 | _(this commit)_ | docs: README beyond-Maven section + run-history dashboard |

## Beyond-Maven differentiator summary

By the end of iteration 22, every Maven-aspect listed in
`docs/MAVEN_RESEARCH.md` has either parity or a deliberate beyond.

| Maven feature | Grid-Sentinel | Beyond-Maven beat |
|---|---|---|
| Fused Map View | Cesium globe + 6 modes + 5 layer overlays | + numbered stable-ID detection dots + state-pulse animations |
| Detection Layer with stable IDs | Numbered #NNNN dots on every Target | + state-coloured ring + per-INT filter |
| Kanban / Target Workbench | 8-column TargetWorkbench (DETECTED → COMPLETE) | + per-card confidence sparkline with trend arrow |
| AI Asset Tasking | `ai_tasking_manager.evaluate_and_retask_async` via LLMAdapter | + AssetTaskingDrawer with why-trace |
| AIP Chat | AIPChatPanel slash-router to all 11 agents | + per-task model-tier picker + ModelHubBadge |
| Effector dispatch (AFATDS, JREAP, JADOCS, AMPS) | All four stubs with NATO message IDs | + ack latency surfaced on ActivityTimeline |
| Foundry/Gotham ontology | OntologyService with object/link/action types | + dynamic security: per-persona broadcast filter |
| Multi-classification | Single tier per Maven deployment | + UNCLASS/CUI/SECRET live persona switch with reactive ClassificationBanner |
| Audit + AAR | `audit_log` SHA-256 hash chain + verify_chain | + decision_replay agent for postmortem re-run |
| Reflective AI | Not in Maven | self_critic agent surveys audit_log for COA churn / repeated rejections |
| Theater coverage | Single theater per deployment | + cross-theater hot-swap (Romania ↔ Baltic ↔ SCS) without restart |
| Two-person concurrence (FedRAMP) | Single-operator on Maven | TwoPersonConcurrence backend + UI panel; AUTONOMOUS dispatch blocks without authorised pair |
| 3D rendering | Maven leans on commercial GIS stack | NVIDIA-free pyrender pipeline, runs on a 2015 Intel MacBook Air |
| F2T2EA SLA observability | Maven internal | `metrics.sla_snapshot` with per-stage thresholds + SLADashboard |
| ROE attribution | Generic "rejected" | `evaluate_with_attribution` cites the matched rule name |
| CI / supply-chain hygiene | Maven internal | Public CI matrix + pip-audit / npm audit / bandit / trufflehog SARIF |

## Operator-visible keyboard shortcuts (current)

| Key | Action |
|---|---|
| `1` … `6` | Map modes OPERATIONAL / COVERAGE / THREAT / FUSION / SWARM / TERRAIN |
| `2` (alone) | Toggle two-person concurrence panel |
| `A` | Toggle asset tasking drawer |
| `B` | Floating strike board |
| `G` | Global alert center |
| `H` | Activity timeline |
| `L` | Map legend |
| `N` | NVIS mode |
| `S` | SLA dashboard |
| `T` | Timeline dock |
| `W` | Target workbench |
| `/` | AIP chat |
| `Ctrl+K` / `Cmd+K` | Command palette |
| `Ctrl+Shift+A` / `Cmd+Shift+A` | Colorblind mode |

## Outstanding (deferred / weeks-of-work)

These items are tracked in `.ralph/fix_plan.md` but were not in scope
for the iteration 1-22 sweep:

- Real Romania DEM tiles for the pyrender backdrop (one-shot
  `build_terrain_mesh.py` per theater).
- Apollo-equivalent edge-replication checkpoint sync.
- Playwright visual-regression goldens for each Maven-parity panel.
- `trivy fs` once a Dockerfile lands; `osv-scanner` for cross-ecosystem
  CVE coverage.
- DoD CAC/PIV smart-card auth as a JWT alternative.
- FIPS-140-3 validated cryptography swap (depends on third-party).
- 3-year audit log retention (depends on storage policy).
