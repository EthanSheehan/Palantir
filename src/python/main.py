"""
main.py
=======
LangGraph application -- wires the Strategy Analyst into a runnable graph.

Usage (from project root):
    source venv/bin/activate
    python -m src.python.main
"""

from __future__ import annotations

import structlog
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

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Build and compile the Strategy Analyst LangGraph."""
    graph = StateGraph(AnalystState)

    # Single node for now -- additional agents will be added as new nodes
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

    # -- Friendly Forces --
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

    # -- Rules of Engagement --
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

    # -- ISR Detections --
    detections = [
        # 1) Clear hostile TEL -- high confidence, far from friendlies
        Detection(
            id="DET-001",
            detection_type=DetectionType.LAUNCHER,
            identity=IdentityClassification.HOSTILE,
            confidence=0.95,
            location=Location(latitude=33.4200, longitude=44.5000),
            sensor=SensorType.EO_IR,
            description="TEL detected via EO/IR -- erector raised",
        ),
        # 2) Ambiguous vehicle -- low confidence, unknown identity
        Detection(
            id="DET-002",
            detection_type=DetectionType.VEHICLE,
            identity=IdentityClassification.UNKNOWN,
            confidence=0.35,
            location=Location(latitude=33.3800, longitude=44.4200),
            sensor=SensorType.GMTI,
            description="Moving target, single return -- identity unresolved",
        ),
        # 3) Hostile vehicle dangerously close to Alpha Platoon
        Detection(
            id="DET-003",
            detection_type=DetectionType.VEHICLE,
            identity=IdentityClassification.HOSTILE,
            confidence=0.90,
            location=Location(latitude=33.3105, longitude=44.3665),
            sensor=SensorType.FMV,
            description="Technical vehicle with mounted weapon -- very close to friendlies",
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

    logger.info("evaluation_started", agent="Strategy Analyst", detections=len(initial_state["detections"]))

    result = app.invoke(initial_state)

    # -- Strike Board --
    logger.info("strike_board", count=len(result["strike_board"]))
    for t in result["strike_board"]:
        logger.info(
            "strike_target",
            priority=t.priority,
            detection_id=t.detection.id,
            detection_type=t.detection.detection_type.value,
            identity=t.detection.identity.value,
            confidence=f"{t.detection.confidence:.0%}",
            nearest_friendly=t.nearest_friendly_id,
            nearest_distance_m=f"{t.nearest_friendly_distance_m:.0f}",
            reasoning=t.reasoning_trace,
        )

    # -- Tasking Requests --
    logger.info("tasking_requests", count=len(result["tasking_requests"]))
    for tr in result["tasking_requests"]:
        logger.info(
            "tasking_request",
            detection_id=tr.detection_id,
            requested_sensor=tr.requested_sensor.value,
            reason=tr.reason,
        )

    # -- Rejected --
    logger.info("rejected", count=len(result["rejected"]))
    for r in result["rejected"]:
        logger.info("rejected_detection", detection_id=r["detection_id"], reason=r["reason"])

    logger.info("evaluation_complete")


if __name__ == "__main__":
    main()
