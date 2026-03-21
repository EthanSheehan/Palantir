"""Tests for the demo_autopilot() autonomous kill chain loop."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hitl_manager import CourseOfAction, HITLManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uav(uav_id: int, mode: str = "SEARCH", x: float = 44.5, y: float = 26.0, primary_target_id=None):
    return SimpleNamespace(id=uav_id, mode=mode, x=x, y=y, primary_target_id=primary_target_id)


def _make_target(target_id: int, x: float = 44.5, y: float = 26.1, tracked_by_uav_id=None):
    return SimpleNamespace(id=target_id, x=x, y=y, tracked_by_uav_id=tracked_by_uav_id)


def _make_enemy_uav(
    enemy_id: int, mode: str = "RECON", fused_confidence: float = 0.8, x: float = 44.6, y: float = 26.2
):
    return SimpleNamespace(id=enemy_id, mode=mode, fused_confidence=fused_confidence, x=x, y=y)


def _make_coa(coa_id: str = "COA-1", pk: float = 0.85) -> CourseOfAction:
    return CourseOfAction(
        id=coa_id,
        effector_name="JDAM",
        effector_type="PGM",
        time_to_effect_min=2.5,
        pk_estimate=pk,
        risk_score=0.3,
        composite_score=0.9,
        reasoning_trace="Test COA",
        status="PROPOSED",
    )


def _nominate(hitl: HITLManager, target_id: int = 42, target_type: str = "SAM") -> dict:
    """Nominate a target and return the strike board entry dict."""
    hitl.nominate_target(
        {
            "target_id": target_id,
            "target_type": target_type,
            "target_location": (44.5, 26.1),
            "detection_confidence": 0.9,
        },
        {"priority_score": 8.0, "roe_evaluation": "ENGAGE", "reasoning_trace": "test"},
    )
    return hitl.get_strike_board()[-1]


def _build_deps(
    *,
    uavs: dict | None = None,
    targets: dict | None = None,
    enemy_uavs: dict | None = None,
    hitl: HITLManager | None = None,
    coas: list[CourseOfAction] | None = None,
):
    """Build injected dependencies for demo_autopilot with sensible defaults."""
    sim = MagicMock()
    sim.uavs = uavs if uavs is not None else {1: _make_uav(1)}
    sim.targets = targets if targets is not None else {}
    sim.enemy_uavs = enemy_uavs if enemy_uavs is not None else {}

    def find_target(tid):
        return sim.targets.get(tid) if isinstance(sim.targets, dict) else None

    sim._find_target = MagicMock(side_effect=find_target)

    _hitl = hitl if hitl is not None else HITLManager()

    broadcast_fn = AsyncMock()
    clients = {"ws1": {"type": "DASHBOARD"}}
    intel_router = AsyncMock()
    intel_router.emit = AsyncMock()

    tactical_planner = MagicMock()
    test_coas = coas if coas is not None else [_make_coa("COA-1", 0.85), _make_coa("COA-2", 0.65)]
    tactical_planner._generate_coas_heuristic = MagicMock(return_value=test_coas)

    get_effectors = MagicMock(return_value=[{"effector": SimpleNamespace(name="JDAM", effector_type="PGM")}])

    return {
        "sim": sim,
        "hitl": _hitl,
        "broadcast_fn": broadcast_fn,
        "clients": clients,
        "intel_router": intel_router,
        "tactical_planner": tactical_planner,
        "get_effectors": get_effectors,
        "approval_delay": 0.0,
        "follow_delay": 0.0,
        "paint_delay": 0.0,
    }


async def _noop_coro(_seconds=0):
    """Awaitable that returns immediately — replaces asyncio.sleep."""
    return


async def _run_autopilot_once(deps: dict):
    """Run demo_autopilot and cancel it after one full loop iteration.

    Strategy: patch asyncio.sleep with an instant coroutine. Track 2.0s sleep
    calls (top-of-loop marker) — cancel on the third occurrence (startup,
    first loop entry, second loop entry = first iteration done).
    """
    from autopilot import demo_autopilot

    loop_top_count = 0

    async def fake_sleep(seconds):
        nonlocal loop_top_count
        if seconds == 2.0:
            loop_top_count += 1
            if loop_top_count >= 3:
                raise asyncio.CancelledError()

    with patch("autopilot.asyncio.sleep", side_effect=fake_sleep):
        try:
            await demo_autopilot(**deps)
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_autopilot_approves_pending_after_delay():
    """Autopilot auto-approves PENDING nominations."""
    deps = _build_deps()
    hitl = deps["hitl"]
    entry = _nominate(hitl, target_id=42)

    # Target must exist for UAV dispatch
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    await _run_autopilot_once(deps)

    board = hitl.get_strike_board()
    approved = [e for e in board if e["status"] == "APPROVED"]
    assert len(approved) >= 1, f"Expected at least one APPROVED entry, got statuses: {[e['status'] for e in board]}"


@pytest.mark.asyncio
async def test_demo_autopilot_dispatches_nearest_uav():
    """Autopilot dispatches nearest SEARCH-mode UAV to follow target."""
    uav_near = _make_uav(1, mode="SEARCH", x=44.5, y=26.05)
    uav_far = _make_uav(2, mode="SEARCH", x=45.0, y=27.0)
    deps = _build_deps(uavs={1: uav_near, 2: uav_far})
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    _nominate(hitl, target_id=42)

    await _run_autopilot_once(deps)

    deps["sim"].command_follow.assert_called()
    # The nearest UAV (id=1) should be dispatched
    first_call_uav_id = deps["sim"].command_follow.call_args_list[0][0][0]
    assert first_call_uav_id == 1, f"Expected UAV 1 (nearest), got UAV {first_call_uav_id}"


@pytest.mark.asyncio
async def test_demo_autopilot_escalates_follow_to_paint():
    """After follow delay, autopilot escalates to PAINT mode."""
    deps = _build_deps()
    # Target reports being tracked by UAV 1 so escalation proceeds
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    _nominate(hitl, target_id=42)

    await _run_autopilot_once(deps)

    deps["sim"].command_paint.assert_called_once()
    call_args = deps["sim"].command_paint.call_args[0]
    assert call_args[1] == 42, f"Expected paint on target 42, got {call_args[1]}"


@pytest.mark.asyncio
async def test_demo_autopilot_generates_coas_after_paint():
    """COAs are generated after painting a target."""
    deps = _build_deps()
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    _nominate(hitl, target_id=42)

    await _run_autopilot_once(deps)

    deps["tactical_planner"]._generate_coas_heuristic.assert_called_once()
    # COAs should be proposed on the HITL manager
    coas = hitl.get_coas_for_entry(hitl.get_strike_board()[0]["id"])
    assert len(coas) >= 1, "Expected COAs to be proposed"


@pytest.mark.asyncio
async def test_demo_autopilot_authorizes_best_coa():
    """Best COA (first after sort) gets auto-authorized."""
    deps = _build_deps()
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    entry = _nominate(hitl, target_id=42)

    await _run_autopilot_once(deps)

    entry_id = hitl.get_strike_board()[0]["id"]
    coas = hitl.get_coas_for_entry(entry_id)
    authorized = [c for c in coas if c["status"] == "AUTHORIZED"]
    assert len(authorized) == 1, f"Expected 1 AUTHORIZED COA, got {len(authorized)}"
    assert authorized[0]["id"] == "COA-1"


@pytest.mark.asyncio
async def test_demo_autopilot_auto_intercepts_enemy_above_threshold():
    """Enemy UAVs with fused_confidence > 0.7 trigger auto-intercept."""
    enemy = _make_enemy_uav(1001, mode="RECON", fused_confidence=0.85)
    uav = _make_uav(1, mode="SEARCH", primary_target_id=None)
    deps = _build_deps(uavs={1: uav}, enemy_uavs={1001: enemy})

    await _run_autopilot_once(deps)

    deps["sim"].command_intercept_enemy.assert_called_once_with(1, 1001)


@pytest.mark.asyncio
async def test_demo_autopilot_skips_already_inflight():
    """Autopilot doesn't double-dispatch for the same strike board entry."""
    deps = _build_deps()
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    _nominate(hitl, target_id=42)

    # Run twice — the entry should only be processed once since after first
    # run it's no longer PENDING.
    await _run_autopilot_once(deps)
    approve_count_before = deps["sim"].command_follow.call_count

    # Re-run — no new PENDING entries, so no new dispatches
    await _run_autopilot_once(deps)
    approve_count_after = deps["sim"].command_follow.call_count

    assert approve_count_after == approve_count_before, "Should not double-dispatch for same entry"


