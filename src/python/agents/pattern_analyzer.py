"""
Pattern Analyzer Agent – Predictive Intelligence.

Analyses long-term historical adversary activity to identify anomalies
(e.g., supply-route frequency changes, new facilities, comms anomalies)
and triggers predictive alerts before a kinetic event occurs.
"""

import json
from datetime import datetime
from typing import Any

from schemas.ontology import PatternAnalyzerOutput
from mission_data.historical_activity import get_activity_summary, get_sector_activity


PATTERN_ANALYZER_PROMPT = """You are the Pattern Analyzer Agent for Project Antigravity. \
You operate as a predictive intelligence layer, looking for the 'unseen' \
by analysing long-term historical data rather than just immediate feeds.

Instructions:

1. System Focus: Identify deviations from established adversary movement \
   patterns within the sector you are assigned to assess.

2. Anomaly Detection: For every activity type in the historical log, \
   compute a baseline (average frequency and characteristics over the \
   earliest 75 % of records) and compare against the most recent 25 %. \
   Flag deviations that exceed ±30 % of baseline as anomalies.

3. Anomaly Categories:
   - Route Frequency Change – significant increase/decrease in convoy frequency.
   - New Facility – appearance of previously unobserved structures or earthworks.
   - Movement Surge – sudden spike in troop or vehicle movement volume.
   - Pattern Break – change in timing, direction, or composition vs. baseline.
   - Communications Anomaly – new frequencies, unusual burst patterns, or \
     co-located emitters.

4. Predictive Alerting: For every HIGH or CRITICAL anomaly, issue a \
   forward-looking alert stating the possible adversary intent and \
   recommended ISR re-tasking.

5. Reasoning Traces: Every anomaly MUST include a human-readable \
   'reasoning' string explaining *why* it constitutes a deviation.

Constraint: You must NOT recommend kinetic action. Your role is \
analytical and advisory only. \
Output must be strictly valid JSON matching the PatternAnalyzerOutput schema.
"""


