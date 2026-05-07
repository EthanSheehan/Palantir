"""
ontology/service.py
===================
`OntologyService` wraps the live SimulationModel and exposes a uniform
`get / links / apply` API over the ontology primitives. Designed so that
agents can be migrated one-at-a-time off direct `sim.targets / sim.uavs`
access without changing the broadcast loop or test fixtures.

Per the blueprint's Phase 3.1:
  > Migrate one agent (start with synthesis_query_agent) to read from
  > OntologyService instead of sim.targets/uavs directly.

This iteration delivers the service. Migration of an agent is a
follow-up task tracked in .ralph/fix_plan.md.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from .object_types import OBJECT_TYPES, get_object_type
from .link_types import LINK_TYPES, get_link_type
from .action_types import ACTION_TYPES, get_action_type

logger = logging.getLogger(__name__)


class OntologyService:
    """Live view over a SimulationModel exposing ontology-typed access.

    The service does *not* own state; every call resolves against the
    underlying `sim` object. This means the answer is always current —
    no cache invalidation problems.
    """

    def __init__(self, sim: Any):
        self._sim = sim

    # ------------------------------------------------------------------
    # Query side: get / links
    # ------------------------------------------------------------------

    def get(self, object_type: str, id: int | str) -> Any:
        """Resolve a single object instance by type + id.

        Returns the live SimulationModel instance (UAV, Target, EnemyUAV,
        ...) — not a dict — so callers can use existing typed attributes.
        Raises KeyError if the instance doesn't exist.
        """
        spec = get_object_type(object_type)
        if spec.sim_attribute is None:
            raise KeyError(f"Object type {object_type!r} has no live sim binding")
        store = getattr(self._sim, spec.sim_attribute, None) or {}
        try:
            id = int(id)  # type: ignore[assignment]
        except (TypeError, ValueError):
            pass
        if id in store:
            return store[id]
        raise KeyError(f"{object_type} {id!r} not found")

    def list(self, object_type: str) -> list:
        """Return every live instance of `object_type`."""
        spec = get_object_type(object_type)
        if spec.sim_attribute is None:
            return []
        store = getattr(self._sim, spec.sim_attribute, None) or {}
        if hasattr(store, "values"):
            return list(store.values())
        return list(store)

    def links(
        self,
        object_type: str,
        id: int | str,
        link_type: str,
    ) -> list[tuple[str, Any]]:
        """Traverse a link from a specific object.

        Returns a list of `(target_object_type, target_object)` tuples.
        Empty list if no links match. Raises KeyError on unknown types.
        """
        get_link_type(link_type)  # validate

        # `Sensor` is a *virtual* object type keyed by its sensor_type
        # string — there's no SimulationModel.sensors store. Resolve it
        # without calling self.get().
        if link_type == "Sensor-contributes-to-Target":
            sensor_type = str(id)
            results: list[tuple[str, Any]] = []
            for t in self.list("Target"):
                contribs = getattr(t, "sensor_contributions", []) or []
                for c in contribs:
                    sensor_id = c.get("sensor_type") if isinstance(c, dict) else getattr(c, "sensor_type", None)
                    if sensor_id == sensor_type:
                        results.append(("Target", t))
                        break
            return results

        # All other link types resolve a concrete subject first
        subject = self.get(object_type, id)

        if link_type == "UAV-tracks-Target":
            target_ids = list(getattr(subject, "tracked_target_ids", []) or [])
            return [("Target", t) for t in self._resolve_many("Target", target_ids)]

        if link_type == "UAV-carries-Sensor":
            sensors = list(getattr(subject, "sensors", []) or [])
            return [("Sensor", s) for s in sensors]

        # Reverse traversal of UAV-tracks-Target — given a Target, who
        # tracks it?
        if link_type == "Effector-engages-Target":
            return []  # Engagements live in audit_log; query separately

        # Unknown traversal — return empty (caller can branch on shape).
        logger.warning("ontology_links_unsupported", extra={"link_type": link_type})
        return []

    def _resolve_many(self, object_type: str, ids: Iterable) -> list:
        out = []
        for x in ids:
            try:
                out.append(self.get(object_type, x))
            except KeyError:
                continue
        return out

    # ------------------------------------------------------------------
    # Action side: apply
    # ------------------------------------------------------------------

    def apply(self, action_name: str, **kwargs) -> dict:
        """Execute an action against the simulation, audit-logging the
        invocation. Returns `{ok: bool, action: str, kwargs, error?}`.

        This is the *typed* alternative to building free-form WS messages.
        A migrated agent can call `ontology.apply("approve_nomination",
        target_id=42)` instead of fabricating a WebSocket payload.
        """
        spec = get_action_type(action_name)
        # Audit every apply() — even if the underlying handler also audits.
        # This is the operator-action source of truth.
        try:
            from audit_log import audit_log as _audit
            _audit.append(
                action_type=f"ontology_apply_{action_name}",
                target_id=kwargs.get("target_id"),
                drone_id=kwargs.get("drone_id"),
                details={"affects": list(spec.affects_types), "kwargs": dict(kwargs)},
            )
        except Exception:  # noqa: BLE001
            pass

        # Dispatch to the appropriate sim/handler entry point. Coverage
        # is intentionally narrow this iteration — proves the typed API
        # works end-to-end without rewiring the WebSocket layer.
        sim = self._sim
        if action_name == "switch_theater":
            theater = kwargs.get("theater")
            if not theater:
                return {"ok": False, "action": action_name, "error": "theater required"}
            try:
                from sim_engine import SimulationModel
                from theater_loader import load_theater
                new_sim = SimulationModel(theater_name=theater)
                new_sim.theater = load_theater(theater)
                for attr in (
                    "theater_name", "theater", "uavs", "targets",
                    "enemy_uavs", "bounds", "grid", "environment",
                ):
                    if hasattr(new_sim, attr):
                        setattr(sim, attr, getattr(new_sim, attr))
                return {"ok": True, "action": action_name, "theater": theater}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "action": action_name, "error": str(exc)}

        if action_name == "request_swarm":
            target_id = kwargs.get("target_id")
            target = sim.targets.get(target_id) if hasattr(sim, "targets") else None
            if target is None:
                return {"ok": False, "action": action_name, "error": "target not found"}
            sim.swarm_coordinator.evaluate_and_assign(
                [target], list(sim.uavs.values()), force=True
            )
            return {"ok": True, "action": action_name, "target_id": target_id}

        # Future: hook the rest of the actions through to handlers. For
        # now, return a deterministic "not implemented" so callers can
        # detect coverage gaps without exceptions.
        return {"ok": False, "action": action_name, "error": "not_implemented_in_service"}

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def schema(self) -> dict:
        """Return the full ontology schema (object/link/action types)."""
        return {
            "object_types": {k: vars(v) for k, v in OBJECT_TYPES.items()},
            "link_types": {k: vars(v) for k, v in LINK_TYPES.items()},
            "action_types": {k: vars(v) for k, v in ACTION_TYPES.items()},
        }
