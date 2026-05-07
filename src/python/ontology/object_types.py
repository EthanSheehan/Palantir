"""
ontology/object_types.py
========================
Registry of every object type in the Grid-Sentinel domain. Each entry tags
its **classification tier** and **audit policy** — the two cross-cutting
concerns the rest of the platform binds against.

Mirrors Foundry's "Ontology object type" concept. New object types added
here automatically show up in `list_object_types()` and can be looked up
by callers that don't know the type at compile time.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectTypeSpec:
    name: str
    plural: str
    classification: str          # min tier required to read full payload
    audit_policy: str            # "ALL", "STATE_TRANSITIONS", or "OPERATOR_ONLY"
    description: str
    sim_attribute: str | None = None   # how to find live instances on SimulationModel


OBJECT_TYPES: dict[str, ObjectTypeSpec] = {
    "UAV": ObjectTypeSpec(
        name="UAV",
        plural="UAVs",
        classification="UNCLASSIFIED",
        audit_policy="STATE_TRANSITIONS",
        description="Friendly unmanned aerial vehicle. Tracked targets, fuel state, autonomy level.",
        sim_attribute="uavs",
    ),
    "Target": ObjectTypeSpec(
        name="Target",
        plural="Targets",
        classification="UNCLASSIFIED",
        audit_policy="STATE_TRANSITIONS",
        description="Detected red-force entity progressing through F2T2EA.",
        sim_attribute="targets",
    ),
    "EnemyUAV": ObjectTypeSpec(
        name="EnemyUAV",
        plural="EnemyUAVs",
        classification="CUI",
        audit_policy="STATE_TRANSITIONS",
        description="Adversary unmanned platform. Behavior + threat assessment is CUI.",
        sim_attribute="enemy_uavs",
    ),
    "Sensor": ObjectTypeSpec(
        name="Sensor",
        plural="Sensors",
        classification="UNCLASSIFIED",
        audit_policy="OPERATOR_ONLY",
        description="Sensor payload on a UAV: EO/IR, SAR, SIGINT, MTI, GEOINT.",
    ),
    "Munition": ObjectTypeSpec(
        name="Munition",
        plural="Munitions",
        classification="CUI",
        audit_policy="OPERATOR_ONLY",
        description="Air-, ground-, or sea-launched weapon catalogued for COA generation.",
    ),
    "Effector": ObjectTypeSpec(
        name="Effector",
        plural="Effectors",
        classification="UNCLASSIFIED",
        audit_policy="OPERATOR_ONLY",
        description="Aviation/artillery/naval platform that delivers a munition. AFATDS/JREAP/JADOCS/AMPS dispatch.",
    ),
    "Theater": ObjectTypeSpec(
        name="Theater",
        plural="Theaters",
        classification="UNCLASSIFIED",
        audit_policy="OPERATOR_ONLY",
        description="Bounded geographic area of operation with ROE config and launchers.",
    ),
    "Mission": ObjectTypeSpec(
        name="Mission",
        plural="Missions",
        classification="CUI",
        audit_policy="ALL",
        description="Coherent unit of work spanning multiple targets and engagements.",
    ),
    "Engagement": ObjectTypeSpec(
        name="Engagement",
        plural="Engagements",
        classification="CUI",
        audit_policy="ALL",
        description="A specific kinetic event against a target. Includes COA, dispatch ack, BDA.",
    ),
    "COA": ObjectTypeSpec(
        name="COA",
        plural="COAs",
        classification="CUI",
        audit_policy="ALL",
        description="Course of Action — effector + munition + Pk + rationale.",
    ),
}


def get_object_type(name: str) -> ObjectTypeSpec:
    """Look up an object type by name. Raises KeyError if unknown."""
    spec = OBJECT_TYPES.get(name)
    if spec is None:
        raise KeyError(f"Unknown object type: {name!r}")
    return spec


def list_object_types() -> list[str]:
    """Return every registered object type name in stable order."""
    return sorted(OBJECT_TYPES.keys())