class PatternAnalyzerAgent:
    """Predictive intelligence agent that detects adversary pattern anomalies."""

    def __init__(self, llm_client: Any):
        """
        Initialise the Pattern Analyzer Agent.

        Args:
            llm_client: An initialised LLM client (e.g., OpenAI, Anthropic,
                        or wrapped LiteLLM client).
        """
        self.llm_client = llm_client
        self.system_prompt = PATTERN_ANALYZER_PROMPT

    def _generate_response(self, historical_data: str, sector: str = "Unknown") -> str:
        """
        Wrapper to call the underlying LLM.
        Falls back to heuristic pattern analysis when llm_client is None.
        """
        if self.llm_client is not None:
            # Example for OpenAI client:
            # response = self.llm_client.beta.chat.completions.parse(
            #     model="gpt-4o",
            #     messages=[
            #         {"role": "system", "content": self.system_prompt},
            #         {"role": "user", "content": f"Historical Activity Log:\n{historical_data}"},
            #     ],
            #     response_format=PatternAnalyzerOutput,
            # )
            # return response.choices[0].message.content
            raise NotImplementedError("LLM integration needs to be completed.")

        return self._heuristic_pattern_analysis(historical_data, sector)

    def _heuristic_pattern_analysis(self, historical_data: str, sector: str = "Unknown") -> str:
        """Build pattern analysis from historical data without an LLM."""
        lines = historical_data.splitlines()
        total_records = 0

        if lines:
            header = lines[0]
            if "records" in header:
                for part in header.split():
                    if part.isdigit():
                        total_records = int(part)
                        break

        entries = get_sector_activity(sector)
        if not entries:
            output = {
                "anomalies": [],
                "sector_assessed": sector if sector != "Unknown" else "Unknown",
                "historical_window_days": 90,
                "predictive_alerts": [],
                "summary": f"No historical activity recorded for sector {sector}. No anomalies detected.",
            }
            return json.dumps(output)

        activity_counts: dict[str, list] = {}
        for e in entries:
            activity_counts.setdefault(e.activity_type, []).append(e)

        split_idx = int(len(entries) * 0.75)
        baseline_entries = entries[:split_idx]
        recent_entries = entries[split_idx:]

        baseline_counts: dict[str, int] = {}
        for e in baseline_entries:
            baseline_counts[e.activity_type] = baseline_counts.get(e.activity_type, 0) + 1

        recent_counts: dict[str, int] = {}
        for e in recent_entries:
            recent_counts[e.activity_type] = recent_counts.get(e.activity_type, 0) + 1

        anomalies = []
        predictive_alerts = []
        anomaly_seq = 1

        for activity_type, baseline_n in baseline_counts.items():
            recent_n = recent_counts.get(activity_type, 0)
            baseline_rate = baseline_n / max(split_idx, 1)
            recent_rate = recent_n / max(len(recent_entries), 1)

            if baseline_rate == 0:
                continue

            deviation_pct = ((recent_rate - baseline_rate) / baseline_rate) * 100.0

            if abs(deviation_pct) < 30.0:
                continue

            severity = "HIGH" if abs(deviation_pct) >= 100 else "MEDIUM"
            first_recent = next(
                (e for e in entries[split_idx:] if e.activity_type == activity_type),
                entries[-1],
            )

            anomaly_type_map = {
                "Supply Convoy": "Route Frequency Change",
                "COMMS Intercept": "Communications Anomaly",
                "Facility Construction": "New Facility",
            }
            anom_type = anomaly_type_map.get(activity_type, "Pattern Break")

            anomaly = {
                "anomaly_id": f"ANOM-{anomaly_seq:03d}",
                "anomaly_type": anom_type,
                "sector": sector,
                "description": (
                    f"{activity_type} frequency deviation of {deviation_pct:+.0f}% "
                    f"vs baseline in sector {sector}."
                ),
                "severity": severity,
                "baseline_value": round(baseline_rate, 3),
                "observed_value": round(recent_rate, 3),
                "deviation_pct": round(deviation_pct, 1),
                "first_observed": first_recent.timestamp,
                "reasoning": (
                    f"Baseline rate was {baseline_rate:.2f} events/record over {split_idx} records. "
                    f"Recent rate is {recent_rate:.2f} events/record over {len(recent_entries)} records "
                    f"— a {deviation_pct:+.0f}% deviation exceeding the 30% threshold."
                ),
            }
            anomalies.append(anomaly)
            anomaly_seq += 1

            if severity in ("HIGH", "CRITICAL"):
                predictive_alerts.append(
                    f"Possible pre-offensive preparation: {activity_type} surge in sector {sector}. "
                    "Recommend ISR re-tasking to confirm intent."
                )

        for activity_type in recent_counts:
            if activity_type not in baseline_counts:
                recent_n = recent_counts[activity_type]
                first_recent = next(
                    (e for e in entries[split_idx:] if e.activity_type == activity_type),
                    entries[-1],
                )
                anom_type_map = {
                    "Facility Construction": "New Facility",
                    "COMMS Intercept": "Communications Anomaly",
                }
                anom_type = anom_type_map.get(activity_type, "Pattern Break")
                anomaly = {
                    "anomaly_id": f"ANOM-{anomaly_seq:03d}",
                    "anomaly_type": anom_type,
                    "sector": sector,
                    "description": (
                        f"New activity type '{activity_type}' observed in sector {sector} — "
                        "not present in baseline period."
                    ),
                    "severity": "CRITICAL",
                    "baseline_value": 0.0,
                    "observed_value": float(recent_n),
                    "deviation_pct": 100.0,
                    "first_observed": first_recent.timestamp,
                    "reasoning": (
                        f"'{activity_type}' was not observed in the baseline period. "
                        f"First detected at {first_recent.timestamp} — a new pattern."
                    ),
                }
                anomalies.append(anomaly)
                anomaly_seq += 1
                predictive_alerts.append(
                    f"New activity '{activity_type}' in sector {sector} — no prior baseline. "
                    "Immediate ISR tasking recommended."
                )

        summary = (
            f"Sector {sector} assessment over 90 days ({total_records or len(entries)} records). "
            f"{len(anomalies)} anomaly(ies) detected."
            + (" Possible pre-kinetic indicators present." if predictive_alerts else " No significant alerts.")
        )

        output = {
            "anomalies": anomalies,
            "sector_assessed": sector,
            "historical_window_days": 90,
            "predictive_alerts": predictive_alerts,
            "summary": summary,
        }
        return json.dumps(output)

    def analyze_patterns(self, sector: str = "Bravo") -> PatternAnalyzerOutput:
        """
        Fetch historical activity for the requested sector, send it to the
        LLM for anomaly analysis, and return a structured output.
        """
        historical_data = get_activity_summary(sector)
        response_content = self._generate_response(historical_data, sector)
        return PatternAnalyzerOutput.model_validate_json(response_content)
