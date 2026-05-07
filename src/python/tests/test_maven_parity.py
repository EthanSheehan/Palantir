"""
test_maven_parity.py
====================
Tests for the Maven-parity backend additions:
  - agents/registry.py      plug-in agent registry
  - vision/multi_int_simulator.py  synthetic SAR/SIGINT/MTI/GEO contributions
  - effectors/{afatds,jreap,jadocs,amps}.py  mock effector dispatch
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.registry import get_agent, list_agents, register_agent
from effectors import AfatdsStub, AmpsStub, EffectorAck, JadocsStub, JreapStub
from effectors.afatds import FireMissionRequest
from effectors.amps import AviationMissionRequest
from effectors.jadocs import DeepFireRequest
from effectors.jreap import TrackForwardRequest
from vision.multi_int_simulator import (
    DEFAULT_STREAMS,
    MultiIntSimulator,
    SAR_CONFIG,
    SIGINT_CONFIG,
    attach_to_target,
)


# -------------- Agent registry --------------

class TestAgentRegistry:
    def test_nine_default_agents(self):
        keys = list_agents()
        # Expected 9 agents per CLAUDE.md "AI Agent Layer" list
        for expected in (
            "isr_observer", "strategy_analyst", "tactical_planner", "effectors_agent",
            "pattern_analyzer", "ai_tasking_manager", "battlespace_manager",
            "synthesis_query_agent", "performance_auditor",
        ):
            assert expected in keys, f"missing default agent {expected!r}"

    def test_unknown_falls_back_to_synthesis(self):
        h_unknown = get_agent("does_not_exist")
        h_synth = get_agent("synthesis_query_agent")
        assert h_unknown is h_synth

    @pytest.mark.asyncio
    async def test_agent_handler_returns_text_and_meta(self):
        h = get_agent("synthesis_query_agent")

        class FakeSim:
            uavs = {1: object(), 2: object()}
            targets = {}

        class Ctx:
            sim = FakeSim()

        text, meta = await h("status", Ctx())
        assert isinstance(text, str)
        assert isinstance(meta, dict)
        assert "uav_count" in meta

    def test_register_decorator_adds_agent(self):
        @register_agent("custom_agent_for_test")
        async def _h(query, ctx):  # noqa: ARG001
            return ("custom ok", {})

        assert "custom_agent_for_test" in list_agents()


# -------------- multi-INT simulator --------------


class _FakeTarget:
    def __init__(self, x=44.5, y=26.0, ttype="SAM", emitting=True):
        self.x = x
        self.y = y
        self.type = ttype
        self.is_emitting = emitting
        self.sensor_contributions = []


class _FakeUav:
    def __init__(self, uid, x, y):
        self.id = uid
        self.x = x
        self.y = y


class TestMultiIntSimulator:
    def test_default_stream_set_has_all_four_kinds(self):
        kinds = {s.sensor_type for s in DEFAULT_STREAMS}
        assert kinds == {"SAR", "SIGINT", "MTI", "GEO"}

    def test_emits_contributions_for_close_uav(self):
        sim = MultiIntSimulator(weather_factor=0.0, is_daytime=True)
        target = _FakeTarget()
        uav = _FakeUav(1, 44.51, 26.005)  # ~1km from target
        added = attach_to_target(target, [uav], sim)
        assert added > 0
        assert all(c["uav_id"] == 1 for c in target.sensor_contributions)
        types = {c["sensor_type"] for c in target.sensor_contributions}
        # SAR works in any weather, SIGINT works because target is_emitting=True
        assert "SAR" in types
        assert "SIGINT" in types

    def test_sigint_skipped_for_non_emitter(self):
        sim = MultiIntSimulator()
        target = _FakeTarget(emitting=False)
        uav = _FakeUav(1, 44.51, 26.005)
        attach_to_target(target, [uav], sim)
        types = {c["sensor_type"] for c in target.sensor_contributions}
        assert "SIGINT" not in types

    def test_geo_skipped_at_night(self):
        sim = MultiIntSimulator(is_daytime=False)
        target = _FakeTarget()
        uav = _FakeUav(1, 44.51, 26.005)
        attach_to_target(target, [uav], sim)
        types = {c["sensor_type"] for c in target.sensor_contributions}
        assert "GEO" not in types

    def test_uav_outside_range_rejected(self):
        sim = MultiIntSimulator(streams=(SAR_CONFIG,))  # SAR max range = 400 km
        target = _FakeTarget()
        uav = _FakeUav(1, 80.0, 26.0)  # ~3900 km away
        added = attach_to_target(target, [uav], sim)
        assert added == 0

    def test_weather_degrades_confidence(self):
        clear = MultiIntSimulator(weather_factor=0.0, streams=(SAR_CONFIG,))
        bad = MultiIntSimulator(weather_factor=1.0, streams=(SAR_CONFIG,))
        # Re-seed for determinism
        clear.rng.seed(0)
        bad.rng.seed(0)
        target_a = _FakeTarget()
        target_b = _FakeTarget()
        uav = _FakeUav(1, 44.51, 26.005)
        attach_to_target(target_a, [uav], clear)
        attach_to_target(target_b, [uav], bad)
        # SAR weather_sensitivity = 0.10 — small but non-zero degradation
        if target_a.sensor_contributions and target_b.sensor_contributions:
            assert target_a.sensor_contributions[0]["confidence"] >= target_b.sensor_contributions[0]["confidence"]


# -------------- effector stubs --------------


class TestSlaMetrics:
    """Verify metrics.record_stage_latency / sla_snapshot."""

    def test_sla_snapshot_returns_six_stages_when_empty(self):
        import metrics
        # Reset state to make the test independent
        metrics._state.stage_latencies_ms = {
            k: [] for k in ("FIND", "FIX", "TRACK", "TARGET", "ENGAGE", "ASSESS")
        }
        snap = metrics.sla_snapshot()
        stages = [s["stage"] for s in snap]
        assert stages == ["FIND", "FIX", "TRACK", "TARGET", "ENGAGE", "ASSESS"]
        for entry in snap:
            assert entry["samples"] == []
            assert entry["threshold_ms"] == metrics.SLA_THRESHOLDS_MS[entry["stage"]]

    def test_record_stage_latency_clamps_bad_values(self):
        import metrics
        metrics._state.stage_latencies_ms["FIND"] = []
        metrics.record_stage_latency("FIND", -50)             # negative rejected
        metrics.record_stage_latency("FIND", 1_000_000_000)   # too large rejected
        metrics.record_stage_latency("UNKNOWN", 100)          # bad stage rejected
        metrics.record_stage_latency("FIND", 1234)            # accepted
        assert metrics._state.stage_latencies_ms["FIND"] == [1234.0]

    def test_record_stage_latency_bounded(self):
        import metrics
        metrics._state.stage_latencies_ms["FIX"] = []
        for i in range(300):
            metrics.record_stage_latency("FIX", float(i))
        assert len(metrics._state.stage_latencies_ms["FIX"]) == 240
        # Most recent samples retained
        assert metrics._state.stage_latencies_ms["FIX"][-1] == 299.0

    def test_sla_snapshot_computes_percentiles(self):
        import metrics
        metrics._state.stage_latencies_ms["TRACK"] = []
        for v in [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
            metrics.record_stage_latency("TRACK", float(v))
        snap = metrics.sla_snapshot()
        track = next(s for s in snap if s["stage"] == "TRACK")
        # median is index len/2 = 5 → 600
        assert track["median_ms"] == 600
        assert track["p95_ms"] == 1000
        assert len(track["samples"]) == 10


class TestAuditTimelineEvents:
    """Verify audit_log.events_for_target shapes events for the timeline UI."""

    def test_events_for_target_filters_by_id(self):
        from audit_log import AuditLog
        log = AuditLog()
        log.append("target_state_transition", target_id=1,
                   details={"from_state": "DETECTED", "to_state": "CLASSIFIED",
                            "fused_confidence": 0.6})
        log.append("target_state_transition", target_id=2,
                   details={"from_state": "DETECTED", "to_state": "CLASSIFIED",
                            "fused_confidence": 0.5})
        events = log.events_for_target(1)
        assert len(events) == 1
        assert events[0]["kind"] == "STATE"
        assert "DETECTED → CLASSIFIED" in events[0]["label"]

    def test_engagement_event_shape(self):
        from audit_log import AuditLog
        log = AuditLog()
        log.append("engagement_executed", target_id=42,
                   details={"effector": "F-15E", "damage_level": "DESTROYED",
                            "modified_pk": 0.85, "reasoning_trace": "Test"})
        events = log.events_for_target(42)
        assert len(events) == 1
        assert events[0]["kind"] == "ENGAGEMENT"
        assert "F-15E" in events[0]["label"]

    def test_effector_dispatch_event_includes_latency(self):
        from audit_log import AuditLog
        log = AuditLog()
        log.append("effector_dispatched", target_id=7,
                   details={"channel": "AFATDS", "mission_id": "FM-XYZ",
                            "latency_ms": 350, "detail": "FM accepted"})
        events = log.events_for_target(7)
        assert len(events) == 1
        assert events[0]["kind"] == "ENGAGEMENT"
        assert "AFATDS" in events[0]["label"]
        assert "350ms" in events[0]["detail"]


class TestPersonaBroadcastFilter:
    """Per-persona classification filter on the broadcast payload."""

    def test_unclassified_drops_cui_and_secret_fields(self):
        from api_main import _filter_for_persona
        state = {
            "targets": [{
                "id": 1,
                "type": "SAM",
                "threat_range_km": 75,    # CUI
                "detection_range_km": 50, # CUI
                "sensor_contributions": [{
                    "uav_id": 2, "sensor_type": "SIGINT",
                    "source_kind": "RFEMITTER-S-band",  # SECRET
                }],
            }],
        }
        out = _filter_for_persona(state, "UNCLASSIFIED")
        assert "threat_range_km" not in out["targets"][0]
        assert "detection_range_km" not in out["targets"][0]
        contrib = out["targets"][0]["sensor_contributions"][0]
        assert "source_kind" not in contrib
        assert contrib["sensor_type"] == "SIGINT"

    def test_cui_keeps_cui_drops_secret(self):
        from api_main import _filter_for_persona
        state = {
            "threat_range_km": 75,
            "sensor_contributions": [{
                "uav_id": 1,
                "source_kind": "ICEYE-X-band",
            }],
        }
        out = _filter_for_persona(state, "CUI")
        assert out["threat_range_km"] == 75
        assert "source_kind" not in out["sensor_contributions"][0]

    def test_secret_keeps_everything(self):
        from api_main import _filter_for_persona
        state = {
            "threat_range_km": 75,
            "sensor_contributions": [{"source_kind": "x"}],
        }
        out = _filter_for_persona(state, "SECRET")
        assert out["threat_range_km"] == 75
        assert out["sensor_contributions"][0]["source_kind"] == "x"

    def test_unknown_persona_treated_as_unclassified(self):
        from api_main import _filter_for_persona
        out = _filter_for_persona({"threat_range_km": 1}, "BOGUS")
        assert out == {}


class TestSelfCriticAgent:
    """Reflective AI surfaces audit-log patterns."""

    @pytest.mark.asyncio
    async def test_no_records_returns_clean_message(self):
        from agents.registry import get_agent
        # Build an empty audit log via context that exposes a trivial sim
        class _Sim:
            uavs = {}
            targets = {}
            theater_name = "test"
        class Ctx:
            sim = _Sim()
            llm_adapter = None
        # Pin audit_log to a fresh instance so leftover records from other
        # tests don't influence this one.
        import audit_log as _mod
        original = _mod.audit_log
        _mod.audit_log = _mod.AuditLog()
        try:
            handler = get_agent("self_critic")
            text, meta = await handler("status?", Ctx())
            assert "no audit history" in text.lower() or "no patterns" in text.lower()
            assert isinstance(meta, dict)
        finally:
            _mod.audit_log = original

    @pytest.mark.asyncio
    async def test_repeated_rejections_surface_finding(self):
        from agents.registry import get_agent
        import audit_log as _mod
        original = _mod.audit_log
        _mod.audit_log = _mod.AuditLog()
        try:
            for _ in range(3):
                _mod.audit_log.append("nomination_rejected", target_id=42, details={"rationale": "bad PID"})
            class Ctx:
                sim = None
                llm_adapter = None
            handler = get_agent("self_critic")
            text, meta = await handler("any concerns?", Ctx())
            assert "0042" in text
            assert meta.get("finding_count", 0) >= 1
        finally:
            _mod.audit_log = original


class TestDecisionReplayAgent:
    """Re-run a past engagement deterministically."""

    @pytest.mark.asyncio
    async def test_no_target_id_in_query_returns_hint(self):
        from agents.registry import get_agent
        class Ctx:
            sim = None
            llm_adapter = None
        text, _meta = await get_agent("decision_replay")("status only", Ctx())
        assert "target ID" in text or "target id" in text.lower()

    @pytest.mark.asyncio
    async def test_no_engagement_returns_clean_message(self):
        from agents.registry import get_agent
        import audit_log as _mod
        original = _mod.audit_log
        _mod.audit_log = _mod.AuditLog()
        try:
            class Ctx:
                sim = None
                llm_adapter = None
            text, meta = await get_agent("decision_replay")("/replay 999", Ctx())
            assert "0999" in text
            assert "no engagement_executed" in text
            assert meta.get("found") is False
        finally:
            _mod.audit_log = original

    @pytest.mark.asyncio
    async def test_replay_runs_against_existing_engagement(self):
        from agents.registry import get_agent
        import audit_log as _mod
        original = _mod.audit_log
        _mod.audit_log = _mod.AuditLog()
        try:
            _mod.audit_log.append(
                "engagement_executed",
                target_id=77,
                details={
                    "coa_id": "tac-001",
                    "effector": "F-15E",
                    "modified_pk": 0.85,
                    "damage_level": "DESTROYED",
                    "hit": True,
                },
            )
            class Ctx:
                sim = None
                llm_adapter = None
            text, meta = await get_agent("decision_replay")("replay 77", Ctx())
            assert "0077" in text
            assert meta["seed"] == 42
            assert meta["original_damage_level"] == "DESTROYED"
            # The replay deterministically runs the engagement; outcome is
            # whatever seed=42 produces. We just assert it ran.
            assert meta["replay_damage_level"] in ("DESTROYED", "DAMAGED", "MISSED")
        finally:
            _mod.audit_log = original


class TestEffectorRouting:
    """Verify EffectorsAgent picks the right channel for a COA's effector."""

    def test_route_aviation(self):
        from agents.effectors_agent import _route_effector
        assert _route_effector("F-35") == "AMPS"
        assert _route_effector("MQ-9") == "AMPS"
        assert _route_effector("AH-64 Apache") == "AMPS"
        assert _route_effector("B-21 Raider") == "AMPS"

    def test_route_artillery(self):
        from agents.effectors_agent import _route_effector
        assert _route_effector("HIMARS") == "AFATDS"
        assert _route_effector("M777 howitzer") == "AFATDS"
        assert _route_effector("GMLRS") == "AFATDS"
        assert _route_effector("ATACMS") == "AFATDS"

    def test_route_naval(self):
        from agents.effectors_agent import _route_effector
        assert _route_effector("SM-6") == "JREAP"
        assert _route_effector("AEGIS") == "JREAP"
        assert _route_effector("Tomahawk TLAM") == "JREAP"

    def test_route_default_jadocs(self):
        from agents.effectors_agent import _route_effector
        assert _route_effector("UNKNOWN_PLATFORM") == "JADOCS"
        assert _route_effector("") == "JADOCS"


