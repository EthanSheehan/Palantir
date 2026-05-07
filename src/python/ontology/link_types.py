"""
ontology/link_types.py
======================
Registry of every (subject, predicate, object) link type. Mirrors
Foundry's "Ontology link type" concept. Allows the AIPChatPanel slash-
commands to traverse relationships ("which UAVs are tracking target #42?")
without binding to a specific data source.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkTypeSpec:
    predicate: str
    subject_type: str
    object_type: str
    description: str
    cardinality: str = "many-to-many"  # "one-to-one", "one-to-many", "many-to-many"


LINK_TYPES: dict[str, LinkTypeSpec] = {
    "UAV-tracks-Target": LinkTypeSpec(
        predicate="tracks",
        subject_type="UAV",
        object_type="Target",
        description="A UAV is contributing sensor confidence to a target's fused track.",
        cardinality="many-to-many",
    ),
    "Sensor-contributes-to-Target": LinkTypeSpec(
        predicate="contributes_to",
        subject_type="Sensor",
        object_type="Target",
        description="A specific sensor (EO_IR/SAR/SIGINT/...) feeds a sensor_contribution.",
        cardinality="many-to-many",
    ),
    "UAV-carries-Sensor": LinkTypeSpec(
        predicate="carries",
        subject_type="UAV",
        object_type="Sensor",
        description="UAV's payload includes this sensor.",
        cardinality="one-to-many",
    ),
    "Effector-engages-Target": LinkTypeSpec(
        predicate="engages",
        subject_type="Effector",
        object_type="Target",
        description="An effector dispatched a kinetic action against a target via AFATDS/JREAP/JADOCS/AMPS.",
        cardinality="many-to-many",
    ),
    "Engagement-results-in-BDA": LinkTypeSpec(
        predicate="results_in_BDA",
        subject_type="Engagement",
        object_type="Target",
        description="An engagement produced a Battle Damage Assessment for the target.",
        cardinality="one-to-one",
    ),
    "COA-generated-by-TacticalPlanner": LinkTypeSpec(
        predicate="generated_by",
        subject_type="COA",
        object_type="Mission",
        description="A COA was produced for a mission by the tactical planner.",
        cardinality="many-to-one",
    ),
    "Theater-bounds-Mission": LinkTypeSpec(
        predicate="bounds",
        subject_type="Theater",
        object_type="Mission",
        description="A theater's bounds + ROE govern this mission.",
        cardinality="one-to-many",
    ),
}


def get_link_type(name: str) -> LinkTypeSpec:
    spec = LINK_TYPES.get(name)
    if spec is None:
        raise KeyError(f"Unknown link type: {name!r}")
    return spec


def list_link_types() -> list[str]:
    return sorted(LINK_TYPES.keys())
