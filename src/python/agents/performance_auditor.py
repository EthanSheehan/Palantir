"""
Performance Auditor Agent
=========================
Watchdog of the Process Improvement Flywheel.
Audits every kill chain by comparing BDA outcomes against original nominations,
detecting model drift, and producing weekly health reports.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from schemas.ontology import (
    BDAReport,
    DiscrepancyFlag,
    DriftAlert,
    EffectOutcome,
    FlywheelHealthReport,
    StrategyNomination,
    TargetClassification,
    Track,
)


PERFORMANCE_AUDITOR_PROMPT = """You are the Performance Auditor Agent. You are the watchdog of the 'Process Improvement Flywheel'.

Instructions:

Outcome Analysis: Compare the 'Effectors Agent's' BDA report against the 'Strategy Analyst's' original nomination.

Discrepancy Flagging: If a strike was approved but failed to achieve the predicted effect, flag the 'Tactical Planner's' COA logic for manual review.

Drift Detection: Monitor the 'ISR Observer's' confidence scores over time. If confidence in identifying a specific target type (e.g., a T-72 tank) drops below 80%, trigger an alert to generate new training data.

Reporting: Produce a weekly 'Flywheel Health Report' summarising the reduction in human labour and the increase in decision speed.
"""

# Default confidence threshold for drift detection (80%).
DRIFT_CONFIDENCE_THRESHOLD = 0.80


class PerformanceAuditorAgent:
    """Audits kill-chain outcomes, flags discrepancies, and detects model drift."""

    def __init__(self, llm_client: Any = None):
        """
        Initialise the Performance Auditor Agent.

        Args:
            llm_client: Optional LLM client for advanced analysis (future use).
        """
        self.llm_client = llm_client
        self.system_prompt = PERFORMANCE_AUDITOR_PROMPT
        self.confidence_threshold = DRIFT_CONFIDENCE_THRESHOLD

        # In-memory stores for auditing (replace with persistent storage in production).
        self._discrepancy_flags: List[DiscrepancyFlag] = []
        self._drift_alerts: List[DriftAlert] = []

    # ------------------------------------------------------------------
    # 1. Outcome Analysis
    # ------------------------------------------------------------------
    def compare_outcome(
        self,
        bda_report: BDAReport,
        nomination: StrategyNomination,
    ) -> DiscrepancyFlag | None:
        """
        Compare a BDA report against the original Strategy Analyst nomination.

        Returns a DiscrepancyFlag if the observed effect does not match the
        predicted effect, otherwise returns None.
        """
        if bda_report.effect_achieved == nomination.predicted_effect:
            return None

        flag = DiscrepancyFlag(
            flag_id=f"DISC-{uuid.uuid4().hex[:8].upper()}",
            bda_id=bda_report.bda_id,
            nomination_id=nomination.nomination_id,
            coa_id=bda_report.coa_id,
            predicted_effect=nomination.predicted_effect,
            actual_effect=bda_report.effect_achieved,
            requires_manual_review=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._discrepancy_flags.append(flag)
        return flag

    # ------------------------------------------------------------------
    # 2. Drift Detection
    # ------------------------------------------------------------------
    def check_confidence_drift(
        self,
        tracks: List[Track],
        target_type: TargetClassification | None = None,
    ) -> List[DriftAlert]:
        """
        Monitor ISR Observer confidence scores for a given target type.
        If the average confidence drops below the threshold, return a DriftAlert.

        Args:
            tracks: Recent tracks from the ISR Observer.
            target_type: Specific classification to check. If None, checks all types.
        """
        alerts: List[DriftAlert] = []
        types_to_check = [target_type] if target_type else list(TargetClassification)

        for t_type in types_to_check:
            matching = [t for t in tracks if t.classification == t_type]
            if not matching:
                continue

            avg_conf = sum(t.confidence for t in matching) / len(matching)
            if avg_conf < self.confidence_threshold:
                alert = DriftAlert(
                    alert_id=f"DRIFT-{uuid.uuid4().hex[:8].upper()}",
                    target_classification=t_type,
                    current_avg_confidence=round(avg_conf, 4),
                    threshold=self.confidence_threshold,
                    sample_count=len(matching),
                    recommendation=f"Generate new training data for {t_type.value} classification",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                alerts.append(alert)
                self._drift_alerts.append(alert)

        return alerts

    # ------------------------------------------------------------------
    # 3. Weekly Flywheel Health Report
    # ------------------------------------------------------------------
    def generate_health_report(
        self,
        period_start: str,
        period_end: str,
        total_kill_chains: int,
        successful_outcomes: int,
        avg_decision_speed_seconds: float,
        prior_avg_decision_speed_seconds: float,
        labor_reduction_pct: float,
    ) -> FlywheelHealthReport:
        """
        Produce a weekly Flywheel Health Report summarising system performance.

        Args:
            period_start: ISO 8601 start of the reporting window.
            period_end: ISO 8601 end of the reporting window.
            total_kill_chains: Total kill chains audited this period.
            successful_outcomes: Kill chains where effect matched prediction.
            avg_decision_speed_seconds: Average time from detection to engagement.
            prior_avg_decision_speed_seconds: Same metric from the prior period.
            labor_reduction_pct: Estimated reduction in human eyes-on-glass time.
        """
        if prior_avg_decision_speed_seconds > 0:
            delta = (
                (avg_decision_speed_seconds - prior_avg_decision_speed_seconds)
                / prior_avg_decision_speed_seconds
            ) * 100.0
        else:
            delta = 0.0

        report = FlywheelHealthReport(
            report_id=f"FHR-{uuid.uuid4().hex[:8].upper()}",
            reporting_period_start=period_start,
            reporting_period_end=period_end,
            total_kill_chains_audited=total_kill_chains,
            successful_outcomes=successful_outcomes,
            discrepancies_flagged=len(self._discrepancy_flags),
            drift_alerts_triggered=len(self._drift_alerts),
            avg_decision_speed_seconds=round(avg_decision_speed_seconds, 2),
            decision_speed_delta_pct=round(delta, 2),
            labor_reduction_pct=round(labor_reduction_pct, 2),
            flags=list(self._discrepancy_flags),
            drift_alerts=list(self._drift_alerts),
        )

        # Reset accumulators after report generation.
        self._discrepancy_flags.clear()
        self._drift_alerts.clear()

        return report
