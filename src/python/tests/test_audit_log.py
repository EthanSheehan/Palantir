"""Tests for the structured audit trail (W3-002)."""

from __future__ import annotations

import json
import threading
from datetime import datetime

import pytest


@pytest.fixture
def audit_log():
    from audit_log import AuditLog

    return AuditLog()


@pytest.fixture
def populated_log(audit_log):
    audit_log.append("NOMINATION_APPROVED", autonomy_level="SUPERVISED", target_id=1, details={"reason": "high threat"})
    audit_log.append("COA_AUTHORIZED", autonomy_level="SUPERVISED", target_id=1, drone_id=3, details={"coa": "COA-1"})
    audit_log.append(
        "ENGAGEMENT_INITIATED", autonomy_level="AUTONOMOUS", target_id=2, drone_id=5, details={"weapon": "JDAM"}
    )
    audit_log.append("OPERATOR_OVERRIDE", autonomy_level="MANUAL", target_id=3, details={"action": "reject"})
    audit_log.append("ROE_VETO", autonomy_level="SUPERVISED", target_id=4, details={"rule": "ROE-3"})
    return audit_log


# ---------------------------------------------------------------------------
# Record creation
# ---------------------------------------------------------------------------


class TestRecordCreation:
    def test_record_has_all_fields(self, audit_log):
        audit_log.append("NOMINATION_APPROVED", autonomy_level="SUPERVISED", target_id=1, details={"x": 1})
        records = audit_log.to_json()
        assert len(records) == 1
        r = records[0]
        assert "timestamp" in r
        assert r["action_type"] == "NOMINATION_APPROVED"
        assert r["autonomy_level"] == "SUPERVISED"
        assert r["target_id"] == 1
        assert r["details"] == {"x": 1}
        assert "record_hash" in r
        assert "prev_hash" in r

    def test_record_is_frozen(self):
        from audit_log import AuditRecord

        r = AuditRecord(
            timestamp="2026-01-01T00:00:00Z",
            action_type="TEST",
            autonomy_level="MANUAL",
            target_id=None,
            drone_id=None,
            operator_id=None,
            sensor_evidence=None,
            hitl_status=None,
            details={},
            prev_hash="0" * 64,
            record_hash="a" * 64,
        )
        with pytest.raises(AttributeError):
            r.action_type = "CHANGED"

    def test_first_record_prev_hash_is_zeros(self, audit_log):
        audit_log.append("TEST", autonomy_level="MANUAL", details={})
        records = audit_log.to_json()
        assert records[0]["prev_hash"] == "0" * 64

    def test_timestamp_is_iso8601(self, audit_log):
        audit_log.append("TEST", autonomy_level="MANUAL", details={})
        ts = audit_log.to_json()[0]["timestamp"]
        datetime.fromisoformat(ts)

    def test_optional_fields_default_none(self, audit_log):
        audit_log.append("TEST", autonomy_level="MANUAL", details={})
        r = audit_log.to_json()[0]
        assert r["target_id"] is None
        assert r["drone_id"] is None
        assert r["operator_id"] is None
        assert r["sensor_evidence"] is None
        assert r["hitl_status"] is None

    def test_sensor_evidence_stored(self, audit_log):
        evidence = {"eo_ir": 0.8, "sar": 0.6}
        audit_log.append("TEST", autonomy_level="MANUAL", sensor_evidence=evidence, details={})
        r = audit_log.to_json()[0]
        assert r["sensor_evidence"] == evidence


# ---------------------------------------------------------------------------
# Hash chain integrity
# ---------------------------------------------------------------------------


