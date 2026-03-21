"""Tests for agents/tactical_planner.py — pure functions and heuristic COA generation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from agents.tactical_planner import (
    TacticalPlannerAgent,
    _build_coa,
    _compute_composite,
    _estimate_time_to_target,
    _haversine_km,
    _risk_from_cost,
    _score_asset,
)
from hitl_manager import CourseOfAction as HITLCourseOfAction
from schemas.ontology import (
    Effector,
    EngagementDecision,
    StrategyAnalystOutput,
    TargetClassification,
    TargetNomination,
    Track,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_effector(name="F-35A", etype="Kinetic", eid="F35-01"):
    return Effector(effector_id=eid, name=name, effector_type=etype, status="Available")


def _make_asset(effector=None, lat=33.5, lon=44.4, pk=0.95, cost=8.5, speed=1960.0, **extras):
    asset = {
        "effector": effector or _make_effector(),
        "lat": lat,
        "lon": lon,
        "pk_rating": pk,
        "cost_index": cost,
        "speed_kmh": speed,
    }
    asset.update(extras)
    return asset


def _make_track(track_id="TRK-001", lat=33.0, lon=44.0, classification="SAM"):
    return Track(
        track_id=track_id,
        lat=lat,
        lon=lon,
        classification=TargetClassification(classification),
        confidence=0.9,
    )


def _make_nomination(track_id="TRK-001", decision="Nominate"):
    return TargetNomination(
        track_id=track_id,
        decision=EngagementDecision(decision),
        roe_compliance=True,
        collateral_risk="LOW",
        reasoning="test",
    )


# ---------------------------------------------------------------------------
# _haversine_km
# ---------------------------------------------------------------------------


class TestHaversineKm:
    def test_same_point_is_zero(self):
        assert _haversine_km(33.0, 44.0, 33.0, 44.0) == 0.0

    def test_known_distance(self):
        # London (51.5, -0.12) to Paris (48.86, 2.35) ≈ 343 km
        dist = _haversine_km(51.5, -0.12, 48.86, 2.35)
        assert 340.0 < dist < 350.0

    def test_symmetry(self):
        d1 = _haversine_km(33.0, 44.0, 34.0, 45.0)
        d2 = _haversine_km(34.0, 45.0, 33.0, 44.0)
        assert abs(d1 - d2) < 0.001

    def test_antipodal(self):
        # Roughly half the earth's circumference
        dist = _haversine_km(0, 0, 0, 180)
        assert 20_000 < dist < 20_100


# ---------------------------------------------------------------------------
# _estimate_time_to_target
# ---------------------------------------------------------------------------


class TestEstimateTimeToTarget:
    def test_uses_time_to_effect_field(self):
        asset = _make_asset(time_to_effect_min=0.5)
        assert _estimate_time_to_target(asset, 33.0, 44.0) == 0.5

    def test_uses_rocket_flight_time(self):
        asset = _make_asset(rocket_flight_time_min=3.5, speed=0.0)
        # time_to_effect_min not present in base, but rocket_flight_time_min is
        del asset["speed_kmh"]  # ensure fallthrough
        asset["speed_kmh"] = 0.0
        # Remove time_to_effect_min if present
        asset.pop("time_to_effect_min", None)
        assert _estimate_time_to_target(asset, 33.0, 44.0) == 3.5

    def test_calculates_from_speed_and_distance(self):
        asset = _make_asset(lat=33.0, lon=44.0, speed=100.0)
        # Target at same location → 0 time
        result = _estimate_time_to_target(asset, 33.0, 44.0)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_zero_speed_returns_inf(self):
        asset = _make_asset(speed=0.0)
        asset.pop("time_to_effect_min", None)
        asset.pop("rocket_flight_time_min", None)
        result = _estimate_time_to_target(asset, 34.0, 45.0)
        assert result == float("inf")

    def test_negative_speed_returns_inf(self):
        asset = _make_asset(speed=-10.0)
        asset.pop("time_to_effect_min", None)
        asset.pop("rocket_flight_time_min", None)
        result = _estimate_time_to_target(asset, 34.0, 45.0)
        assert result == float("inf")


# ---------------------------------------------------------------------------
# _score_asset
# ---------------------------------------------------------------------------


class TestScoreAsset:
    def test_returns_all_fields(self):
        asset = _make_asset()
        result = _score_asset(asset, 33.0, 44.0)
        assert "asset" in result
        assert "time_min" in result
        assert "pk" in result
        assert "cost" in result

    def test_pk_from_asset(self):
        asset = _make_asset(pk=0.88)
        result = _score_asset(asset, 33.0, 44.0)
        assert result["pk"] == 0.88

    def test_cost_from_asset(self):
        asset = _make_asset(cost=3.0)
        result = _score_asset(asset, 33.0, 44.0)
        assert result["cost"] == 3.0

    def test_default_cost(self):
        asset = _make_asset()
        del asset["cost_index"]
        result = _score_asset(asset, 33.0, 44.0)
        assert result["cost"] == 10.0


# ---------------------------------------------------------------------------
# _compute_composite
# ---------------------------------------------------------------------------


class TestComputeComposite:
    def test_higher_pk_higher_score(self):
        s1 = _compute_composite(pk=0.5, time_min=5.0, risk=5.0)
        s2 = _compute_composite(pk=0.9, time_min=5.0, risk=5.0)
        assert s2 > s1

    def test_lower_time_higher_score(self):
        s1 = _compute_composite(pk=0.8, time_min=10.0, risk=5.0)
        s2 = _compute_composite(pk=0.8, time_min=1.0, risk=5.0)
        assert s2 > s1

    def test_lower_risk_higher_score(self):
        s1 = _compute_composite(pk=0.8, time_min=5.0, risk=10.0)
        s2 = _compute_composite(pk=0.8, time_min=5.0, risk=1.0)
        assert s2 > s1

    def test_near_zero_time_no_crash(self):
        result = _compute_composite(pk=0.8, time_min=0.001, risk=5.0)
        assert result > 0

    def test_near_zero_risk_no_crash(self):
        result = _compute_composite(pk=0.8, time_min=5.0, risk=0.001)
        assert result > 0


# ---------------------------------------------------------------------------
# _risk_from_cost
# ---------------------------------------------------------------------------


class TestRiskFromCost:
    def test_clamps_low(self):
        assert _risk_from_cost(0.0) == 1.0
        assert _risk_from_cost(-5.0) == 1.0

    def test_clamps_high(self):
        assert _risk_from_cost(15.0) == 10.0

    def test_passthrough(self):
        assert _risk_from_cost(5.0) == 5.0
        assert _risk_from_cost(1.0) == 1.0
        assert _risk_from_cost(10.0) == 10.0


# ---------------------------------------------------------------------------
# _build_coa
# ---------------------------------------------------------------------------


class TestBuildCoa:
    def test_builds_coa_with_correct_fields(self):
        asset = _make_asset()
        scored = {"asset": asset, "time_min": 5.5, "pk": 0.95, "cost": 8.5}
        coa = _build_coa(scored, "fastest", "TRK-001", "test rationale")
        assert coa.coa_type == "fastest"
        assert coa.target_track_id == "TRK-001"
        assert coa.time_to_target_minutes == 5.5
        assert coa.probability_of_kill == 0.95
        assert coa.rationalization == "test rationale"
        assert coa.coa_id.startswith("COA-")

    def test_effector_assigned(self):
        eff = _make_effector(name="HIMARS")
        asset = _make_asset(effector=eff)
        scored = {"asset": asset, "time_min": 3.5, "pk": 0.88, "cost": 5.0}
        coa = _build_coa(scored, "highest_pk", "TRK-002", "pk reason")
        assert coa.effector.name == "HIMARS"


# ---------------------------------------------------------------------------
# TacticalPlannerAgent._scored_to_hitl_coa
# ---------------------------------------------------------------------------


class TestScoredToHitlCoa:
    def test_produces_frozen_hitl_coa(self):
        asset = _make_asset(pk=0.95, cost=8.5)
        scored = {"asset": asset, "time_min": 5.5, "pk": 0.95, "cost": 8.5}
        coa = TacticalPlannerAgent._scored_to_hitl_coa("COA-1", scored, "Fastest option")
        assert isinstance(coa, HITLCourseOfAction)
        assert coa.id == "COA-1"
        assert coa.pk_estimate == 0.95
        assert coa.status == "PROPOSED"
        assert "Fastest option" in coa.reasoning_trace

    def test_composite_score_positive(self):
        asset = _make_asset(pk=0.8, cost=3.0)
        scored = {"asset": asset, "time_min": 2.0, "pk": 0.8, "cost": 3.0}
        coa = TacticalPlannerAgent._scored_to_hitl_coa("COA-2", scored, "test")
        assert coa.composite_score > 0


# ---------------------------------------------------------------------------
# TacticalPlannerAgent._generate_coas_heuristic
# ---------------------------------------------------------------------------


class TestGenerateCoasHeuristic:
    def test_returns_three_coas(self):
        agent = TacticalPlannerAgent()
        assets = [
            _make_asset(effector=_make_effector("Fast", eid="F1"), pk=0.7, cost=5.0, speed=2000.0),
            _make_asset(effector=_make_effector("HighPk", eid="F2"), pk=0.99, cost=9.0, speed=500.0),
            _make_asset(effector=_make_effector("Cheap", eid="F3"), pk=0.5, cost=1.0, speed=100.0),
        ]
        target = {"lat": 33.0, "lon": 44.0}
        result = agent._generate_coas_heuristic(target, assets)
        assert len(result) == 3

    def test_sorted_by_composite_descending(self):
        agent = TacticalPlannerAgent()
        assets = [
            _make_asset(effector=_make_effector("A", eid="A1"), pk=0.7, cost=5.0, speed=2000.0),
            _make_asset(effector=_make_effector("B", eid="B1"), pk=0.99, cost=9.0, speed=500.0),
            _make_asset(effector=_make_effector("C", eid="C1"), pk=0.5, cost=1.0, speed=100.0),
        ]
        target = {"lat": 33.0, "lon": 44.0}
        result = agent._generate_coas_heuristic(target, assets)
        scores = [c.composite_score for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_all_proposed_status(self):
        agent = TacticalPlannerAgent()
        assets = [_make_asset(effector=_make_effector("X", eid=f"X{i}")) for i in range(3)]
        result = agent._generate_coas_heuristic({"lat": 0, "lon": 0}, assets)
        for coa in result:
            assert coa.status == "PROPOSED"


# ---------------------------------------------------------------------------
# TacticalPlannerAgent.generate_coas (sync, original schema)
# ---------------------------------------------------------------------------


class TestGenerateCoas:
    def test_skips_non_nominate_decisions(self):
        agent = TacticalPlannerAgent()
        analyst_output = StrategyAnalystOutput(
            nominations=[
                _make_nomination("TRK-001", "Nominate"),
                _make_nomination("TRK-002", "Monitor"),
                _make_nomination("TRK-003", "Reject"),
            ],
            summary="test",
        )
        tracks = [_make_track("TRK-001"), _make_track("TRK-002"), _make_track("TRK-003")]
        results = agent.generate_coas(analyst_output, tracks)
        assert len(results) == 1
        assert results[0].target_track_id == "TRK-001"

    def test_skips_missing_track(self):
        agent = TacticalPlannerAgent()
        analyst_output = StrategyAnalystOutput(
            nominations=[_make_nomination("TRK-MISSING", "Nominate")],
            summary="test",
        )
        tracks = [_make_track("TRK-001")]
        results = agent.generate_coas(analyst_output, tracks)
        assert len(results) == 0

    def test_produces_three_coas_per_nomination(self):
        agent = TacticalPlannerAgent()
        analyst_output = StrategyAnalystOutput(
            nominations=[_make_nomination("TRK-001", "Nominate")],
            summary="test",
        )
        tracks = [_make_track("TRK-001")]
        results = agent.generate_coas(analyst_output, tracks)
        assert len(results) == 1
        assert len(results[0].coas) == 3

    def test_coa_types_present(self):
        agent = TacticalPlannerAgent()
        analyst_output = StrategyAnalystOutput(
            nominations=[_make_nomination("TRK-001", "Nominate")],
            summary="test",
        )
        tracks = [_make_track("TRK-001")]
        results = agent.generate_coas(analyst_output, tracks)
        types = {c.coa_type for c in results[0].coas}
        assert types == {"fastest", "highest_pk", "lowest_cost"}

    def test_llm_client_falls_back_to_heuristic(self):
        """When llm_client is set, _generate_via_llm still falls back to heuristic."""
        agent = TacticalPlannerAgent(llm_client=MagicMock())
        analyst_output = StrategyAnalystOutput(
            nominations=[_make_nomination("TRK-001", "Nominate")],
            summary="test",
        )
        tracks = [_make_track("TRK-001")]
        results = agent.generate_coas(analyst_output, tracks)
        assert len(results) == 1
        assert len(results[0].coas) == 3

    def test_multiple_nominations(self):
        agent = TacticalPlannerAgent()
        analyst_output = StrategyAnalystOutput(
            nominations=[
                _make_nomination("TRK-001", "Nominate"),
                _make_nomination("TRK-002", "Nominate"),
            ],
            summary="test",
        )
        tracks = [_make_track("TRK-001"), _make_track("TRK-002")]
        results = agent.generate_coas(analyst_output, tracks)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# TacticalPlannerAgent.generate_coas_enhanced (async, HITL format)
# ---------------------------------------------------------------------------


class TestGenerateCoasEnhanced:
    @pytest.mark.asyncio
    async def test_heuristic_fallback_when_no_adapter(self):
        agent = TacticalPlannerAgent()
        target = {"lat": 33.0, "lon": 44.0}
        assets = [
            _make_asset(effector=_make_effector("A", eid="A1"), pk=0.9, cost=5.0, speed=1000.0),
            _make_asset(effector=_make_effector("B", eid="B1"), pk=0.7, cost=2.0, speed=500.0),
            _make_asset(effector=_make_effector("C", eid="C1"), pk=0.5, cost=1.0, speed=100.0),
        ]
        result = await agent.generate_coas_enhanced(target, assets)
        assert len(result) == 3
        assert all(isinstance(c, HITLCourseOfAction) for c in result)

    @pytest.mark.asyncio
    async def test_heuristic_fallback_when_adapter_unavailable(self):
        adapter = AsyncMock()
        adapter.is_available = MagicMock(return_value=False)
        agent = TacticalPlannerAgent(llm_adapter=adapter)
        target = {"lat": 33.0, "lon": 44.0}
        assets = [_make_asset(effector=_make_effector("A", eid="A1"))]
        result = await agent.generate_coas_enhanced(target, assets)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_llm_path_success(self):
        adapter = AsyncMock()
        adapter.is_available = MagicMock(return_value=True)
        adapter.complete_structured.return_value = {
            "coas": [
                {
                    "effector_name": "F-35A",
                    "effector_type": "Kinetic",
                    "time_to_effect_min": 12.0,
                    "pk_estimate": 0.95,
                    "risk_score": 8.0,
                    "reasoning_trace": "fastest",
                },
                {
                    "effector_name": "HIMARS",
                    "effector_type": "Kinetic",
                    "time_to_effect_min": 3.5,
                    "pk_estimate": 0.88,
                    "risk_score": 5.0,
                    "reasoning_trace": "highest pk",
                },
                {
                    "effector_name": "MQ-9",
                    "effector_type": "Kinetic",
                    "time_to_effect_min": 25.0,
                    "pk_estimate": 0.8,
                    "risk_score": 3.0,
                    "reasoning_trace": "lowest cost",
                },
            ]
        }
        agent = TacticalPlannerAgent(llm_adapter=adapter)
        result = await agent.generate_coas_enhanced({"lat": 33.0, "lon": 44.0}, [])
        assert len(result) == 3
        assert result[0].composite_score >= result[1].composite_score

    @pytest.mark.asyncio
    async def test_llm_path_exception_falls_back(self):
        adapter = AsyncMock()
        adapter.is_available = MagicMock(return_value=True)
        adapter.complete_structured.side_effect = Exception("LLM down")
        agent = TacticalPlannerAgent(llm_adapter=adapter)
        assets = [_make_asset(effector=_make_effector("A", eid="A1"))]
        result = await agent.generate_coas_enhanced({"lat": 33.0, "lon": 44.0}, assets)
        # Falls back to heuristic
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_llm_empty_result_falls_back(self):
        adapter = AsyncMock()
        adapter.is_available = MagicMock(return_value=True)
        adapter.complete_structured.return_value = {}
        agent = TacticalPlannerAgent(llm_adapter=adapter)
        assets = [_make_asset(effector=_make_effector("A", eid="A1"))]
        result = await agent.generate_coas_enhanced({"lat": 33.0, "lon": 44.0}, assets)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_llm_clamps_pk_and_risk(self):
        adapter = AsyncMock()
        adapter.is_available = MagicMock(return_value=True)
        adapter.complete_structured.return_value = {
            "coas": [
                {
                    "effector_name": "A",
                    "effector_type": "K",
                    "time_to_effect_min": 5.0,
                    "pk_estimate": 1.5,  # should clamp to 1.0
                    "risk_score": 15.0,  # should clamp to 10.0
                    "reasoning_trace": "test",
                },
                {
                    "effector_name": "B",
                    "effector_type": "K",
                    "time_to_effect_min": 5.0,
                    "pk_estimate": -0.5,  # should clamp to 0.0
                    "risk_score": -1.0,  # should clamp to 1.0
                    "reasoning_trace": "test",
                },
                {
                    "effector_name": "C",
                    "effector_type": "K",
                    "time_to_effect_min": 5.0,
                    "pk_estimate": 0.5,
                    "risk_score": 5.0,
                    "reasoning_trace": "test",
                },
            ]
        }
        agent = TacticalPlannerAgent(llm_adapter=adapter)
        result = await agent.generate_coas_enhanced({"lat": 0, "lon": 0}, [])
        pks = {c.pk_estimate for c in result}
        risks = {c.risk_score for c in result}
        assert all(0.0 <= c.pk_estimate <= 1.0 for c in result)
        assert all(1.0 <= c.risk_score <= 10.0 for c in result)


# ---------------------------------------------------------------------------
# TacticalPlannerAgent.__init__
# ---------------------------------------------------------------------------


class TestAgentInit:
    def test_default_init(self):
        agent = TacticalPlannerAgent()
        assert agent.llm_client is None
        assert agent.llm_adapter is None
        assert agent.system_prompt is not None

    def test_with_llm_client(self):
        client = MagicMock()
        agent = TacticalPlannerAgent(llm_client=client)
        assert agent.llm_client is client
