"""Tests for the F2T2EA Kill Chain Progress Tracker."""

from __future__ import annotations

import pytest
from kill_chain_tracker import KillChainPhase, KillChainStatus, KillChainTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _target(tid: int, state: str = "DETECTED", tracked_by_uav_id=None, mode_tracking=False):
    """Build a minimal target dict matching sim_engine.get_state() format."""
    return {
        "id": tid,
        "type": "SAM",
        "state": state,
        "detected": state != "UNDETECTED",
        "tracked_by_uav_id": tracked_by_uav_id,
        "tracked_by_uav_ids": [tracked_by_uav_id] if tracked_by_uav_id else [],
    }


def _drone(did: int, mode: str = "SEARCH", tracked_target_id=None):
    """Build a minimal drone dict matching sim_engine.get_state() format."""
    return {
        "id": did,
        "mode": mode,
        "tracked_target_id": tracked_target_id,
    }


def _strike_entry(target_id: int, status: str = "PENDING"):
    """Build a minimal strike board entry dict."""
    return {
        "target_id": target_id,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Tests: KillChainPhase enum
# ---------------------------------------------------------------------------


class TestKillChainPhase:
    def test_enum_has_six_phases(self):
        assert len(KillChainPhase) == 6

    def test_phase_names(self):
        names = [p.name for p in KillChainPhase]
        assert names == ["FIND", "FIX", "TRACK", "TARGET", "ENGAGE", "ASSESS"]


# ---------------------------------------------------------------------------
# Tests: KillChainStatus frozen dataclass
# ---------------------------------------------------------------------------


class TestKillChainStatus:
    def test_frozen(self):
        status = KillChainStatus(phase=KillChainPhase.FIND, target_count=1, target_ids=[1])
        with pytest.raises(AttributeError):
            status.target_count = 5

    def test_fields(self):
        status = KillChainStatus(phase=KillChainPhase.ENGAGE, target_count=2, target_ids=[3, 4])
        assert status.phase == KillChainPhase.ENGAGE
        assert status.target_count == 2
        assert status.target_ids == [3, 4]


# ---------------------------------------------------------------------------
# Tests: compute()
# ---------------------------------------------------------------------------


class TestCompute:
    def setup_method(self):
        self.tracker = KillChainTracker()

    def test_empty_targets(self):
        result = self.tracker.compute(targets=[], drones=[], strike_board=[])
        assert len(result) == 6
        for status in result:
            assert status.target_count == 0
            assert status.target_ids == []

    def test_find_phase_detected(self):
        targets = [_target(1, "DETECTED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        find = _phase(result, KillChainPhase.FIND)
        assert find.target_count == 1
        assert find.target_ids == [1]

    def test_fix_phase_classified(self):
        targets = [_target(1, "CLASSIFIED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        fix = _phase(result, KillChainPhase.FIX)
        assert fix.target_count == 1
        assert fix.target_ids == [1]

    def test_track_phase_drone_following(self):
        targets = [_target(1, "CLASSIFIED", tracked_by_uav_id=10)]
        drones = [_drone(10, mode="FOLLOW", tracked_target_id=1)]
        result = self.tracker.compute(targets=targets, drones=drones, strike_board=[])
        track = _phase(result, KillChainPhase.TRACK)
        assert track.target_count == 1
        assert track.target_ids == [1]

    def test_track_phase_drone_painting(self):
        targets = [_target(1, "CLASSIFIED", tracked_by_uav_id=10)]
        drones = [_drone(10, mode="PAINT", tracked_target_id=1)]
        result = self.tracker.compute(targets=targets, drones=drones, strike_board=[])
        track = _phase(result, KillChainPhase.TRACK)
        assert track.target_count == 1
        assert track.target_ids == [1]

    def test_target_phase_verified(self):
        targets = [_target(1, "VERIFIED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        target = _phase(result, KillChainPhase.TARGET)
        assert target.target_count == 1
        assert target.target_ids == [1]

    def test_target_phase_nominated(self):
        targets = [_target(1, "NOMINATED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        target = _phase(result, KillChainPhase.TARGET)
        assert target.target_count == 1
        assert target.target_ids == [1]

    def test_target_phase_pending_strike(self):
        targets = [_target(1, "NOMINATED")]
        strike = [_strike_entry(1, "PENDING")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=strike)
        target = _phase(result, KillChainPhase.TARGET)
        assert target.target_count == 1
        assert target.target_ids == [1]

    def test_engage_phase_approved_strike(self):
        targets = [_target(1, "LOCKED")]
        strike = [_strike_entry(1, "APPROVED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=strike)
        engage = _phase(result, KillChainPhase.ENGAGE)
        assert engage.target_count == 1
        assert engage.target_ids == [1]

    def test_engage_phase_engaged_state(self):
        targets = [_target(1, "ENGAGED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        engage = _phase(result, KillChainPhase.ENGAGE)
        assert engage.target_count == 1
        assert engage.target_ids == [1]

    def test_assess_phase_destroyed(self):
        targets = [_target(1, "DESTROYED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        assess = _phase(result, KillChainPhase.ASSESS)
        assert assess.target_count == 1
        assert assess.target_ids == [1]

    def test_assess_phase_hit_strike(self):
        targets = [_target(1, "DESTROYED")]
        strike = [_strike_entry(1, "HIT")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=strike)
        assess = _phase(result, KillChainPhase.ASSESS)
        assert assess.target_count == 1

    def test_assess_phase_miss_strike(self):
        targets = [_target(1, "ESCAPED")]
        strike = [_strike_entry(1, "MISS")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=strike)
        assess = _phase(result, KillChainPhase.ASSESS)
        assert assess.target_count == 1

    def test_every_target_in_exactly_one_phase(self):
        targets = [
            _target(1, "DETECTED"),
            _target(2, "CLASSIFIED"),
            _target(3, "VERIFIED"),
            _target(4, "NOMINATED"),
            _target(5, "ENGAGED"),
            _target(6, "DESTROYED"),
        ]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        all_ids = []
        for status in result:
            all_ids.extend(status.target_ids)
        assert sorted(all_ids) == [1, 2, 3, 4, 5, 6]
        assert len(all_ids) == 6  # no duplicates

    def test_multiple_targets_same_phase(self):
        targets = [_target(1, "DETECTED"), _target(2, "DETECTED"), _target(3, "DETECTED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        find = _phase(result, KillChainPhase.FIND)
        assert find.target_count == 3
        assert sorted(find.target_ids) == [1, 2, 3]

    def test_target_transitions_through_all_phases(self):
        """Simulate a target moving through each kill chain phase."""
        tracker = KillChainTracker()
        states = [
            ("DETECTED", KillChainPhase.FIND),
            ("CLASSIFIED", KillChainPhase.FIX),
            ("VERIFIED", KillChainPhase.TARGET),
            ("ENGAGED", KillChainPhase.ENGAGE),
            ("DESTROYED", KillChainPhase.ASSESS),
        ]
        for state, expected_phase in states:
            targets = [_target(1, state)]
            result = tracker.compute(targets=targets, drones=[], strike_board=[])
            phase_status = _phase(result, expected_phase)
            assert 1 in phase_status.target_ids, f"Target 1 not in {expected_phase} for state {state}"

    def test_undetected_targets_excluded(self):
        targets = [_target(1, "UNDETECTED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        all_ids = []
        for status in result:
            all_ids.extend(status.target_ids)
        assert all_ids == []

    def test_mixed_target_states(self):
        targets = [
            _target(1, "DETECTED"),
            _target(2, "CLASSIFIED"),
            _target(3, "CLASSIFIED"),
            _target(4, "VERIFIED"),
            _target(5, "ENGAGED"),
            _target(6, "DESTROYED"),
            _target(7, "UNDETECTED"),
        ]
        strike = [_strike_entry(5, "APPROVED")]
        drones = [_drone(10, "FOLLOW", tracked_target_id=2)]
        result = self.tracker.compute(targets=targets, drones=drones, strike_board=strike)

        find = _phase(result, KillChainPhase.FIND)
        fix = _phase(result, KillChainPhase.FIX)
        track = _phase(result, KillChainPhase.TRACK)
        target = _phase(result, KillChainPhase.TARGET)
        engage = _phase(result, KillChainPhase.ENGAGE)
        assess = _phase(result, KillChainPhase.ASSESS)

        assert find.target_ids == [1]
        assert 2 in track.target_ids  # CLASSIFIED but tracked -> TRACK
        assert 3 in fix.target_ids  # CLASSIFIED, not tracked -> FIX
        assert target.target_ids == [4]
        assert engage.target_ids == [5]
        assert assess.target_ids == [6]

    def test_escaped_target_in_assess(self):
        targets = [_target(1, "ESCAPED")]
        result = self.tracker.compute(targets=targets, drones=[], strike_board=[])
        assess = _phase(result, KillChainPhase.ASSESS)
        assert assess.target_count == 1
        assert assess.target_ids == [1]


# ---------------------------------------------------------------------------
# Tests: to_dict()
# ---------------------------------------------------------------------------


class TestToDict:
    def setup_method(self):
        self.tracker = KillChainTracker()

    def test_serialization_structure(self):
        statuses = [
            KillChainStatus(phase=KillChainPhase.FIND, target_count=2, target_ids=[1, 2]),
            KillChainStatus(phase=KillChainPhase.FIX, target_count=0, target_ids=[]),
            KillChainStatus(phase=KillChainPhase.TRACK, target_count=0, target_ids=[]),
            KillChainStatus(phase=KillChainPhase.TARGET, target_count=1, target_ids=[3]),
            KillChainStatus(phase=KillChainPhase.ENGAGE, target_count=0, target_ids=[]),
            KillChainStatus(phase=KillChainPhase.ASSESS, target_count=0, target_ids=[]),
        ]
        result = self.tracker.to_dict(statuses)
        assert "phases" in result
        assert len(result["phases"]) == 6
        assert result["total_tracked"] == 3

    def test_serialization_phase_fields(self):
        statuses = [
            KillChainStatus(phase=KillChainPhase.FIND, target_count=1, target_ids=[5]),
        ]
        result = self.tracker.to_dict(statuses)
        phase = result["phases"][0]
        assert phase["phase"] == "FIND"
        assert phase["target_count"] == 1
        assert phase["target_ids"] == [5]

    def test_round_trip(self):
        targets = [_target(1, "DETECTED"), _target(2, "ENGAGED")]
        tracker = KillChainTracker()
        statuses = tracker.compute(targets=targets, drones=[], strike_board=[])
        d = tracker.to_dict(statuses)
        assert isinstance(d, dict)
        assert d["total_tracked"] == 2
        find_phase = next(p for p in d["phases"] if p["phase"] == "FIND")
        assert find_phase["target_ids"] == [1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phase(result: list[KillChainStatus], phase: KillChainPhase) -> KillChainStatus:
    return next(s for s in result if s.phase == phase)
