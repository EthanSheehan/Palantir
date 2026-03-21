"""Tests for aar_engine.py — After-Action Review Engine (W4-008)."""

import json
from unittest.mock import patch

import pytest
from aar_engine import AAREngine, AARReport, AARSnapshot, AARTimeline
from audit_log import AuditLog
from mission_store import MissionStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

F2T2EA_EVENT_TYPES = {
    "FIND": ["DETECTED"],
    "FIX": ["CLASSIFIED"],
    "TRACK": ["VERIFIED", "TRACKING"],
    "TARGET": ["NOMINATED", "COA_GENERATED"],
    "ENGAGE": ["AUTHORIZED", "ENGAGED"],
    "ASSESS": ["BDA_COMPLETE", "DESTROYED", "MISS"],
}


@pytest.fixture
def store(tmp_path):
    return MissionStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def audit():
    return AuditLog()


@pytest.fixture
def engine(store, audit):
    return AAREngine(store, audit)


@pytest.fixture
def populated_mission(store, audit):
    """Create a mission with events spanning all F2T2EA phases."""
    mid = store.create_mission("Op Test", "romania")
    store.log_target_event(mid, 1, "SAM", "DETECTED")
    store.log_target_event(mid, 1, "SAM", "CLASSIFIED")
    store.log_target_event(mid, 1, "SAM", "VERIFIED")
    store.log_target_event(mid, 1, "SAM", "NOMINATED")
    store.log_target_event(mid, 1, "SAM", "AUTHORIZED")
    store.log_target_event(mid, 1, "SAM", "BDA_COMPLETE")
    store.log_engagement(mid, 1, 1, "KINETIC", "HIT")
    audit.append(
        "APPROVE_NOMINATION",
        autonomy_level="SUPERVISED",
        target_id=1,
        operator_id="operator-1",
    )
    audit.append(
        "AUTHORIZE_COA",
        autonomy_level="AUTONOMOUS",
        target_id=1,
    )
    return mid


# ---------------------------------------------------------------------------
# AARTimeline tests
# ---------------------------------------------------------------------------


