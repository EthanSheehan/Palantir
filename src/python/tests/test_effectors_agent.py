"""
Tests for the Effectors Agent – engagement simulation, BDA, and feedback loop.
"""

import dataclasses
import random

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")

from schemas.ontology import CourseOfAction, Effector
from agents.effectors_agent import (
    DAMAGE_DAMAGED,
    DAMAGE_DESTROYED,
    DAMAGE_MISSED,
    FEEDBACK_CLOSE_TRACK,
    FEEDBACK_RE_DETECT,
    FEEDBACK_RE_ENGAGE,
    EffectorsAgent,
    EngagementResult,
    _compute_modified_pk,
    _determine_damage,
    _roll_hit,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_effector(**overrides) -> Effector:
    defaults = {
        "effector_id": "F35-ALPHA-01",
        "name": "F-35A Lightning II (Alpha)",
        "effector_type": "Kinetic",
        "status": "Available",
    }
    defaults.update(overrides)
    return Effector(**defaults)


def _make_coa(pk: float = 0.90, **overrides) -> CourseOfAction:
    defaults = {
        "coa_id": "COA-TEST-001",
        "coa_type": "highest_pk",
        "target_track_id": "TRK-42",
        "effector": _make_effector(),
        "time_to_target_minutes": 5.0,
        "probability_of_kill": pk,
        "munition_efficiency_cost": 8.5,
        "rationalization": "Test COA",
    }
    defaults.update(overrides)
    return CourseOfAction(**defaults)


def _make_target_data(target_id: int = 42, state: str = "LOCKED", **overrides) -> dict:
    defaults = {
        "id": target_id,
        "state": state,
        "type": "SAM",
        "lon": 25.0,
        "lat": 45.0,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestPkModifiers:
    def test_locked_adds_10_percent(self):
        assert _compute_modified_pk(0.80, "LOCKED") == pytest.approx(0.90)

    def test_tracked_adds_5_percent(self):
        assert _compute_modified_pk(0.80, "TRACKED") == pytest.approx(0.85)

    def test_detected_no_bonus(self):
        assert _compute_modified_pk(0.80, "DETECTED") == pytest.approx(0.80)

    def test_capped_at_1(self):
        assert _compute_modified_pk(0.95, "LOCKED") == pytest.approx(1.0)

    def test_undetected_no_bonus(self):
        assert _compute_modified_pk(0.50, "UNDETECTED") == pytest.approx(0.50)


class TestRollHit:
    def test_pk_1_always_hits(self):
        rng = random.Random(0)
        assert all(_roll_hit(1.0, rng) for _ in range(100))

    def test_pk_0_never_hits(self):
        rng = random.Random(0)
        assert not any(_roll_hit(0.0, rng) for _ in range(100))


class TestDetermineDamage:
    def test_miss_returns_missed(self):
        rng = random.Random(0)
        assert _determine_damage(False, rng) == DAMAGE_MISSED

    def test_hit_returns_destroyed_or_damaged(self):
        rng = random.Random(0)
        results = {_determine_damage(True, rng) for _ in range(200)}
        assert DAMAGE_DESTROYED in results
        assert DAMAGE_DAMAGED in results
        assert DAMAGE_MISSED not in results


# ---------------------------------------------------------------------------
# EngagementResult immutability
# ---------------------------------------------------------------------------

class TestEngagementResultImmutability:
    def test_frozen_dataclass(self):
        result = EngagementResult(
            target_id=1,
            coa_id="COA-001",
            effector_used="F-35",
            hit=True,
            damage_level=DAMAGE_DESTROYED,
            bda_confidence=0.9,
            assessment_notes="Destroyed.",
            reasoning_trace="Test.",
            timestamp="2026-01-01T00:00:00Z",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.hit = False

    def test_all_fields_present(self):
        result = EngagementResult(
            target_id=1,
            coa_id="COA-001",
            effector_used="F-35",
            hit=True,
            damage_level=DAMAGE_DESTROYED,
            bda_confidence=0.9,
            assessment_notes="Destroyed.",
            reasoning_trace="Test.",
            timestamp="2026-01-01T00:00:00Z",
        )
        fields = {f.name for f in dataclasses.fields(result)}
        expected = {
            "target_id", "coa_id", "effector_used", "hit",
            "damage_level", "bda_confidence", "assessment_notes",
            "reasoning_trace", "timestamp",
        }
        assert fields == expected


# ---------------------------------------------------------------------------
# Engagement execution (async)
# ---------------------------------------------------------------------------

class TestExecuteEngagement:
    @pytest.mark.asyncio
    async def test_high_pk_usually_hits(self):
        hits = 0
        trials = 100
        for seed in range(trials):
            agent = EffectorsAgent(llm_adapter=None, rng=random.Random(seed))
            coa = _make_coa(pk=0.95)
            target = _make_target_data(state="LOCKED")
            result = await agent.execute_engagement(coa, target)
            if result.hit:
                hits += 1
        assert hits > 80, f"Expected >80 hits out of {trials}, got {hits}"

    @pytest.mark.asyncio
    async def test_low_pk_usually_misses(self):
        hits = 0
        trials = 100
        for seed in range(trials):
            agent = EffectorsAgent(llm_adapter=None, rng=random.Random(seed))
            coa = _make_coa(pk=0.05)
            target = _make_target_data(state="DETECTED")
            result = await agent.execute_engagement(coa, target)
            if result.hit:
                hits += 1
        assert hits < 20, f"Expected <20 hits out of {trials}, got {hits}"

    @pytest.mark.asyncio
    async def test_result_has_correct_target_id(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        coa = _make_coa()
        target = _make_target_data(target_id=99)
        result = await agent.execute_engagement(coa, target)
        assert result.target_id == 99

    @pytest.mark.asyncio
    async def test_result_has_correct_coa_id(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        coa = _make_coa(coa_id="COA-CUSTOM-777")
        target = _make_target_data()
        result = await agent.execute_engagement(coa, target)
        assert result.coa_id == "COA-CUSTOM-777"

    @pytest.mark.asyncio
    async def test_result_has_timestamp(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        result = await agent.execute_engagement(_make_coa(), _make_target_data())
        assert result.timestamp is not None
        assert "T" in result.timestamp

    @pytest.mark.asyncio
    async def test_damage_level_consistent_with_hit(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        for seed in range(50):
            agent = EffectorsAgent(llm_adapter=None, rng=random.Random(seed))
            result = await agent.execute_engagement(_make_coa(), _make_target_data())
            if result.hit:
                assert result.damage_level in (DAMAGE_DESTROYED, DAMAGE_DAMAGED)
            else:
                assert result.damage_level == DAMAGE_MISSED


# ---------------------------------------------------------------------------
# BDA report
# ---------------------------------------------------------------------------

class TestBDAReport:
    @pytest.mark.asyncio
    async def test_bda_has_required_fields(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        bda = await agent.generate_bda(
            damage_level=DAMAGE_DESTROYED,
            hit=True,
            coa=_make_coa(),
            target_data=_make_target_data(),
        )
        assert "assessment_notes" in bda
        assert "bda_confidence" in bda
        assert isinstance(bda["assessment_notes"], str)
        assert 0.0 <= bda["bda_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_bda_destroyed_high_confidence(self):
        agent = EffectorsAgent(llm_adapter=None)
        bda = await agent.generate_bda(
            damage_level=DAMAGE_DESTROYED,
            hit=True,
            coa=_make_coa(),
            target_data=_make_target_data(),
        )
        assert bda["bda_confidence"] >= 0.85

    @pytest.mark.asyncio
    async def test_bda_missed_low_confidence(self):
        agent = EffectorsAgent(llm_adapter=None)
        bda = await agent.generate_bda(
            damage_level=DAMAGE_MISSED,
            hit=False,
            coa=_make_coa(),
            target_data=_make_target_data(),
        )
        assert bda["bda_confidence"] <= 0.55

    @pytest.mark.asyncio
    async def test_bda_notes_mention_target_type(self):
        agent = EffectorsAgent(llm_adapter=None)
        bda = await agent.generate_bda(
            damage_level=DAMAGE_DAMAGED,
            hit=True,
            coa=_make_coa(),
            target_data=_make_target_data(type="TEL"),
        )
        assert "TEL" in bda["assessment_notes"]


# ---------------------------------------------------------------------------
# Feedback recommendations
# ---------------------------------------------------------------------------

class TestFeedbackRecommendation:
    def _make_result(self, damage_level: str, hit: bool = True) -> EngagementResult:
        return EngagementResult(
            target_id=1,
            coa_id="COA-001",
            effector_used="F-35",
            hit=hit,
            damage_level=damage_level,
            bda_confidence=0.9,
            assessment_notes="Test.",
            reasoning_trace="Test.",
            timestamp="2026-01-01T00:00:00Z",
        )

    def test_destroyed_closes_track(self):
        agent = EffectorsAgent()
        feedback = agent.get_feedback_recommendation(
            self._make_result(DAMAGE_DESTROYED)
        )
        assert feedback["action"] == FEEDBACK_CLOSE_TRACK
        assert feedback["new_target_state"] == "DESTROYED"

    def test_damaged_recommends_re_engage(self):
        agent = EffectorsAgent()
        feedback = agent.get_feedback_recommendation(
            self._make_result(DAMAGE_DAMAGED)
        )
        assert feedback["action"] == FEEDBACK_RE_ENGAGE
        assert feedback["new_target_state"] == "ENGAGED"

    def test_missed_recommends_re_detect(self):
        agent = EffectorsAgent()
        feedback = agent.get_feedback_recommendation(
            self._make_result(DAMAGE_MISSED, hit=False)
        )
        assert feedback["action"] == FEEDBACK_RE_DETECT
        assert feedback["new_target_state"] == "ESCAPED"

    def test_feedback_includes_target_id(self):
        agent = EffectorsAgent()
        result = EngagementResult(
            target_id=77,
            coa_id="COA-001",
            effector_used="F-35",
            hit=True,
            damage_level=DAMAGE_DESTROYED,
            bda_confidence=0.9,
            assessment_notes="Test.",
            reasoning_trace="Test.",
            timestamp="2026-01-01T00:00:00Z",
        )
        feedback = agent.get_feedback_recommendation(result)
        assert feedback["target_id"] == 77

    def test_feedback_includes_reason(self):
        agent = EffectorsAgent()
        for damage in (DAMAGE_DESTROYED, DAMAGE_DAMAGED, DAMAGE_MISSED):
            feedback = agent.get_feedback_recommendation(
                self._make_result(damage)
            )
            assert "reason" in feedback
            assert len(feedback["reason"]) > 0


# ---------------------------------------------------------------------------
# Heuristic works without LLM
# ---------------------------------------------------------------------------

class TestHeuristicFallback:
    @pytest.mark.asyncio
    async def test_works_without_llm(self):
        agent = EffectorsAgent(llm_adapter=None, rng=random.Random(42))
        result = await agent.execute_engagement(_make_coa(), _make_target_data())
        assert result.damage_level in (DAMAGE_DESTROYED, DAMAGE_DAMAGED, DAMAGE_MISSED)
        assert len(result.assessment_notes) > 0
        assert len(result.reasoning_trace) > 0
