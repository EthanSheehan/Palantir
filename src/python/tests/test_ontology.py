"""
test_ontology.py
================
Coverage for the new ontology layer (`src/python/ontology/`).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ontology import (
    OntologyService,
    get_object_type,
    list_object_types,
    get_link_type,
    list_link_types,
    get_action_type,
    list_action_types,
)


# -------------- object types --------------


class TestObjectTypeRegistry:
    def test_lists_canonical_types(self):
        types = set(list_object_types())
        assert {
            "UAV", "Target", "EnemyUAV", "Sensor", "Munition",
            "Effector", "Theater", "Mission", "Engagement", "COA",
        }.issubset(types)

    def test_get_returns_spec_with_classification(self):
        uav = get_object_type("UAV")
        assert uav.name == "UAV"
        assert uav.classification == "UNCLASSIFIED"
        assert uav.sim_attribute == "uavs"

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            get_object_type("Bogus")

    def test_enemy_uav_is_cui(self):
        spec = get_object_type("EnemyUAV")
        assert spec.classification == "CUI"


# -------------- link types --------------


class TestLinkTypeRegistry:
    def test_canonical_links(self):
        for name in (
            "UAV-tracks-Target",
            "Sensor-contributes-to-Target",
            "Effector-engages-Target",
            "Engagement-results-in-BDA",
        ):
            spec = get_link_type(name)
            assert spec.predicate
            assert spec.subject_type
            assert spec.object_type

    def test_list_is_sorted(self):
        links = list_link_types()
        assert links == sorted(links)

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            get_link_type("not-a-link")


# -------------- action types --------------


class TestActionTypeRegistry:
    def test_canonical_actions(self):
        names = set(list_action_types())
        for expected in (
            "approve_nomination", "reject_nomination", "authorize_coa",
            "engage", "retask", "request_swarm", "release_swarm",
            "set_persona", "switch_theater",
        ):
            assert expected in names

    def test_authorize_coa_requires_cui(self):
        spec = get_action_type("authorize_coa")
        assert spec.requires_persona == "CUI"

    def test_engage_requires_autonomous(self):
        spec = get_action_type("engage")
        assert spec.min_autonomy_level == "AUTONOMOUS"


# -------------- OntologyService --------------


class _FakeUav:
    def __init__(self, uid, sensors, tracked_target_ids):
        self.id = uid
        self.sensors = sensors
        self.tracked_target_ids = tracked_target_ids


class _FakeTarget:
    def __init__(self, tid, type_, contributions=None):
        self.id = tid
        self.type = type_
        self.sensor_contributions = contributions or []


class _FakeSim:
    def __init__(self):
        self.uavs = {}
        self.targets = {}
        self.enemy_uavs = {}


class TestOntologyService:
    def test_get_uav_by_id(self):
        sim = _FakeSim()
        sim.uavs[7] = _FakeUav(7, ["EO_IR"], [])
        svc = OntologyService(sim)
        u = svc.get("UAV", 7)
        assert u.id == 7

    def test_get_unknown_id_raises(self):
        svc = OntologyService(_FakeSim())
        with pytest.raises(KeyError):
            svc.get("UAV", 99)

    def test_list_returns_all_instances(self):
        sim = _FakeSim()
        for i in (1, 2, 3):
            sim.uavs[i] = _FakeUav(i, [], [])
        svc = OntologyService(sim)
        assert len(svc.list("UAV")) == 3

    def test_uav_tracks_target_link(self):
        sim = _FakeSim()
        sim.uavs[1] = _FakeUav(1, ["EO_IR"], tracked_target_ids=[42, 43])
        sim.targets[42] = _FakeTarget(42, "SAM")
        sim.targets[43] = _FakeTarget(43, "TEL")
        svc = OntologyService(sim)
        out = svc.links("UAV", 1, "UAV-tracks-Target")
        assert len(out) == 2
        ids = {pair[1].id for pair in out}
        assert ids == {42, 43}

    def test_uav_carries_sensor_link(self):
        sim = _FakeSim()
        sim.uavs[1] = _FakeUav(1, ["EO_IR", "SAR"], [])
        svc = OntologyService(sim)
        out = svc.links("UAV", 1, "UAV-carries-Sensor")
        sensor_names = [pair[1] for pair in out]
        assert sensor_names == ["EO_IR", "SAR"]

    def test_sensor_contributes_to_target_traversal(self):
        sim = _FakeSim()
        sim.targets[1] = _FakeTarget(1, "SAM", contributions=[
            {"sensor_type": "SIGINT", "uav_id": 4, "confidence": 0.9},
        ])
        sim.targets[2] = _FakeTarget(2, "TEL", contributions=[
            {"sensor_type": "EO_IR", "uav_id": 5, "confidence": 0.7},
        ])
        svc = OntologyService(sim)
        out = svc.links("Sensor", "SIGINT", "Sensor-contributes-to-Target")
        assert len(out) == 1
        assert out[0][1].id == 1

    def test_apply_unknown_action_raises(self):
        svc = OntologyService(_FakeSim())
        with pytest.raises(KeyError):
            svc.apply("totally_made_up_action")

    def test_apply_unimplemented_returns_clean_result(self):
        svc = OntologyService(_FakeSim())
        out = svc.apply("approve_nomination", target_id=99)
        # Coverage is intentionally narrow this iteration; service returns
        # a clean shape instead of raising.
        assert out["ok"] is False
        assert out["action"] == "approve_nomination"
        assert "error" in out

    def test_schema_includes_all_three_layers(self):
        svc = OntologyService(_FakeSim())
        s = svc.schema()
        assert "object_types" in s
        assert "link_types" in s
        assert "action_types" in s
        assert "UAV" in s["object_types"]


class TestSynthesisQueryAgentMigration:
    """Synthesis query agent reads through OntologyService — verify
    parity with the legacy `_sim_summary` shape.
    """

    @pytest.mark.asyncio
    async def test_summary_shape_via_ontology_matches_direct(self):
        from agents.registry import _sim_summary, _ontology_sim_summary
        sim = _FakeSim()
        sim.uavs[1] = _FakeUav(1, ["EO_IR"], [42])
        sim.targets[42] = _FakeTarget(42, "SAM")
        sim.targets[42].state = "NOMINATED"
        sim.targets[42].fused_confidence = 0.78
        sim.targets[42].sensor_count = 3
        sim.targets[100] = _FakeTarget(100, "TEL")
        sim.targets[100].state = "DETECTED"
        sim.targets[100].fused_confidence = 0.4
        sim.targets[100].sensor_count = 1

        direct = _sim_summary(sim)
        via_ont = _ontology_sim_summary(sim)
        # The ontology variant adds a `_via` marker but otherwise mirrors
        # every field from the direct summary.
        assert via_ont.get("_via") == "ontology"
        for key in ("uav_count", "target_count", "targets_by_state", "targets_by_type"):
            assert via_ont[key] == direct[key]
        assert {n["id"] for n in via_ont["nominated"]} == {n["id"] for n in direct["nominated"]}

    @pytest.mark.asyncio
    async def test_synthesis_handler_uses_ontology(self):
        from agents.registry import get_agent
        sim = _FakeSim()
        sim.uavs[1] = _FakeUav(1, ["EO_IR"], [])
        sim.targets[7] = _FakeTarget(7, "SAM")
        sim.targets[7].state = "DETECTED"
        sim.targets[7].fused_confidence = 0.5
        sim.targets[7].sensor_count = 2

        class Ctx:
            llm_adapter = None
            theater_name = "test"
        ctx = Ctx()
        ctx.sim = sim

        handler = get_agent("synthesis_query_agent")
        text, meta = await handler("status?", ctx)
        # Heuristic fallback path (no LLM in test env): meta carries the
        # by_state map sourced through the ontology summary.
        assert "by_state" in meta or "uav_count" in meta
        assert "1 UAVs" in text or "uav" in text.lower()
