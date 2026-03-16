"""
core/state.py
=============
LangGraph state definition for the Strategy Analyst workflow.

The state flows through the graph and is updated by each node.
Reducers (operator.add) ensure list fields accumulate rather than overwrite.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from core.ontology import (
    ActionableTarget,
    Detection,
    FriendlyForce,
    RuleOfEngagement,
    TaskingRequest,
)


class AnalystState(TypedDict):
    """
    Shared state for the Strategy Analyst LangGraph workflow.

    Fields
    ------
    detections : list[Detection]
        ISR Observer detections awaiting evaluation.
    friendly_forces : list[FriendlyForce]
        Current positions of friendly units.
    roe : list[RuleOfEngagement]
        Active Rules of Engagement.
    strike_board : Annotated[list[ActionableTarget], add]
        Accumulator — targets deemed actionable (uses `add` reducer).
    tasking_requests : Annotated[list[TaskingRequest], add]
        Accumulator — requests for secondary sensor confirmation.
    rejected : Annotated[list[dict], add]
        Accumulator — detections rejected with reason.
    """

    detections: list[Detection]
    friendly_forces: list[FriendlyForce]
    roe: list[RuleOfEngagement]
    strike_board: Annotated[list[ActionableTarget], add]
    tasking_requests: Annotated[list[TaskingRequest], add]
    rejected: Annotated[list[dict], add]
