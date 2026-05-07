"""
test_two_person_concurrence.py
==============================
Coverage for two_person_concurrence.py (FedRAMP-High control closure).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_person_concurrence import (
    ConcurrenceRecord,
    ConcurrenceRequest,
    DEFAULT_WINDOW_SEC,
    TwoPersonConcurrence,
)


@pytest.fixture
def tpc():
    return TwoPersonConcurrence(window_sec=60.0)


class TestRequest:
    def test_creates_pending_request(self, tpc):
        req = tpc.request_concurrence(
            target_id=42,
            primary_operator_id="alice",
            rationale="High-confidence SAM",
            coa_id="tac-7",
        )
        assert isinstance(req, ConcurrenceRequest)
        assert req.target_id == 42
        assert req.primary_operator_id == "alice"
        pending = tpc.pending()
        assert len(pending) == 1
        assert pending[0]["target_id"] == 42

    def test_rejects_blank_operator(self, tpc):
        with pytest.raises(ValueError):
            tpc.request_concurrence(target_id=1, primary_operator_id="")

    def test_new_request_invalidates_prior_authorisation(self, tpc):
        tpc.request_concurrence(target_id=1, primary_operator_id="alice")
        tpc.record_concurrence(target_id=1, secondary_operator_id="bob")
        assert tpc.is_authorised(1) is True
        # Re-opening the request drops the old authorisation
        tpc.request_concurrence(target_id=1, primary_operator_id="alice")
        assert tpc.is_authorised(1) is False


class TestRecord:
    def test_happy_path_records_concurrence(self, tpc):
        tpc.request_concurrence(target_id=1, primary_operator_id="alice", rationale="r1")
        rec = tpc.record_concurrence(target_id=1, secondary_operator_id="bob")
        assert isinstance(rec, ConcurrenceRecord)
        assert rec.primary_operator_id == "alice"
        assert rec.secondary_operator_id == "bob"
        assert rec.rationale == "r1"
        assert tpc.is_authorised(1) is True

    def test_no_pending_raises(self, tpc):
        with pytest.raises(ValueError):
            tpc.record_concurrence(target_id=99, secondary_operator_id="bob")

    def test_same_operator_rejected(self, tpc):
        tpc.request_concurrence(target_id=1, primary_operator_id="alice")
        with pytest.raises(ValueError, match="must differ"):
            tpc.record_concurrence(target_id=1, secondary_operator_id="alice")

    def test_expired_window_rejected(self, tpc):
        tpc.request_concurrence(
            target_id=1,
            primary_operator_id="alice",
            now=1000.0,
        )
        with pytest.raises(ValueError, match="expired"):
            tpc.record_concurrence(
                target_id=1,
                secondary_operator_id="bob",
                now=1000.0 + 65.0,  # past 60s window
            )
        # Pending request should have been dropped
        assert tpc.pending() == []


class TestConsume:
    def test_consume_returns_record_then_none(self, tpc):
        tpc.request_concurrence(target_id=1, primary_operator_id="alice")
        tpc.record_concurrence(target_id=1, secondary_operator_id="bob")
        first = tpc.consume_authorisation(1)
        assert first is not None
        assert first.secondary_operator_id == "bob"
        # Single-shot: second consume returns None
        assert tpc.consume_authorisation(1) is None

    def test_consume_unknown_target(self, tpc):
        assert tpc.consume_authorisation(999) is None


class TestExpireOld:
    def test_expires_only_old_pending(self, tpc):
        tpc.request_concurrence(target_id=1, primary_operator_id="alice", now=100.0)
        tpc.request_concurrence(target_id=2, primary_operator_id="alice", now=200.0)
        expired = tpc.expire_old(now=200.0 + 30.0)  # only target 1 is past 60s
        ids = [e.target_id for e in expired]
        assert ids == [1]
        # Target 2 still pending
        pending = tpc.pending()
        assert {p["target_id"] for p in pending} == {2}


class TestDefaultWindow:
    def test_default_window_is_five_minutes(self):
        assert DEFAULT_WINDOW_SEC == 300.0


# ---------------------------------------------------------------------------
# EffectorsAgent integration — AUTONOMOUS dispatches require concurrence
# ---------------------------------------------------------------------------


class TestEffectorsAgentTwoPersonGate:
    @pytest.mark.asyncio
    async def test_autonomous_blocked_without_concurrence(self):
        # Pin module-level singleton to a fresh instance so this test is
        # independent of any concurrence requests left over from elsewhere.
        import two_person_concurrence as _tpc_mod
        from agents.effectors_agent import EffectorsAgent
        from schemas.ontology import CourseOfAction, Effector

        original = _tpc_mod.two_person_concurrence
        _tpc_mod.two_person_concurrence = TwoPersonConcurrence()
        try:
            agent = EffectorsAgent()
            coa = CourseOfAction(
                coa_id="tac-1",
                coa_type="fastest",
                target_track_id="42",
                effector=Effector(
                    effector_id="f15",
                    name="F-15E",
                    effector_type="Kinetic",
                    status="AVAILABLE",
                ),
                time_to_target_minutes=5.0,
                probability_of_kill=0.85,
                munition_efficiency_cost=1.0,
                rationalization="Test",
            )
            target_data = {"id": 42, "type": "SAM", "state": "VERIFIED", "lat": 44, "lon": 26}
            result = await agent.execute_engagement(coa, target_data, autonomy_level="AUTONOMOUS")
            assert result.hit is False
            assert result.damage_level == "MISSED"
            assert result.effector_ack and result.effector_ack["channel"] == "BLOCKED_TPC"
            assert "two-person concurrence" in result.assessment_notes.lower()
        finally:
            _tpc_mod.two_person_concurrence = original

    @pytest.mark.asyncio
    async def test_autonomous_proceeds_when_concurrence_recorded(self):
        import two_person_concurrence as _tpc_mod
        from agents.effectors_agent import EffectorsAgent
        from schemas.ontology import CourseOfAction, Effector

        original = _tpc_mod.two_person_concurrence
        tpc = TwoPersonConcurrence()
        _tpc_mod.two_person_concurrence = tpc
        try:
            tpc.request_concurrence(target_id=42, primary_operator_id="alice", coa_id="tac-1")
            tpc.record_concurrence(target_id=42, secondary_operator_id="bob")
            agent = EffectorsAgent()
            coa = CourseOfAction(
                coa_id="tac-1",
                coa_type="fastest",
                target_track_id="42",
                effector=Effector(
                    effector_id="f15",
                    name="F-15E",
                    effector_type="Kinetic",
                    status="AVAILABLE",
                ),
                time_to_target_minutes=5.0,
                probability_of_kill=0.85,
                munition_efficiency_cost=1.0,
                rationalization="Test",
            )
            target_data = {"id": 42, "type": "SAM", "state": "VERIFIED", "lat": 44, "lon": 26}
            result = await agent.execute_engagement(coa, target_data, autonomy_level="AUTONOMOUS")
            # Authorisation was consumed; result reflects the actual roll
            assert result.effector_ack is not None
            assert result.effector_ack["channel"] != "BLOCKED_TPC"
            # Single-shot — second AUTONOMOUS engagement same target is blocked
            r2 = await agent.execute_engagement(coa, target_data, autonomy_level="AUTONOMOUS")
            assert r2.effector_ack["channel"] == "BLOCKED_TPC"
        finally:
            _tpc_mod.two_person_concurrence = original

    @pytest.mark.asyncio
    async def test_manual_autonomy_skips_concurrence(self):
        import two_person_concurrence as _tpc_mod
        from agents.effectors_agent import EffectorsAgent
        from schemas.ontology import CourseOfAction, Effector

        original = _tpc_mod.two_person_concurrence
        _tpc_mod.two_person_concurrence = TwoPersonConcurrence()
        try:
            agent = EffectorsAgent()
            coa = CourseOfAction(
                coa_id="tac-1",
                coa_type="fastest",
                target_track_id="42",
                effector=Effector(
                    effector_id="f15",
                    name="F-15E",
                    effector_type="Kinetic",
                    status="AVAILABLE",
                ),
                time_to_target_minutes=5.0,
                probability_of_kill=0.85,
                munition_efficiency_cost=1.0,
                rationalization="Test",
            )
            target_data = {"id": 42, "type": "SAM", "state": "VERIFIED", "lat": 44, "lon": 26}
            result = await agent.execute_engagement(coa, target_data, autonomy_level="MANUAL")
            # MANUAL skips the gate entirely
            assert result.effector_ack is not None
            assert result.effector_ack["channel"] != "BLOCKED_TPC"
        finally:
            _tpc_mod.two_person_concurrence = original