@pytest.mark.asyncio
async def test_full_kill_chain_auto_mode_completes():
    """Integration test: full F2T2EA cycle from nomination to COA authorization."""
    deps = _build_deps()
    deps["sim"].targets = {42: _make_target(42, tracked_by_uav_id=1)}

    hitl = deps["hitl"]
    _nominate(hitl, target_id=42)

    await _run_autopilot_once(deps)

    board = hitl.get_strike_board()
    entry = board[0]
    entry_id = entry["id"]

    # Gate 1: nomination approved
    assert entry["status"] == "APPROVED", f"Expected APPROVED, got {entry['status']}"

    # UAV dispatched to follow
    deps["sim"].command_follow.assert_called_once()

    # Escalated to paint
    deps["sim"].command_paint.assert_called_once()

    # COAs generated
    deps["tactical_planner"]._generate_coas_heuristic.assert_called_once()

    # Gate 2: best COA authorized
    coas = hitl.get_coas_for_entry(entry_id)
    authorized = [c for c in coas if c["status"] == "AUTHORIZED"]
    assert len(authorized) == 1

    # Broadcast messages sent for each phase
    assert deps["broadcast_fn"].call_count >= 4, "Expected multiple broadcast messages through the kill chain"


@pytest.mark.asyncio
async def test_supervised_requires_approval():
    """In supervised mode (non-demo), PENDING entries are NOT auto-approved.

    The demo_autopilot function itself always auto-approves — supervised mode
    is enforced by not starting the autopilot. This test verifies that a PENDING
    entry stays PENDING when no autopilot processes it.
    """
    hitl = HITLManager()
    _nominate(hitl, target_id=42)

    # Without running autopilot, the entry stays PENDING
    board = hitl.get_strike_board()
    assert board[0]["status"] == "PENDING"

    # Manual approval changes state
    hitl.approve_nomination(board[0]["id"], "Human operator approved")
    board = hitl.get_strike_board()
    assert board[0]["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_autonomous_fleet_with_manual_override():
    """Manual override: if entry is rejected before autopilot processes it,
    autopilot skips it (doesn't override human decision)."""
    deps = _build_deps()
    hitl = deps["hitl"]
    entry = _nominate(hitl, target_id=42)

    # Human rejects the nomination before autopilot runs
    hitl.reject_nomination(entry["id"], "Operator override — do not engage")

    deps["sim"].targets = {42: _make_target(42)}

    await _run_autopilot_once(deps)

    # Autopilot should NOT have dispatched any UAV — entry was already REJECTED
    deps["sim"].command_follow.assert_not_called()
    deps["sim"].command_paint.assert_not_called()

    # Entry remains REJECTED
    board = hitl.get_strike_board()
    assert board[0]["status"] == "REJECTED"