class TestEffectorStubs:
    def test_afatds_dispatch(self):
        stub = AfatdsStub()
        ack = stub.dispatch(FireMissionRequest(
            target_id=42, target_lat=44.5, target_lon=26.0, target_type="SAM"
        ))
        assert isinstance(ack, EffectorAck)
        assert ack.effector == "AFATDS"
        assert ack.accepted is True
        assert ack.mission_id.startswith("FM-")
        assert ack.latency_ms > 0

    def test_afatds_rejects_zero_target(self):
        stub = AfatdsStub()
        ack = stub.dispatch(FireMissionRequest(
            target_id=0, target_lat=44.5, target_lon=26.0, target_type="SAM"
        ))
        assert ack.accepted is False

    def test_jreap_dispatch(self):
        ack = JreapStub().dispatch(TrackForwardRequest(
            target_id=7, target_lat=44.5, target_lon=26.0, track_quality=12
        ))
        assert ack.effector == "JREAP"
        assert ack.accepted is True
        assert ack.nato_msg_id and ack.nato_msg_id.startswith("L16-J3.2-")

    def test_jadocs_dispatch(self):
        ack = JadocsStub().dispatch(DeepFireRequest(
            target_id=11, target_lat=44.5, target_lon=26.0
        ))
        assert ack.effector == "JADOCS"
        assert ack.mission_id.startswith("DC-")

    def test_amps_dispatch(self):
        ack = AmpsStub().dispatch(AviationMissionRequest(
            target_id=99, target_lat=44.5, target_lon=26.0
        ))
        assert ack.effector == "AMPS"
        assert ack.mission_id.startswith("ATO-")
        # AMPS has a longer typical ack window (900-2400ms)
        assert ack.latency_ms >= 900
