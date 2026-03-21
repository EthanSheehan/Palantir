"""Tests for the HITL Manager and strike board system."""

import dataclasses

import pytest

from hitl_manager import CourseOfAction, HITLManager, StrikeBoardEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return HITLManager()


@pytest.fixture
def sample_target_data():
    return {
        "target_id": 42,
        "target_type": "SAM",
        "target_location": (44.5, 26.1),
        "detection_confidence": 0.92,
    }


@pytest.fixture
def sample_evaluation():
    return {
        "priority_score": 8.5,
        "roe_evaluation": "ENGAGE",
        "reasoning_trace": "High-priority SAM site within ROE.",
    }


@pytest.fixture
def sample_coas():
    return [
        CourseOfAction(
            id="COA-1",
            effector_name="F-35A Lightning II",
            effector_type="Kinetic",
            time_to_effect_min=12.5,
            pk_estimate=0.95,
            risk_score=8.5,
            composite_score=0.45,
            reasoning_trace="Fastest strike option",
            status="PROPOSED",
        ),
        CourseOfAction(
            id="COA-2",
            effector_name="HIMARS Battery Bravo",
            effector_type="Kinetic",
            time_to_effect_min=3.5,
            pk_estimate=0.88,
            risk_score=5.0,
            composite_score=0.52,
            reasoning_trace="Highest Pk option",
            status="PROPOSED",
        ),
        CourseOfAction(
            id="COA-3",
            effector_name="MQ-9 Reaper",
            effector_type="Kinetic",
            time_to_effect_min=25.0,
            pk_estimate=0.80,
            risk_score=3.0,
            composite_score=0.41,
            reasoning_trace="Lowest cost option",
            status="PROPOSED",
        ),
    ]


# ---------------------------------------------------------------------------
# Gate 1: Target nomination
# ---------------------------------------------------------------------------

