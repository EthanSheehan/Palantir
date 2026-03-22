"""Tests for the Export/Reporting Module (W5-008)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def targets():
    return [
        {
            "id": 1,
            "type": "SAM",
            "state": "DESTROYED",
            "lat": 44.0,
            "lon": 26.0,
            "detected_at": "2026-03-21T10:00:00+00:00",
            "verified_at": "2026-03-21T10:05:00+00:00",
            "engaged_at": "2026-03-21T10:10:00+00:00",
            "destroyed_at": "2026-03-21T10:12:00+00:00",
            "kill_chain_phase": "ASSESS",
        },
        {
            "id": 2,
            "type": "TEL",
            "state": "VERIFIED",
            "lat": 44.5,
            "lon": 26.5,
            "detected_at": "2026-03-21T10:15:00+00:00",
            "verified_at": "2026-03-21T10:20:00+00:00",
            "engaged_at": None,
            "destroyed_at": None,
            "kill_chain_phase": "TARGET",
        },
    ]


@pytest.fixture
def engagements():
    return [
        {
            "target_id": 1,
            "drone_id": 3,
            "timestamp": "2026-03-21T10:10:00+00:00",
            "outcome": "HIT",
            "coa_id": "COA-001",
            "autonomy_level": "AUTONOMOUS",
        },
        {
            "target_id": 2,
            "drone_id": 5,
            "timestamp": "2026-03-21T10:25:00+00:00",
            "outcome": "MISS",
            "coa_id": "COA-002",
            "autonomy_level": "SUPERVISED",
        },
    ]


@pytest.fixture
def audit_entries():
    return [
        {
            "timestamp": "2026-03-21T10:01:00+00:00",
            "action_type": "NOMINATION_APPROVED",
            "autonomy_level": "SUPERVISED",
            "target_id": 1,
            "drone_id": 3,
            "operator_id": "op-1",
            "hitl_status": "APPROVED",
            "details": {"reason": "high threat"},
            "record_hash": "abc123",
            "prev_hash": "0" * 64,
        },
        {
            "timestamp": "2026-03-21T10:05:00+00:00",
            "action_type": "AUTHORIZE_COA",
            "autonomy_level": "AUTONOMOUS",
            "target_id": 1,
            "drone_id": 3,
            "operator_id": None,
            "hitl_status": "AUTO",
            "details": {"coa": "COA-001"},
            "record_hash": "def456",
            "prev_hash": "abc123",
        },
    ]


# ---------------------------------------------------------------------------
# JSON format — target lifecycle
# ---------------------------------------------------------------------------


class TestTargetLifecycleJSON:
    def test_generate_returns_string(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="json")
        assert isinstance(result, str)

    def test_json_is_valid(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="json")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_contains_report_type(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        assert result.get("report_type") == "target_lifecycle"

    def test_json_contains_generated_at_timestamp(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        assert "generated_at" in result
        datetime.fromisoformat(result["generated_at"])

    def test_json_contains_records(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        assert "records" in result
        assert len(result["records"]) == 2

    def test_json_record_has_id_and_state(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        first = result["records"][0]
        assert first["id"] == 1
        assert first["state"] == "DESTROYED"

    def test_json_record_contains_kill_chain_phase(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        for rec in result["records"]:
            assert "kill_chain_phase" in rec

    def test_empty_targets_produces_empty_records(self):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report([], fmt="json"))
        assert result["records"] == []

    def test_json_has_summary_count(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_target_report(targets, fmt="json"))
        assert result.get("total_targets") == 2


# ---------------------------------------------------------------------------
# CSV format — target lifecycle
# ---------------------------------------------------------------------------


class TestTargetLifecycleCSV:
    def test_csv_is_string(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="csv")
        assert isinstance(result, str)

    def test_csv_has_header_row(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="csv")
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) >= 1
        headers = rows[0]
        assert "id" in headers
        assert "state" in headers

    def test_csv_row_count_matches_targets(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="csv")
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        # header + 2 data rows
        assert len(rows) == 3

    def test_csv_empty_targets_has_only_header(self):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report([], fmt="csv")
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1

    def test_csv_values_match_target_data(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="csv")
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert rows[0]["id"] == "1"
        assert rows[0]["state"] == "DESTROYED"

    def test_csv_kill_chain_phase_in_headers(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_target_report(targets, fmt="csv")
        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "kill_chain_phase" in headers


# ---------------------------------------------------------------------------
# Engagement outcomes report
# ---------------------------------------------------------------------------


class TestEngagementOutcomesReport:
    def test_engagement_json_valid(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_engagement_report(engagements, fmt="json")
        parsed = json.loads(result)
        assert parsed.get("report_type") == "engagement_outcomes"

    def test_engagement_json_has_records(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_engagement_report(engagements, fmt="json"))
        assert len(result["records"]) == 2

    def test_engagement_json_outcome_field(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_engagement_report(engagements, fmt="json"))
        outcomes = {r["target_id"]: r["outcome"] for r in result["records"]}
        assert outcomes[1] == "HIT"
        assert outcomes[2] == "MISS"

    def test_engagement_json_has_timestamp(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_engagement_report(engagements, fmt="json"))
        assert "generated_at" in result
        datetime.fromisoformat(result["generated_at"])

    def test_engagement_csv_has_outcome_header(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_engagement_report(engagements, fmt="csv")
        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "outcome" in headers

    def test_engagement_empty_data_valid(self):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_engagement_report([], fmt="json"))
        assert result["records"] == []

    def test_engagement_summary_hit_miss_count(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_engagement_report(engagements, fmt="json"))
        summary = result.get("summary", {})
        assert summary.get("total") == 2


# ---------------------------------------------------------------------------
# AI decision audit trail report
# ---------------------------------------------------------------------------


class TestAuditTrailReport:
    def test_audit_json_valid(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_audit_report(audit_entries, fmt="json")
        parsed = json.loads(result)
        assert parsed.get("report_type") == "ai_decision_audit"

    def test_audit_json_has_records(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report(audit_entries, fmt="json"))
        assert len(result["records"]) == 2

    def test_audit_record_has_action_type(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report(audit_entries, fmt="json"))
        assert result["records"][0]["action_type"] == "NOMINATION_APPROVED"

    def test_audit_record_has_autonomy_level(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report(audit_entries, fmt="json"))
        autonomy = {r["action_type"]: r["autonomy_level"] for r in result["records"]}
        assert autonomy["NOMINATION_APPROVED"] == "SUPERVISED"
        assert autonomy["AUTHORIZE_COA"] == "AUTONOMOUS"

    def test_audit_json_has_timestamp(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report(audit_entries, fmt="json"))
        assert "generated_at" in result
        datetime.fromisoformat(result["generated_at"])

    def test_audit_csv_has_action_type_header(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = rg.generate_audit_report(audit_entries, fmt="csv")
        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "action_type" in headers
        assert "autonomy_level" in headers

    def test_audit_empty_data_valid(self):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report([], fmt="json"))
        assert result["records"] == []

    def test_audit_record_has_record_hash(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        result = json.loads(rg.generate_audit_report(audit_entries, fmt="json"))
        assert "record_hash" in result["records"][0]


# ---------------------------------------------------------------------------
# Purity — no side effects
# ---------------------------------------------------------------------------


class TestPurity:
    def test_target_report_does_not_mutate_input(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        original = [dict(t) for t in targets]
        rg.generate_target_report(targets, fmt="json")
        assert targets == original

    def test_engagement_report_does_not_mutate_input(self, engagements):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        original = [dict(e) for e in engagements]
        rg.generate_engagement_report(engagements, fmt="json")
        assert engagements == original

    def test_audit_report_does_not_mutate_input(self, audit_entries):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        original = [dict(a) for a in audit_entries]
        rg.generate_audit_report(audit_entries, fmt="json")
        assert audit_entries == original

    def test_multiple_calls_same_result_structure(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        r1 = json.loads(rg.generate_target_report(targets, fmt="json"))
        r2 = json.loads(rg.generate_target_report(targets, fmt="json"))
        assert r1["records"] == r2["records"]
        assert r1["total_targets"] == r2["total_targets"]

    def test_unsupported_format_raises(self, targets):
        from report_generator import ReportGenerator

        rg = ReportGenerator()
        with pytest.raises(ValueError, match="Unsupported format"):
            rg.generate_target_report(targets, fmt="xml")
