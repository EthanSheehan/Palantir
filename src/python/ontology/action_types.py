"""
ontology/action_types.py
========================
Registry of every action the system can execute against the ontology.
Mirrors Foundry's "Ontology function" / "Apply action" concept. Each
action declares the minimum autonomy level required, the audit detail
template, and which object types it operates on.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionTypeSpec:
    name: str
    affects_types: tuple[str, ...]   # which object types this action mutates
    min_autonomy_level: str          # MANUAL | SUPERVISED | AUTONOMOUS
    requires_persona: str = "UNCLASSIFIED"  # min persona to invoke
    description: str = ""


ACTION_TYPES: dict[str, ActionTypeSpec] = {
    "nominate": ActionTypeSpec(
        name="nominate",
        affects_types=("Target",),
        min_autonomy_level="SUPERVISED",
        description="Promote a VERIFIED target to the NOMINATED state, requesting operator approval.",
    ),
    "approve_nomination": ActionTypeSpec(
        name="approve_nomination",
        affects_types=("Target",),
        min_autonomy_level="MANUAL",
        description="Operator gate-1 approval; transitions NOMINATED → AUTHORIZED.",
    ),
    "reject_nomination": ActionTypeSpec(
        name="reject_nomination",
        affects_types=("Target",),
        min_autonomy_level="MANUAL",
        description="Operator rejection; routes back to VERIFIED with cooldown.",
    ),
    "authorize_coa": ActionTypeSpec(
        name="authorize_coa",
        affects_types=("COA", "Engagement"),
        min_autonomy_level="MANUAL",
        requires_persona="CUI",
        description="Operator gate-2 approval; selects which COA to execute.",
    ),
    "engage": ActionTypeSpec(
        name="engage",
        affects_types=("Target", "Engagement"),
        min_autonomy_level="AUTONOMOUS",
        requires_persona="CUI",
        description="Dispatch the authorized COA through AFATDS / JREAP / JADOCS / AMPS.",
    ),
    "retask": ActionTypeSpec(
        name="retask",
        affects_types=("UAV", "Sensor"),
        min_autonomy_level="SUPERVISED",
        description="Redirect a sensor / UAV to a different AOI for confirmation.",
    ),
    "request_swarm": ActionTypeSpec(
        name="request_swarm",
        affects_types=("Target", "UAV"),
        min_autonomy_level="SUPERVISED",
        description="Ask swarm_coordinator to assign multiple UAVs to a target.",
    ),
    "release_swarm": ActionTypeSpec(
        name="release_swarm",
        affects_types=("Target", "UAV"),
        min_autonomy_level="MANUAL",
        description="Release a swarm so its UAVs return to IDLE / SEARCH.",
    ),
    "set_roe": ActionTypeSpec(
        name="set_roe",
        affects_types=("Theater",),
        min_autonomy_level="MANUAL",
        requires_persona="CUI",
        description="Hot-swap the loaded ROE rule set.",
    ),
    "set_persona": ActionTypeSpec(
        name="set_persona",
        affects_types=(),
        min_autonomy_level="MANUAL",
        description="Switch the operator's classification persona (UNCLASS/CUI/SECRET).",
    ),
    "switch_theater": ActionTypeSpec(
        name="switch_theater",
        affects_types=("Theater", "UAV", "Target"),
        min_autonomy_level="MANUAL",
        description="Hot-swap the live SimulationModel theater (Romania / Baltic / SCS).",
    ),
}


def get_action_type(name: str) -> ActionTypeSpec:
    spec = ACTION_TYPES.get(name)
    if spec is None:
        raise KeyError(f"Unknown action type: {name!r}")
    return spec


def list_action_types() -> list[str]:
    return sorted(ACTION_TYPES.keys())
