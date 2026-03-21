"""Tests for mission_store.py — SQLite persistence layer."""

import json
import threading

import pytest
from mission_store import MissionStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_missions.db")
    return MissionStore(db_path=db_path)


# ---------------------------------------------------------------------------
# Mission CRUD
# ---------------------------------------------------------------------------


class TestMissionCRUD:
    def test_create_mission(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        assert isinstance(mid, int)
        assert mid > 0

    def test_get_mission(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        mission = store.get_mission(mid)
        assert mission is not None
        assert mission["name"] == "Op Alpha"
        assert mission["theater"] == "romania"
        assert mission["status"] == "ACTIVE"
        assert mission["end_time"] is None

    def test_get_mission_not_found(self, store):
        assert store.get_mission(9999) is None

    def test_list_missions_empty(self, store):
        assert store.list_missions() == []

    def test_list_missions(self, store):
        store.create_mission("Op Alpha", "romania")
        store.create_mission("Op Bravo", "south_china_sea")
        missions = store.list_missions()
        assert len(missions) == 2
        names = {m["name"] for m in missions}
        assert names == {"Op Alpha", "Op Bravo"}

    def test_end_mission(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.end_mission(mid)
        mission = store.get_mission(mid)
        assert mission["status"] == "COMPLETED"
        assert mission["end_time"] is not None


# ---------------------------------------------------------------------------
# Target events
# ---------------------------------------------------------------------------


class TestTargetEvents:
    def test_log_target_event(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_target_event(mid, 1, "SAM", "DETECTED")
        history = store.get_target_history(mid, 1)
        assert len(history) == 1
        assert history[0]["event_type"] == "DETECTED"
        assert history[0]["target_type"] == "SAM"

    def test_log_target_event_with_details(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        details = {"confidence": 0.85, "sensor": "EO"}
        store.log_target_event(mid, 1, "TEL", "CLASSIFIED", details=details)
        history = store.get_target_history(mid, 1)
        assert len(history) == 1
        parsed = json.loads(history[0]["details_json"]) if history[0]["details_json"] else {}
        assert parsed["confidence"] == 0.85

    def test_target_history_ordering(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_target_event(mid, 1, "SAM", "DETECTED")
        store.log_target_event(mid, 1, "SAM", "CLASSIFIED")
        store.log_target_event(mid, 1, "SAM", "VERIFIED")
        history = store.get_target_history(mid, 1)
        assert len(history) == 3
        assert history[0]["event_type"] == "DETECTED"
        assert history[2]["event_type"] == "VERIFIED"

    def test_target_history_empty(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        assert store.get_target_history(mid, 999) == []


# ---------------------------------------------------------------------------
# Drone assignments
# ---------------------------------------------------------------------------


class TestDroneAssignments:
    def test_log_drone_assignment(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_drone_assignment(mid, 1, 10, "FOLLOW")
        # Verify it was stored by checking mission summary
        summary = store.get_mission_summary(mid)
        assert summary["drone_assignments"] == 1

    def test_multiple_drone_assignments(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_drone_assignment(mid, 1, 10, "FOLLOW")
        store.log_drone_assignment(mid, 2, 10, "PAINT")
        store.log_drone_assignment(mid, 1, 11, "SEARCH")
        summary = store.get_mission_summary(mid)
        assert summary["drone_assignments"] == 3


# ---------------------------------------------------------------------------
# Engagements
# ---------------------------------------------------------------------------


class TestEngagements:
    def test_log_engagement(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_engagement(mid, 10, 1, "KINETIC", "HIT")
        summary = store.get_mission_summary(mid)
        assert summary["engagements"] == 1

    def test_log_engagement_with_details(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        details = {"weapon": "JDAM", "bda_confidence": 0.9}
        store.log_engagement(mid, 10, 1, "KINETIC", "HIT", details=details)
        summary = store.get_mission_summary(mid)
        assert summary["engagements"] == 1

    def test_engagement_outcomes_in_summary(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_engagement(mid, 10, 1, "KINETIC", "HIT")
        store.log_engagement(mid, 11, 2, "KINETIC", "MISS")
        store.log_engagement(mid, 12, 3, "EW", "HIT")
        summary = store.get_mission_summary(mid)
        assert summary["engagements"] == 3
        assert summary["outcomes"]["HIT"] == 2
        assert summary["outcomes"]["MISS"] == 1


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


class TestCheckpoints:
    def test_save_and_load_checkpoint(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        state = json.dumps({"drones": [1, 2, 3], "tick": 42})
        store.save_checkpoint(mid, state)
        loaded = store.load_checkpoint(mid)
        assert loaded == state

    def test_checkpoint_overwrites(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.save_checkpoint(mid, '{"tick": 1}')
        store.save_checkpoint(mid, '{"tick": 2}')
        loaded = store.load_checkpoint(mid)
        assert loaded == '{"tick": 2}'

    def test_load_checkpoint_not_found(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        assert store.load_checkpoint(mid) is None


# ---------------------------------------------------------------------------
# Mission summary
# ---------------------------------------------------------------------------


class TestMissionSummary:
    def test_summary_empty_mission(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        summary = store.get_mission_summary(mid)
        assert summary["target_events"] == 0
        assert summary["drone_assignments"] == 0
        assert summary["engagements"] == 0
        assert summary["outcomes"] == {}

    def test_summary_counts(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_target_event(mid, 1, "SAM", "DETECTED")
        store.log_target_event(mid, 1, "SAM", "CLASSIFIED")
        store.log_drone_assignment(mid, 1, 1, "FOLLOW")
        store.log_engagement(mid, 1, 1, "KINETIC", "HIT")
        summary = store.get_mission_summary(mid)
        assert summary["target_events"] == 2
        assert summary["drone_assignments"] == 1
        assert summary["engagements"] == 1
        assert summary["outcomes"]["HIT"] == 1

    def test_summary_nonexistent_mission(self, store):
        summary = store.get_mission_summary(9999)
        assert summary["target_events"] == 0


# ---------------------------------------------------------------------------
# SQL injection prevention
# ---------------------------------------------------------------------------


class TestSQLInjection:
    def test_mission_name_injection(self, store):
        mid = store.create_mission("'; DROP TABLE missions; --", "romania")
        mission = store.get_mission(mid)
        assert mission["name"] == "'; DROP TABLE missions; --"
        assert len(store.list_missions()) == 1

    def test_target_type_injection(self, store):
        mid = store.create_mission("Op Alpha", "romania")
        store.log_target_event(mid, 1, "'; DROP TABLE target_events; --", "DETECTED")
        history = store.get_target_history(mid, 1)
        assert len(history) == 1


# ---------------------------------------------------------------------------
# Concurrent access
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_writes(self, tmp_path):
        db_path = str(tmp_path / "concurrent.db")
        store = MissionStore(db_path=db_path)
        mid = store.create_mission("Op Alpha", "romania")
        errors = []

        def writer(n):
            try:
                s = MissionStore(db_path=db_path)
                for i in range(10):
                    s.log_target_event(mid, n * 100 + i, "SAM", "DETECTED")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        summary = store.get_mission_summary(mid)
        assert summary["target_events"] == 30


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


class TestRESTEndpoints:
    @pytest.fixture
    def client(self, tmp_path):
        from unittest.mock import patch

        # Create a store for the test
        db_path = str(tmp_path / "rest_test.db")
        test_store = MissionStore(db_path=db_path)

        # Patch the module-level mission_store in api_main
        with patch("api_main.mission_store", test_store):
            from api_main import app
            from fastapi.testclient import TestClient

            yield TestClient(app), test_store

    def test_list_missions_empty(self, client):
        tc, _ = client
        resp = tc.get("/api/missions")
        assert resp.status_code == 200
        assert resp.json()["missions"] == []

    def test_create_mission_endpoint(self, client):
        tc, _ = client
        resp = tc.post("/api/missions", json={"name": "Op Alpha", "theater": "romania"})
        assert resp.status_code == 200
        data = resp.json()
        assert "mission_id" in data
        assert data["mission_id"] > 0

    def test_get_mission_endpoint(self, client):
        tc, store = client
        mid = store.create_mission("Op Alpha", "romania")
        resp = tc.get(f"/api/missions/{mid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission"]["name"] == "Op Alpha"
        assert "summary" in data

    def test_get_mission_not_found(self, client):
        tc, _ = client
        resp = tc.get("/api/missions/9999")
        assert resp.status_code == 404

    def test_get_target_history_endpoint(self, client):
        tc, store = client
        mid = store.create_mission("Op Alpha", "romania")
        store.log_target_event(mid, 5, "TEL", "DETECTED")
        store.log_target_event(mid, 5, "TEL", "CLASSIFIED")
        resp = tc.get(f"/api/missions/{mid}/targets/5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 2
