"""
Tests for the Pattern Analyzer agent, schemas, and historical data store.
"""

from unittest.mock import MagicMock

import pytest
from agents.pattern_analyzer import PatternAnalyzerAgent
from data.historical_activity import (
    get_activity_summary,
    get_sector_activity,
)
from schemas.ontology import (
    AlertSeverity,
    AnomalyType,
    PatternAnalyzerOutput,
    PatternAnomaly,
)

# ── Schema validation tests ──────────────────────────────────────────────────


class TestPatternAnomalySchema:
    """Verify PatternAnomaly accepts valid data and rejects invalid data."""

    def _make_anomaly(self, **overrides) -> dict:
        defaults = {
            "anomaly_id": "ANOM-001",
            "anomaly_type": AnomalyType.ROUTE_FREQUENCY_CHANGE,
            "sector": "Bravo",
            "description": "Supply convoy frequency increased 200%.",
            "severity": AlertSeverity.HIGH,
            "baseline_value": 3.0,
            "observed_value": 9.0,
            "deviation_pct": 200.0,
            "first_observed": "2026-01-08T04:00:00Z",
            "reasoning": "Baseline is 3 convoys/week; observed 9 in last 7 days.",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_anomaly(self):
        anomaly = PatternAnomaly(**self._make_anomaly())
        assert anomaly.anomaly_id == "ANOM-001"
        assert anomaly.anomaly_type == AnomalyType.ROUTE_FREQUENCY_CHANGE
        assert anomaly.severity == AlertSeverity.HIGH

    def test_all_anomaly_types(self):
        for atype in AnomalyType:
            anomaly = PatternAnomaly(**self._make_anomaly(anomaly_type=atype))
            assert anomaly.anomaly_type == atype

    def test_all_severity_levels(self):
        for sev in AlertSeverity:
            anomaly = PatternAnomaly(**self._make_anomaly(severity=sev))
            assert anomaly.severity == sev

    def test_invalid_anomaly_type_rejected(self):
        with pytest.raises(Exception):
            PatternAnomaly(**self._make_anomaly(anomaly_type="InvalidType"))

    def test_invalid_severity_rejected(self):
        with pytest.raises(Exception):
            PatternAnomaly(**self._make_anomaly(severity="EXTREME"))


class TestPatternAnalyzerOutputSchema:
    """Verify PatternAnalyzerOutput model."""

    def test_valid_output(self):
        anomaly = PatternAnomaly(
            anomaly_id="ANOM-002",
            anomaly_type=AnomalyType.NEW_FACILITY,
            sector="Bravo",
            description="New earthworks detected.",
            severity=AlertSeverity.CRITICAL,
            baseline_value=0.0,
            observed_value=1.0,
            deviation_pct=100.0,
            first_observed="2026-01-09T09:00:00Z",
            reasoning="No prior facilities at this grid; new construction observed.",
        )
        output = PatternAnalyzerOutput(
            anomalies=[anomaly],
            sector_assessed="Bravo",
            historical_window_days=90,
            predictive_alerts=["Possible TEL shelter under construction at 33.46N 44.43E."],
            summary="Sector Bravo shows significant deviation from baseline.",
        )
        assert output.sector_assessed == "Bravo"
        assert len(output.anomalies) == 1
        assert output.historical_window_days == 90

    def test_empty_anomalies_list(self):
        output = PatternAnalyzerOutput(
            anomalies=[],
            sector_assessed="Alpha",
            historical_window_days=30,
            summary="No anomalies detected in sector Alpha.",
        )
        assert len(output.anomalies) == 0
        assert output.predictive_alerts == []


# ── Historical data store tests ──────────────────────────────────────────────


class TestHistoricalActivity:
    """Verify the simulated historical activity data store."""

    def test_bravo_entries_exist(self):
        bravo = get_sector_activity("Bravo")
        assert len(bravo) > 0
        assert all(a.sector == "Bravo" for a in bravo)

    def test_alpha_entries_exist(self):
        alpha = get_sector_activity("Alpha")
        assert len(alpha) > 0
        assert all(a.sector == "Alpha" for a in alpha)

    def test_unknown_sector_returns_empty(self):
        assert get_sector_activity("Zulu") == []

    def test_activity_summary_format(self):
        summary = get_activity_summary("Bravo")
        assert "Sector Bravo" in summary
        assert "Supply Convoy" in summary

    def test_activity_summary_empty_sector(self):
        summary = get_activity_summary("Zulu")
        assert "No historical activity" in summary


# ── Agent instantiation tests ────────────────────────────────────────────────


class TestPatternAnalyzerAgent:
    """Verify agent construction and method existence."""

    def test_agent_initialises(self):
        mock_client = MagicMock()
        agent = PatternAnalyzerAgent(mock_client)
        assert agent.llm_client is mock_client
        assert "Pattern Analyzer" in agent.system_prompt

    def test_analyze_patterns_raises_not_implemented(self):
        mock_client = MagicMock()
        agent = PatternAnalyzerAgent(mock_client)
        with pytest.raises(NotImplementedError):
            agent.analyze_patterns("Bravo")
