"""
Tests for forward_sim.py — written FIRST (TDD RED phase).

Tests cover:
  - clone_simulation: deep copy produces independent SimulationModel
  - score_state: scoring function returns a float in expected range
  - project_forward: runs N ticks on a clone, returns a score float
  - evaluate_coas: async parallel COA evaluation returns ranked COA list
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    def test_returns_float(self):
        model = _make_model()
        result = project_forward(model, ticks=5)
        assert isinstance(result, float)

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

        def _patched_project_forward(m, ticks=50):
            tick_count.append(ticks)
            return 0.0

        with patch.object(forward_sim, "project_forward", side_effect=_patched_project_forward):
            forward_sim.project_forward(model)
        assert tick_count == [50]

    def test_score_is_non_negative(self):
        model = _make_model()
        result = project_forward(model, ticks=3)
        assert result >= 0.0


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

        scores = {"COA-1": 3.0, "COA-2": 7.5, "COA-3": 1.0}

        def _mock_project_forward(m, ticks=50):
            # Distinguish by inspecting COA ID stored on model mock
            return scores.get(getattr(m, "_coa_id", "?"), 0.0)

        with patch.object(forward_sim, "project_forward", side_effect=_mock_project_forward):
            # Patch clone so we can set _coa_id for identification
            original_clone = forward_sim.clone_simulation

            def _clone_with_id(m):
                c = MagicMock()
                c.targets = {}
                c.uavs = {}
                c.tick = MagicMock()
                return c

            with patch.object(forward_sim, "clone_simulation", side_effect=_clone_with_id):
                result = asyncio.run(evaluate_coas(model, coas, ticks=5))

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
