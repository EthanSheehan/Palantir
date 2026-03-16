"""
Historical Activity Log – simulated adversary activity records for sector Bravo.

In production this would be backed by a time-series database or ISR data lake.
Each entry represents a recorded adversary activity event used by the
Pattern Analyzer for baseline comparison and anomaly detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class AdversaryActivity:
    """A single historical adversary activity observation."""
    timestamp: str          # ISO 8601
    sector: str             # e.g., "Bravo", "Alpha"
    activity_type: str      # e.g., "Supply Convoy", "Facility Construction"
    lat: float
    lon: float
    details: str


# ---------------------------------------------------------------------------
# 90-day simulated log for development / demo.  Replace with DB queries.
# ---------------------------------------------------------------------------
HISTORICAL_LOG: list[AdversaryActivity] = [
    # ── Sector Bravo: Supply route traffic (steady baseline ~3/week) ─────
    AdversaryActivity("2025-12-15T06:00:00Z", "Bravo", "Supply Convoy", 33.42, 44.38, "3-vehicle convoy observed on Route Amber heading NE."),
    AdversaryActivity("2025-12-18T14:30:00Z", "Bravo", "Supply Convoy", 33.43, 44.39, "2-vehicle convoy on Route Amber, same direction."),
    AdversaryActivity("2025-12-22T07:15:00Z", "Bravo", "Supply Convoy", 33.42, 44.37, "4-vehicle convoy including possible fuel tanker."),
    AdversaryActivity("2025-12-26T05:45:00Z", "Bravo", "Supply Convoy", 33.44, 44.40, "3-vehicle convoy, routine pattern."),
    AdversaryActivity("2025-12-30T08:00:00Z", "Bravo", "Supply Convoy", 33.42, 44.38, "2-vehicle convoy, standard load."),
    AdversaryActivity("2026-01-03T06:30:00Z", "Bravo", "Supply Convoy", 33.43, 44.39, "3-vehicle convoy, matches previous weeks."),

    # ── Sector Bravo: COMMS intercepts (baseline ~1/week) ────────────────
    AdversaryActivity("2025-12-20T22:00:00Z", "Bravo", "COMMS Intercept", 33.45, 44.42, "Routine encrypted burst on known freq 147.3 MHz."),
    AdversaryActivity("2025-12-28T23:10:00Z", "Bravo", "COMMS Intercept", 33.45, 44.42, "Standard comms burst, duration 12s."),
    AdversaryActivity("2026-01-05T21:45:00Z", "Bravo", "COMMS Intercept", 33.45, 44.42, "Burst detected, amplitude consistent with baseline."),

    # ── Sector Bravo: ANOMALOUS recent data ──────────────────────────────
    AdversaryActivity("2026-01-08T04:00:00Z", "Bravo", "Supply Convoy", 33.42, 44.38, "5-vehicle convoy, unusually large — includes 2 covered HETs."),
    AdversaryActivity("2026-01-09T03:30:00Z", "Bravo", "Supply Convoy", 33.44, 44.40, "4-vehicle convoy with military escort, night movement."),
    AdversaryActivity("2026-01-10T02:15:00Z", "Bravo", "Supply Convoy", 33.42, 44.37, "6-vehicle convoy observed — frequency +200% vs baseline."),
    AdversaryActivity("2026-01-09T09:00:00Z", "Bravo", "Facility Construction", 33.46, 44.43, "New earthworks detected at grid 33.46N 44.43E, possible hardened shelter."),
    AdversaryActivity("2026-01-10T11:00:00Z", "Bravo", "Facility Construction", 33.46, 44.43, "Construction activity continued; perimeter fencing observed."),
    AdversaryActivity("2026-01-10T22:30:00Z", "Bravo", "COMMS Intercept", 33.45, 44.42, "Unusual burst pattern — 4 transmissions in 2 hrs on new freq 152.7 MHz."),
    AdversaryActivity("2026-01-10T23:45:00Z", "Bravo", "COMMS Intercept", 33.46, 44.43, "New emitter co-located with construction site."),

    # ── Sector Alpha: control data (for filtering tests) ─────────────────
    AdversaryActivity("2025-12-17T10:00:00Z", "Alpha", "Supply Convoy", 34.10, 43.80, "2-vehicle convoy observed on Route Crimson."),
    AdversaryActivity("2025-12-25T08:30:00Z", "Alpha", "Patrol", 34.12, 43.82, "Foot patrol, 6 personnel, routine movement."),
    AdversaryActivity("2026-01-02T14:00:00Z", "Alpha", "Supply Convoy", 34.11, 43.81, "3-vehicle convoy, standard pattern."),
]


def get_sector_activity(sector: str) -> list[AdversaryActivity]:
    """Return all historical activity for the given sector."""
    return [a for a in HISTORICAL_LOG if a.sector == sector]


def get_activity_summary(sector: str) -> str:
    """
    Format the sector's historical activity log into a text block
    suitable for LLM consumption by the Pattern Analyzer.
    """
    entries = get_sector_activity(sector)
    if not entries:
        return f"No historical activity recorded for sector {sector}."

    lines = [f"Historical Activity Log — Sector {sector} ({len(entries)} records)\n"]
    for e in entries:
        lines.append(
            f"[{e.timestamp}] {e.activity_type} | "
            f"({e.lat:.2f}, {e.lon:.2f}) | {e.details}"
        )
    return "\n".join(lines)