class TestHashChain:
    def test_hash_chain_valid_single_record(self, audit_log):
        audit_log.append("TEST", autonomy_level="MANUAL", details={})
        assert audit_log.verify_chain() is True

    def test_hash_chain_valid_multiple_records(self, populated_log):
        assert populated_log.verify_chain() is True

    def test_second_record_prev_hash_matches_first_record_hash(self, audit_log):
        audit_log.append("FIRST", autonomy_level="MANUAL", details={})
        audit_log.append("SECOND", autonomy_level="MANUAL", details={})
        records = audit_log.to_json()
        assert records[1]["prev_hash"] == records[0]["record_hash"]

    def test_tamper_detection_modify_action_type(self, populated_log):
        from dataclasses import replace

        original = populated_log._records[1]
        tampered = replace(original, action_type="TAMPERED")
        populated_log._records[1] = tampered
        assert populated_log.verify_chain() is False

    def test_tamper_detection_modify_details(self, populated_log):
        from dataclasses import replace

        original = populated_log._records[0]
        tampered = replace(original, details={"tampered": True})
        populated_log._records[0] = tampered
        assert populated_log.verify_chain() is False

    def test_tamper_detection_swap_records(self, populated_log):
        populated_log._records[1], populated_log._records[2] = (
            populated_log._records[2],
            populated_log._records[1],
        )
        assert populated_log.verify_chain() is False

    def test_verify_empty_log(self, audit_log):
        assert audit_log.verify_chain() is True

    def test_hash_is_sha256(self, audit_log):
        audit_log.append("TEST", autonomy_level="MANUAL", details={})
        h = audit_log.to_json()[0]["record_hash"]
        assert len(h) == 64
        int(h, 16)  # valid hex


# ---------------------------------------------------------------------------
# Query filters
# ---------------------------------------------------------------------------


class TestQuery:
    def test_query_by_action_type(self, populated_log):
        results = populated_log.query(action_type="NOMINATION_APPROVED")
        assert len(results) == 1
        assert results[0]["action_type"] == "NOMINATION_APPROVED"

    def test_query_by_autonomy_level(self, populated_log):
        results = populated_log.query(autonomy_level="SUPERVISED")
        assert len(results) == 3

    def test_query_by_target_id(self, populated_log):
        results = populated_log.query(target_id=2)
        assert len(results) == 1
        assert results[0]["action_type"] == "ENGAGEMENT_INITIATED"

    def test_query_by_time_range(self, populated_log):
        all_records = populated_log.to_json()
        mid_ts = all_records[2]["timestamp"]
        results = populated_log.query(start_time=mid_ts)
        assert len(results) >= 3

    def test_query_by_end_time(self, populated_log):
        all_records = populated_log.to_json()
        mid_ts = all_records[1]["timestamp"]
        results = populated_log.query(end_time=mid_ts)
        assert len(results) <= 2

    def test_query_combined_filters(self, populated_log):
        results = populated_log.query(autonomy_level="SUPERVISED", target_id=1)
        assert len(results) == 2
        for r in results:
            assert r["autonomy_level"] == "SUPERVISED"
            assert r["target_id"] == 1

    def test_query_no_match(self, populated_log):
        results = populated_log.query(action_type="NONEXISTENT")
        assert results == []

    def test_query_no_filters_returns_all(self, populated_log):
        results = populated_log.query()
        assert len(results) == 5

    def test_query_empty_log(self, audit_log):
        results = audit_log.query(action_type="TEST")
        assert results == []


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_json_returns_list_of_dicts(self, populated_log):
        result = populated_log.to_json()
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_to_json_empty_log(self, audit_log):
        assert audit_log.to_json() == []

    def test_to_json_is_json_serializable(self, populated_log):
        result = populated_log.to_json()
        json.dumps(result)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_appends(self):
        from audit_log import AuditLog

        log = AuditLog()
        errors = []

        def append_records(n):
            try:
                for i in range(n):
                    log.append(f"ACTION_{threading.current_thread().name}", autonomy_level="MANUAL", details={"i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=append_records, args=(20,), name=f"t{i}") for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(log.to_json()) == 100
        assert log.verify_chain() is True


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------


class TestRESTEndpoints:
    @pytest.fixture
    def client(self):
        import sys

        # Ensure fresh import with audit_log available
        if "api_main" in sys.modules:
            # Use existing module
            from api_main import app
        else:
            from api_main import app

        from starlette.testclient import TestClient

        return TestClient(app)

    def test_get_audit_returns_list(self, client):
        resp = client.get("/api/audit")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_audit_verify(self, client):
        resp = client.get("/api/audit/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert "valid" in body
        assert "record_count" in body
        assert body["valid"] is True

    def test_get_audit_filter_by_action_type(self, client):
        resp = client.get("/api/audit", params={"action_type": "NOMINATION_APPROVED"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_audit_filter_by_target_id(self, client):
        resp = client.get("/api/audit", params={"target_id": "1"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_audit_filter_by_autonomy_level(self, client):
        resp = client.get("/api/audit", params={"autonomy_level": "SUPERVISED"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
