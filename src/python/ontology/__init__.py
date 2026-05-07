"""
ontology package
================
Foundry/Gotham-style ontology primitives for Grid-Sentinel.

Layered the *correct* way for a defence C2 system: object types describe
what exists, link types describe how objects relate, action types describe
what the system can do, and `OntologyService` wraps the live
SimulationModel to expose a uniform `get / links / apply` API.

This is additive — agents and panels keep reading from `sim.uavs` /
`sim.targets` directly. Future migrations (start with
`synthesis_query_agent` per the blueprint) can opt in to the typed API.
"""
from .object_types import (
    OBJECT_TYPES,
    ObjectTypeSpec,
    get_object_type,
    list_object_types,
)
from .link_types import (
    LINK_TYPES,
    LinkTypeSpec,
    get_link_type,
    list_link_types,
)
from .action_types import (
    ACTION_TYPES,
    ActionTypeSpec,
    get_action_type,
    list_action_types,
)
from .service import OntologyService

__all__ = [
    "OBJECT_TYPES",
    "ObjectTypeSpec",
    "get_object_type",
    "list_object_types",
    "LINK_TYPES",
    "LinkTypeSpec",
    "get_link_type",
    "list_link_types",
    "ACTION_TYPES",
    "ActionTypeSpec",
    "get_action_type",
    "list_action_types",
    "OntologyService",
]
