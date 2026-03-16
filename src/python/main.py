"""
main.py
=======
LangGraph application — wires the Strategy Analyst into a runnable graph.

Usage (from project root):
    source venv/bin/activate
    python -m src.python.main
"""

from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph

from src.python.agents.strategy_analyst import evaluate_detections
from src.python.core.ontology import (
    Detection,
    DetectionType,
    FriendlyForce,
    IdentityClassification,
    Location,
    ROEAction,
    RuleOfEngagement,
    SensorType,
)
from src.python.core.state import AnalystState


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Build and compile the Strategy Analyst LangGraph."""
    graph = StateGraph(AnalystState)

    # Single node for now — additional agents will be added as new nodes
    graph.add_node("strategy_analyst", evaluate_detections)

    # Edges
    graph.add_edge(START, "strategy_analyst")
    graph.add_edge("strategy_analyst", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Demo scenario
# ---------------------------------------------------------------------------

def _demo_scenario() -> AnalystState:
    """Build a realistic demo scenario with mixed detection types."""

    # ── Friendly Forces ───────────────────────────────────────────────
    friendlies = [
        FriendlyForce(
            id="ALPHA-1",
            name="Alpha Platoon",
            unit_type="Infantry Platoon",
            location=Location(latitude=33.3100, longitude=44.3660),
        ),
        FriendlyForce(
            id="REAPER-9",
            name="Reaper 9",
            unit_type="MQ-9 Reaper",
            location=Location(latitude=33.3500, longitude=44.4000, altitude_m=5000),
        ),
    ]

    # ── Rules of Engagement ───────────────────────────────────────────
    roe = [
        RuleOfEngagement(
            id="ROE-001",
            description="Engage confirmed hostile targets >500m from friendlies",
            permitted_action=ROEAction.ENGAGE,
            min_confidence=0.8,
            min_distance_friendly_m=500.0,
            applicable_identities=[IdentityClassification.HOSTILE],
        ),
        RuleOfEngagement(
            id="ROE-002",
            description="Observe-only for suspect targets",
            permitted_action=ROEAction.OBSERVE_ONLY,
            min_confidence=0.5,
            min_distance_friendly_m=200.0,
            applicable_identities=[IdentityClassification.SUSPECT],
        ),
    ]

    # ── ISR Detections ────────────────────────────────────────────────
    detections = [
        # 1) Clear hostile TEL — high confidence, far from friendlies
        Detection(
            id="DET-001",
            detection_type=DetectionType.LAUNCHER,
            identity=IdentityClassification.HOSTILE,
            confidence=0.95,
            location=Location(latitude=33.4200, longitude=44.5000),
            sensor=SensorType.EO_IR,
            description="TEL detected via EO/IR — erector raised",
        ),
        # 2) Ambiguous vehicle — low confidence, unknown identity
        Detection(
            id="DET-002",
            detection_type=DetectionType.VEHICLE,
            identity=IdentityClassification.UNKNOWN,
            confidence=0.35,
            location=Location(latitude=33.3800, longitude=44.4200),
            sensor=SensorType.GMTI,
            description="Moving target, single return — identity unresolved",
        ),
        # 3) Hostile vehicle dangerously close to Alpha Platoon
        Detection(
            id="DET-003",
            detection_type=DetectionType.VEHICLE,
            identity=IdentityClassification.HOSTILE,
            confidence=0.90,
            location=Location(latitude=33.3105, longitude=44.3665),
            sensor=SensorType.FMV,
            description="Technical vehicle with mounted weapon — very close to friendlies",
        ),
    ]

    return {
        "detections": detections,
        "friendly_forces": friendlies,
        "roe": roe,
        "strike_board": [],
        "tasking_requests": [],
        "rejected": [],
    }


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the demo scenario through the Strategy Analyst graph."""
    app = build_graph()
    initial_state = _demo_scenario()

    print("=" * 72)
    print("  PROJECT ANTIGRAVITY — Strategy Analyst Agent")
    print("=" * 72)
    print(f"\n  Evaluating {len(initial_state['detections'])} detections ...\n")

    result = app.invoke(initial_state)

    # ── Strike Board ──────────────────────────────────────────────────
    print("-" * 72)
    print(f"  STRIKE BOARD  ({len(result['strike_board'])} targets)")
    print("-" * 72)
    for t in result["strike_board"]:
        print(f"\n  [{t.priority}/10]  Target {t.detection.id}")
        print(f"           Type : {t.detection.detection_type.value}")
        print(f"       Identity : {t.detection.identity.value}")
        print(f"     Confidence : {t.detection.confidence:.0%}")
        print(f"  Nearest Frdly : {t.nearest_friendly_id} ({t.nearest_friendly_distance_m:.0f}m)")
        print(f"      Reasoning : {t.reasoning_trace}")

    # ── Tasking Requests ──────────────────────────────────────────────
    print("\n" + "-" * 72)
    print(f"  TASKING REQUESTS  ({len(result['tasking_requests'])} pending)")
    print("-" * 72)
    for tr in result["tasking_requests"]:
        print(f"\n  Detection {tr.detection_id} → Request {tr.requested_sensor.value}")
        print(f"     Reason : {tr.reason}")

    # ── Rejected ──────────────────────────────────────────────────────
    print("\n" + "-" * 72)
    print(f"  REJECTED  ({len(result['rejected'])} detections)")
    print("-" * 72)
    for r in result["rejected"]:
        print(f"\n  Detection {r['detection_id']}")
        print(f"     Reason : {r['reason']}")

    print("\n" + "=" * 72)
    print("  Evaluation complete.")
    print("=" * 72)


if __name__ == "__main__":
    main()
