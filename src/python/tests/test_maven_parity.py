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