class TestBuildTimeline:
    def test_build_timeline_all_phases(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        assert isinstance(timeline, AARTimeline)
        assert timeline.mission_id == populated_mission
        assert "FIND" in timeline.phases
        assert "FIX" in timeline.phases
        assert "TRACK" in timeline.phases
        assert "TARGET" in timeline.phases
        assert "ENGAGE" in timeline.phases
        assert "ASSESS" in timeline.phases

    def test_build_timeline_find_has_detected(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        find_events = timeline.phases["FIND"]
        assert len(find_events) >= 1
        assert any(e["event_type"] == "DETECTED" for e in find_events)

    def test_build_timeline_engage_has_authorized(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        engage_events = timeline.phases["ENGAGE"]
        assert any(e["event_type"] == "AUTHORIZED" for e in engage_events)

    def test_build_timeline_empty_mission(self, engine, store):
        mid = store.create_mission("Empty Op", "romania")
        timeline = engine.build_timeline(mid)
        assert timeline.mission_id == mid
        for phase_events in timeline.phases.values():
            assert phase_events == []

    def test_build_timeline_total_ticks(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        assert isinstance(timeline.total_ticks, int)

    def test_build_timeline_duration(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        assert isinstance(timeline.duration_seconds, float)
        assert timeline.duration_seconds >= 0.0

    def test_timeline_is_frozen(self, engine, populated_mission):
        timeline = engine.build_timeline(populated_mission)
        with pytest.raises(AttributeError):
            timeline.mission_id = 999


# ---------------------------------------------------------------------------
# Snapshot / Replay tests
# ---------------------------------------------------------------------------


class TestGetSnapshots:
    def test_snapshots_with_checkpoint(self, engine, store):
        mid = store.create_mission("Op Replay", "romania")
        state = {"drones": [], "tick": 10}
        store.save_checkpoint(mid, json.dumps(state))
        snapshots = engine.get_snapshots(mid)
        assert isinstance(snapshots, list)
        assert len(snapshots) >= 1
        assert isinstance(snapshots[0], AARSnapshot)

    def test_snapshots_empty_mission(self, engine, store):
        mid = store.create_mission("Op Empty", "romania")
        snapshots = engine.get_snapshots(mid)
        assert snapshots == []

    def test_snapshot_is_frozen(self, engine, store):
        mid = store.create_mission("Op Frozen", "romania")
        store.save_checkpoint(mid, json.dumps({"tick": 1}))
        snapshots = engine.get_snapshots(mid)
        if snapshots:
            with pytest.raises(AttributeError):
                snapshots[0].tick = 999

    def test_snapshots_with_step(self, engine, store):
        mid = store.create_mission("Op Step", "romania")
        store.save_checkpoint(mid, json.dumps({"tick": 50}))
        snapshots = engine.get_snapshots(mid, step=5)
        assert isinstance(snapshots, list)


# ---------------------------------------------------------------------------
# Compare decisions tests
# ---------------------------------------------------------------------------


class TestCompareDecisions:
    def test_compare_decisions_returns_list(self, engine, populated_mission):
        result = engine.compare_decisions(populated_mission)
        assert isinstance(result, list)

    def test_compare_decisions_with_operator_actions(self, engine, store, audit):
        mid = store.create_mission("Op Compare", "romania")
        audit.append(
            "APPROVE_NOMINATION",
            autonomy_level="MANUAL",
            target_id=5,
            operator_id="op-1",
        )
        audit.append(
            "REJECT_NOMINATION",
            autonomy_level="MANUAL",
            target_id=6,
            operator_id="op-1",
        )
        audit.append(
            "AUTHORIZE_COA",
            autonomy_level="AUTONOMOUS",
            target_id=5,
        )
        result = engine.compare_decisions(mid)
        assert isinstance(result, list)

    def test_compare_decisions_empty_audit(self, store):
        empty_audit = AuditLog()
        eng = AAREngine(store, empty_audit)
        mid = store.create_mission("Op NoAudit", "romania")
        result = eng.compare_decisions(mid)
        assert result == []


# ---------------------------------------------------------------------------
# Generate report tests
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_generate_report_structure(self, engine, populated_mission):
        report = engine.generate_report(populated_mission)
        assert isinstance(report, AARReport)
        assert report.mission_id == populated_mission
        assert report.theater == "romania"
        assert isinstance(report.duration_seconds, float)
        assert isinstance(report.targets_detected, int)
        assert isinstance(report.targets_engaged, int)
        assert isinstance(report.engagements_successful, int)
        assert isinstance(report.ai_acceptance_rate, float)
        assert isinstance(report.phase_breakdown, dict)

    def test_report_counts(self, engine, populated_mission):
        report = engine.generate_report(populated_mission)
        assert report.targets_detected >= 1
        assert report.engagements_successful >= 0

    def test_report_empty_mission(self, engine, store):
        mid = store.create_mission("Op Empty", "romania")
        report = engine.generate_report(mid)
        assert report.targets_detected == 0
        assert report.targets_engaged == 0
        assert report.engagements_successful == 0
        assert report.ai_acceptance_rate == 0.0

    def test_report_is_frozen(self, engine, populated_mission):
        report = engine.generate_report(populated_mission)
        with pytest.raises(AttributeError):
            report.mission_id = 999

    def test_report_phase_breakdown_keys(self, engine, populated_mission):
        report = engine.generate_report(populated_mission)
        for phase in ("FIND", "FIX", "TRACK", "TARGET", "ENGAGE", "ASSESS"):
            assert phase in report.phase_breakdown

    def test_report_operator_overrides(self, engine, store, audit):
        mid = store.create_mission("Op Override", "romania")
        audit.append("REJECT_NOMINATION", autonomy_level="MANUAL", target_id=1, operator_id="op-1")
        audit.append("REJECT_COA", autonomy_level="MANUAL", target_id=2, operator_id="op-1")
        report = engine.generate_report(mid)
        assert report.operator_overrides >= 2


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------


class TestAAREndpoints:
    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "test_api.db")
        test_store = MissionStore(db_path=db_path)
        test_audit = AuditLog()

        mid = test_store.create_mission("Op API", "romania")
        test_store.log_target_event(mid, 1, "SAM", "DETECTED")
        test_store.log_target_event(mid, 1, "SAM", "CLASSIFIED")
        test_store.log_engagement(mid, 1, 1, "KINETIC", "HIT")

        with (
            patch("api_main.mission_store", test_store),
            patch("api_main.audit_log", test_audit),
        ):
            import api_main

            api_main.aar_engine = AAREngine(test_store, test_audit)

            from fastapi.testclient import TestClient

            yield TestClient(api_main.app), mid

    def test_timeline_endpoint(self, client):
        tc, mid = client
        resp = tc.get(f"/api/aar/{mid}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "phases" in data
        assert "mission_id" in data

    def test_report_endpoint(self, client):
        tc, mid = client
        resp = tc.get(f"/api/aar/{mid}/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "mission_id" in data
        assert "theater" in data
        assert "targets_detected" in data

    def test_replay_endpoint(self, client):
        tc, mid = client
        resp = tc.get(f"/api/aar/{mid}/replay?start=0&end=100&speed=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data

    def test_timeline_not_found(self, client):
        tc, _ = client
        resp = tc.get("/api/aar/9999/timeline")
        assert resp.status_code == 404

    def test_report_not_found(self, client):
        tc, _ = client
        resp = tc.get("/api/aar/9999/report")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# F2T2EA phase classification tests
# ---------------------------------------------------------------------------


class TestPhaseClassification:
    def test_detected_maps_to_find(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "DETECTED")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["FIND"]) == 1

    def test_classified_maps_to_fix(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "CLASSIFIED")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["FIX"]) == 1

    def test_verified_maps_to_track(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "VERIFIED")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["TRACK"]) == 1

    def test_nominated_maps_to_target(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "NOMINATED")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["TARGET"]) == 1

    def test_authorized_maps_to_engage(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "AUTHORIZED")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["ENGAGE"]) == 1

    def test_bda_complete_maps_to_assess(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "BDA_COMPLETE")
        timeline = engine.build_timeline(mid)
        assert len(timeline.phases["ASSESS"]) == 1

    def test_unknown_event_not_classified(self, engine, store):
        mid = store.create_mission("Op Phase", "romania")
        store.log_target_event(mid, 1, "SAM", "UNKNOWN_EVENT")
        timeline = engine.build_timeline(mid)
        total = sum(len(v) for v in timeline.phases.values())
        assert total == 0
