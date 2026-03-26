"""
Tests for forward_sim.py — written FIRST (TDD RED phase).

Tests cover:
  - clone_simulation: deep copy produces independent SimulationModel
  - score_state: scoring function returns a float in expected range
  - project_forward: runs N ticks on a clone, returns {score, completed} dict
  - evaluate_coas: async parallel COA evaluation returns ranked COA list
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import forward_sim
from forward_sim import (
    clone_simulation,
    evaluate_coas,
    project_forward,
    score_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_target(target_id: int, state: str = "DETECTED", fused_confidence: float = 0.7):
    t = SimpleNamespace(
        id=target_id,
        state=state,
        fused_confidence=fused_confidence,
        type="SAM",
    )
    return t


def _make_uav(uav_id: int, mode: str = "SEARCH", fuel_hours: float = 4.0):
    u = SimpleNamespace(
        id=uav_id,
        mode=mode,
        fuel_hours=fuel_hours,
    )
    return u


def _make_model(
    num_targets: int = 3,
    num_uavs: int = 5,
    verified_count: int = 1,
    destroyed_count: int = 0,
):
    model = MagicMock()
    targets = {}
    for i in range(num_targets):
        state = "VERIFIED" if i < verified_count else "DETECTED"
        targets[i] = _make_target(i, state=state)

    for i in range(destroyed_count):
        targets[num_targets + i] = _make_target(num_targets + i, state="DESTROYED")

    uavs = {i: _make_uav(i) for i in range(num_uavs)}
    model.targets = targets
    model.uavs = uavs
    model.tick = MagicMock()
    return model


# ---------------------------------------------------------------------------
# TestCloneSimulation
# ---------------------------------------------------------------------------


class TestCloneSimulation:
    def test_returns_a_copy_not_same_object(self):
        model = _make_model()
        cloned = clone_simulation(model)
        assert cloned is not model

    def test_targets_are_independent(self):
        model = _make_model(num_targets=2)
        cloned = clone_simulation(model)
        # Mutate original targets dict — clone should be unaffected
        original_target_ids = set(model.targets.keys())
        model.targets[999] = _make_target(999)
        assert 999 not in cloned.targets
        assert set(cloned.targets.keys()) == original_target_ids

    def test_uavs_are_independent(self):
        model = _make_model(num_uavs=3)
        cloned = clone_simulation(model)
        original_uav_ids = set(model.uavs.keys())
        model.uavs[999] = _make_uav(999)
        assert 999 not in cloned.uavs
        assert set(cloned.uavs.keys()) == original_uav_ids

    def test_clone_with_real_sim_model(self):
        """Clone a real SimulationModel to verify deepcopy works end-to-end."""
        from sim_engine import SimulationModel

        real_model = SimulationModel(theater_name="romania")
        cloned = clone_simulation(real_model)
        assert cloned is not real_model
        assert cloned.targets is not real_model.targets
        assert cloned.uavs is not real_model.uavs
        # Verify same number of entities
        assert len(cloned.targets) == len(real_model.targets)
        assert len(cloned.uavs) == len(real_model.uavs)


# ---------------------------------------------------------------------------
# TestScoreState
# ---------------------------------------------------------------------------


class TestScoreState:
    def test_returns_float(self):
        model = _make_model()
        result = score_state(model)
        assert isinstance(result, float)

    def test_higher_score_for_more_verified_targets(self):
        model_low = _make_model(num_targets=5, verified_count=0)
        model_high = _make_model(num_targets=5, verified_count=4)
        assert score_state(model_high) > score_state(model_low)

    def test_lower_score_for_destroyed_targets(self):
        model_ok = _make_model(num_targets=3, verified_count=1, destroyed_count=0)
        model_bad = _make_model(num_targets=3, verified_count=1, destroyed_count=5)
        assert score_state(model_ok) > score_state(model_bad)

    def test_score_non_negative(self):
        model = _make_model(num_targets=2, verified_count=0, destroyed_count=3)
        assert score_state(model) >= 0.0

    def test_empty_model_returns_zero(self):
        model = MagicMock()
        model.targets = {}
        model.uavs = {}
        result = score_state(model)
        assert result == 0.0

    def test_healthy_uavs_improve_score(self):
        model_healthy = _make_model(num_uavs=5)
        for u in model_healthy.uavs.values():
            u.fuel_hours = 6.0
        model_depleted = _make_model(num_uavs=5)
        for u in model_depleted.uavs.values():
            u.fuel_hours = 0.5
        assert score_state(model_healthy) > score_state(model_depleted)


# ---------------------------------------------------------------------------
# TestProjectForward
# ---------------------------------------------------------------------------


class TestProjectForward:
    def test_returns_dict_with_score_and_completed(self):
        model = _make_model()
        result = project_forward(model, ticks=5)
        assert isinstance(result, dict)
        assert "score" in result
        assert "completed" in result

    def test_score_is_float(self):
        model = _make_model()
        result = project_forward(model, ticks=5)
        assert isinstance(result["score"], float)

    def test_completed_true_on_clean_run(self):
        model = _make_model()
        result = project_forward(model, ticks=5)
        assert result["completed"] is True

    def test_completed_false_when_tick_raises(self):
        model = _make_model()
        model.tick.side_effect = RuntimeError("sim error")
        # Clone will also have tick raise since MagicMock deepcopy shares side_effect config
        # patch clone_simulation to return a model whose tick raises
        bad_clone = MagicMock()
        bad_clone.targets = model.targets
        bad_clone.uavs = model.uavs
        bad_clone.tick = MagicMock(side_effect=RuntimeError("sim error"))
        with patch.object(forward_sim, "clone_simulation", return_value=bad_clone):
            result = project_forward(model, ticks=5)
        assert result["completed"] is False

    def test_calls_tick_n_times(self):
        model = _make_model()
        project_forward(model, ticks=10)
        # project_forward should clone and tick 10 times on the clone
        # The original model tick should NOT be called
        model.tick.assert_not_called()

    def test_does_not_mutate_original_model(self):
        from sim_engine import SimulationModel

        real_model = SimulationModel(theater_name="romania")
        original_target_count = len(real_model.targets)
        original_uav_count = len(real_model.uavs)
        project_forward(real_model, ticks=5)
        assert len(real_model.targets) == original_target_count
        assert len(real_model.uavs) == original_uav_count

    def test_default_ticks_is_50(self):
        """project_forward(model) without ticks param uses 50 ticks."""
        model = _make_model()
        tick_count = []

        original_pf = forward_sim.project_forward

        def _patched_project_forward(m, ticks=50):
            tick_count.append(ticks)
            return {"score": 0.0, "completed": True}

        with patch.object(forward_sim, "project_forward", side_effect=_patched_project_forward):
            forward_sim.project_forward(model)
        assert tick_count == [50]

    def test_score_is_non_negative(self):
        model = _make_model()
        result = project_forward(model, ticks=3)
        assert result["score"] >= 0.0

    def test_ticks_clamped_to_max(self):
        """Ticks above _MAX_TICKS (500) are silently clamped."""
        model = _make_model()
        # Should not raise; just runs with clamped ticks
        result = project_forward(model, ticks=9999)
        assert isinstance(result["score"], float)


# ---------------------------------------------------------------------------
# TestEvaluateCoas
# ---------------------------------------------------------------------------


class TestEvaluateCoas:
    def test_returns_sorted_by_projected_score_descending(self):
        model = _make_model()
        coas = [
            {"id": "COA-1", "type": "FASTEST"},
            {"id": "COA-2", "type": "HIGHEST_PK"},
            {"id": "COA-3", "type": "LOWEST_COST"},
        ]

        result = asyncio.run(evaluate_coas(model, coas, ticks=2))

        assert len(result) == 3
        scores_out = [c["projected_score"] for c in result]
        assert scores_out == sorted(scores_out, reverse=True)

    def test_each_coa_has_projected_score(self):
        model = _make_model()
        coas = [{"id": "COA-1"}, {"id": "COA-2"}]

        result = asyncio.run(evaluate_coas(model, coas, ticks=3))

        for coa in result:
            assert "projected_score" in coa
            assert isinstance(coa["projected_score"], float)

    def test_each_coa_has_projected_state_summary(self):
        model = _make_model()
        coas = [{"id": "COA-1"}]

        result = asyncio.run(evaluate_coas(model, coas, ticks=3))

        assert "projected_state_summary" in result[0]
        summary = result[0]["projected_state_summary"]
        assert "verified_targets" in summary
        assert "active_threats" in summary
        assert "drone_health" in summary

    def test_original_coa_fields_preserved(self):
        model = _make_model()
        coas = [{"id": "COA-ALPHA", "pk_estimate": 0.9, "effector_name": "JDAM"}]

        result = asyncio.run(evaluate_coas(model, coas, ticks=2))

        assert result[0]["id"] == "COA-ALPHA"
        assert result[0]["pk_estimate"] == 0.9
        assert result[0]["effector_name"] == "JDAM"

    def test_empty_coa_list_returns_empty(self):
        model = _make_model()
        result = asyncio.run(evaluate_coas(model, [], ticks=3))
        assert result == []

    def test_original_model_not_mutated(self):
        from sim_engine import SimulationModel

        real_model = SimulationModel(theater_name="romania")
        original_target_count = len(real_model.targets)
        coas = [{"id": "COA-1"}, {"id": "COA-2"}]

        asyncio.run(evaluate_coas(real_model, coas, ticks=3))
        assert len(real_model.targets) == original_target_count

    def test_too_many_coas_raises_value_error(self):
        """H3: COA lists > 64 raise ValueError immediately."""
        model = _make_model()
        coas = [{"id": f"COA-{i}"} for i in range(65)]
        with pytest.raises(ValueError, match="Too many COAs"):
            asyncio.run(evaluate_coas(model, coas, ticks=1))

    def test_exactly_64_coas_allowed(self):
        """H3: Exactly _MAX_COAS COAs should not raise."""
        model = _make_model()
        coas = [{"id": f"COA-{i}"} for i in range(64)]
        result = asyncio.run(evaluate_coas(model, coas, ticks=1))
        assert len(result) == 64

    def test_coa_types_receive_different_scores(self):
        """H1: Different COA types should receive differentiated projected scores via bonuses."""
        # Use a model with no NOMINATED/VERIFIED targets so STRIKE won't destroy anything,
        # leaving the type bonus as the sole differentiator.
        model = _make_model(num_targets=3, verified_count=0)
        coas = [
            {"id": "COA-STRIKE", "type": "STRIKE"},
            {"id": "COA-LOWEST_COST", "type": "LOWEST_COST"},
            {"id": "COA-RECON", "type": "RECON"},
        ]
        result = asyncio.run(evaluate_coas(model, coas, ticks=1))
        scores_by_id = {c["id"]: c["projected_score"] for c in result}
        # STRIKE bonus (+2.0) > LOWEST_COST (0.0) > RECON (-0.5, clamped to >= 0)
        assert scores_by_id["COA-STRIKE"] > scores_by_id["COA-LOWEST_COST"]
        assert scores_by_id["COA-LOWEST_COST"] >= scores_by_id["COA-RECON"]

    def test_summary_has_completed_field(self):
        """M4: projected_state_summary includes completed status."""
        model = _make_model()
        coas = [{"id": "COA-1"}]
        result = asyncio.run(evaluate_coas(model, coas, ticks=2))
        assert "completed" in result[0]["projected_state_summary"]