class TestNomination:
    def test_nominate_target_appears_on_strike_board(self, manager, sample_target_data, sample_evaluation):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)

        assert entry.status == "PENDING"
        assert entry.target_id == 42
        assert entry.target_type == "SAM"

        board = manager.get_strike_board()
        assert len(board) == 1
        assert board[0]["id"] == entry.id
        assert board[0]["status"] == "PENDING"

    def test_approve_nomination(self, manager, sample_target_data, sample_evaluation):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)

        approved = manager.approve_nomination(entry.id, rationale="Confirmed hostile")

        assert approved.status == "APPROVED"
        assert approved.decision["action"] == "APPROVED"
        assert approved.decision["rationale"] == "Confirmed hostile"

        board = manager.get_strike_board()
        assert board[0]["status"] == "APPROVED"

    def test_reject_nomination(self, manager, sample_target_data, sample_evaluation):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)

        rejected = manager.reject_nomination(entry.id, rationale="False positive")

        assert rejected.status == "REJECTED"
        assert rejected.decision["action"] == "REJECTED"

        board = manager.get_strike_board()
        assert board[0]["status"] == "REJECTED"

    def test_retask_nomination(self, manager, sample_target_data, sample_evaluation):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)

        retasked = manager.retask_nomination(entry.id, rationale="Need SIGINT confirmation")

        assert retasked.status == "RETASKED"
        assert retasked.decision["action"] == "RETASKED"

        board = manager.get_strike_board()
        assert board[0]["status"] == "RETASKED"

    def test_nominate_not_found_raises(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.approve_nomination("SB-NONEXIST")


# ---------------------------------------------------------------------------
# Gate 2: COA authorization
# ---------------------------------------------------------------------------

class TestCOAAuthorization:
    def test_propose_coas_retrievable(self, manager, sample_target_data, sample_evaluation, sample_coas):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.propose_coas(entry.id, sample_coas)

        coas = manager.get_coas_for_entry(entry.id)
        assert len(coas) == 3
        assert coas[0]["id"] == "COA-1"
        assert coas[1]["id"] == "COA-2"

    def test_authorize_coa(self, manager, sample_target_data, sample_evaluation, sample_coas):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.propose_coas(entry.id, sample_coas)

        authorized = manager.authorize_coa(entry.id, "COA-2", rationale="Best Pk")

        assert authorized.status == "AUTHORIZED"
        assert authorized.id == "COA-2"

        coas = manager.get_coas_for_entry(entry.id)
        statuses = {c["id"]: c["status"] for c in coas}
        assert statuses["COA-2"] == "AUTHORIZED"
        assert statuses["COA-1"] == "PROPOSED"

    def test_reject_coa(self, manager, sample_target_data, sample_evaluation, sample_coas):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.propose_coas(entry.id, sample_coas)

        manager.reject_coa(entry.id, rationale="Unacceptable risk")

        coas = manager.get_coas_for_entry(entry.id)
        assert all(c["status"] == "REJECTED" for c in coas)

    def test_authorize_coa_not_found_raises(self, manager, sample_target_data, sample_evaluation, sample_coas):
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.propose_coas(entry.id, sample_coas)

        with pytest.raises(ValueError, match="not found"):
            manager.authorize_coa(entry.id, "COA-99")


# ---------------------------------------------------------------------------
# Strike board queries
# ---------------------------------------------------------------------------

class TestStrikeBoard:
    def test_get_strike_board_returns_all_entries(self, manager, sample_target_data, sample_evaluation):
        manager.nominate_target(sample_target_data, sample_evaluation)
        manager.nominate_target(
            {**sample_target_data, "target_id": 99, "target_type": "TEL"},
            sample_evaluation,
        )

        board = manager.get_strike_board()
        assert len(board) == 2
        types = {e["target_type"] for e in board}
        assert types == {"SAM", "TEL"}

    def test_get_coas_empty_for_unknown_entry(self, manager):
        coas = manager.get_coas_for_entry("SB-NONEXIST")
        assert coas == []


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_strike_board_entry_is_frozen(self):
        entry = StrikeBoardEntry(
            id="SB-TEST",
            target_id=1,
            target_type="SAM",
            target_location=(44.0, 26.0),
            detection_confidence=0.9,
            priority_score=7.0,
            roe_evaluation="ENGAGE",
            reasoning_trace="test",
            status="PENDING",
            nominated_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.status = "APPROVED"

    def test_course_of_action_is_frozen(self):
        coa = CourseOfAction(
            id="COA-1",
            effector_name="F-35",
            effector_type="Kinetic",
            time_to_effect_min=10.0,
            pk_estimate=0.9,
            risk_score=5.0,
            composite_score=0.5,
            reasoning_trace="test",
            status="PROPOSED",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            coa.status = "AUTHORIZED"

    def test_approve_returns_new_instance(self, manager, sample_target_data, sample_evaluation):
        original = manager.nominate_target(sample_target_data, sample_evaluation)
        approved = manager.approve_nomination(original.id)

        assert original.status == "PENDING"
        assert approved.status == "APPROVED"
        assert original is not approved


# ---------------------------------------------------------------------------
# Replay attack prevention (W1-012)
# ---------------------------------------------------------------------------

class TestReplayAttackPrevention:
    def test_replay_rejected_nomination_fails(self, manager, sample_target_data, sample_evaluation):
        """A REJECTED nomination cannot be replayed to APPROVED."""
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.reject_nomination(entry.id, rationale="False positive")

        with pytest.raises(ValueError, match="REJECTED"):
            manager.approve_nomination(entry.id, rationale="Replay attempt")

    def test_replay_approved_nomination_fails(self, manager, sample_target_data, sample_evaluation):
        """An APPROVED nomination cannot be re-approved."""
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.approve_nomination(entry.id, rationale="Confirmed hostile")

        with pytest.raises(ValueError, match="APPROVED"):
            manager.approve_nomination(entry.id, rationale="Replay attempt")

    def test_only_pending_can_transition(self, manager, sample_target_data, sample_evaluation):
        """Only PENDING entries can be transitioned; RETASKED also blocks replay."""
        entry = manager.nominate_target(sample_target_data, sample_evaluation)
        manager.retask_nomination(entry.id, rationale="Need more intel")

        with pytest.raises(ValueError, match="RETASKED"):
            manager.approve_nomination(entry.id, rationale="Replay attempt")
