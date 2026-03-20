"""Tests for IntelFeedRouter, subscription filtering, and log rotation."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from intel_feed import IntelFeedRouter, _client_subscribed
from event_logger import rotate_logs


# ---------------------------------------------------------------------------
# IntelFeedRouter tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intel_router_emit_calls_broadcast():
    """emit() calls broadcast_fn with FEED_EVENT JSON containing feed and data."""
    broadcast_fn = AsyncMock()
    router = IntelFeedRouter(broadcast_fn=broadcast_fn)
    await router.emit("INTEL_FEED", {"event": "target_detected", "target_id": 1})

    assert broadcast_fn.called
    call_kwargs = broadcast_fn.call_args
    # First positional arg is the message
    msg_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("message", "")
    import json
    msg = json.loads(msg_arg)
    assert msg["type"] == "FEED_EVENT"
    assert msg["feed"] == "INTEL_FEED"
    assert msg["data"]["event"] == "target_detected"


@pytest.mark.asyncio
async def test_intel_router_emit_calls_log_event():
    """emit() calls log_event with feed_type and event data."""
    broadcast_fn = AsyncMock()
    router = IntelFeedRouter(broadcast_fn=broadcast_fn)

    with patch("intel_feed.log_event") as mock_log:
        await router.emit("COMMAND_FEED", {"action": "follow_target"})
        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        assert args[0] == "COMMAND_FEED"
        assert args[1]["action"] == "follow_target"


@pytest.mark.asyncio
async def test_intel_router_history_capped():
    """After emitting 250 events, get_history() returns only the last 200."""
    broadcast_fn = AsyncMock()
    router = IntelFeedRouter(broadcast_fn=broadcast_fn, max_history=200)
    for i in range(250):
        await router.emit("INTEL_FEED", {"seq": i})
    history = router.get_history()
    assert len(history) == 200
    # Should have the last 200 (seq 50..249)
    assert history[0]["seq"] == 50
    assert history[-1]["seq"] == 249


@pytest.mark.asyncio
async def test_intel_router_get_history_returns_list():
    """get_history() returns list of enriched dicts with 'feed' and 'timestamp' keys."""
    broadcast_fn = AsyncMock()
    router = IntelFeedRouter(broadcast_fn=broadcast_fn)
    await router.emit("INTEL_FEED", {"event": "state_change"})
    history = router.get_history()
    assert isinstance(history, list)
    assert len(history) == 1
    assert "feed" in history[0]
    assert "timestamp" in history[0]
    assert history[0]["feed"] == "INTEL_FEED"


# ---------------------------------------------------------------------------
# _client_subscribed tests
# ---------------------------------------------------------------------------

def test_subscription_filtering_subscribed():
    """_client_subscribed returns True when feed is in client subscriptions."""
    info = {"subscriptions": {"INTEL_FEED"}}
    assert _client_subscribed(info, "INTEL_FEED") is True


def test_subscription_filtering_not_subscribed():
    """_client_subscribed returns False when feed is NOT in client subscriptions."""
    info = {"subscriptions": {"INTEL_FEED"}}
    assert _client_subscribed(info, "COMMAND_FEED") is False


def test_subscription_filtering_legacy_client():
    """_client_subscribed returns True for legacy clients (no subscriptions key)."""
    info = {"type": "DASHBOARD"}
    assert _client_subscribed(info, "INTEL_FEED") is True


# ---------------------------------------------------------------------------
# rotate_logs tests
# ---------------------------------------------------------------------------

def test_log_rotation_deletes_old(tmp_path, monkeypatch):
    """rotate_logs(max_days=3) with 5 log files deletes the 2 oldest."""
    import event_logger
    monkeypatch.setattr(event_logger, "LOG_DIR", tmp_path)

    # Create 5 fake log files with date-sorted names
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    for d in dates:
        (tmp_path / f"events-{d}.jsonl").write_text("")

    rotate_logs(max_days=3)

    remaining = sorted(tmp_path.glob("events-*.jsonl"))
    assert len(remaining) == 3
    names = [f.name for f in remaining]
    assert "events-2026-01-03.jsonl" in names
    assert "events-2026-01-04.jsonl" in names
    assert "events-2026-01-05.jsonl" in names
    assert "events-2026-01-01.jsonl" not in names
    assert "events-2026-01-02.jsonl" not in names


def test_log_rotation_keeps_recent(tmp_path, monkeypatch):
    """rotate_logs(max_days=7) with 3 log files deletes nothing."""
    import event_logger
    monkeypatch.setattr(event_logger, "LOG_DIR", tmp_path)

    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    for d in dates:
        (tmp_path / f"events-{d}.jsonl").write_text("")

    rotate_logs(max_days=7)

    remaining = list(tmp_path.glob("events-*.jsonl"))
    assert len(remaining) == 3


# ---------------------------------------------------------------------------
# Integration tests — api_main.py wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_command_feed_coverage():
    """intel_router.emit is called with COMMAND_FEED when follow_target action received."""
    import api_main

    mock_emit = AsyncMock()
    original_emit = api_main.intel_router.emit
    api_main.intel_router.emit = mock_emit

    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()
    api_main.clients[mock_ws] = {"type": "DASHBOARD"}

    # Mock sim.command_follow to avoid real sim side effects
    with patch.object(api_main.sim, "command_follow"):
        await api_main.handle_payload(
            {"action": "follow_target", "drone_id": 0, "target_id": 1},
            mock_ws,
            "",
        )

    mock_emit.assert_called_once()
    args = mock_emit.call_args[0]
    assert args[0] == "COMMAND_FEED"
    assert args[1]["action"] == "follow_target"

    # Restore
    api_main.intel_router.emit = original_emit
    api_main.clients.pop(mock_ws, None)


@pytest.mark.asyncio
async def test_subscribe_action_sets_subscriptions():
    """subscribe action stores feeds set on the client info dict."""
    import api_main

    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()
    api_main.clients[mock_ws] = {"type": "DASHBOARD"}

    await api_main.handle_payload(
        {"action": "subscribe", "feeds": ["INTEL_FEED", "COMMAND_FEED"]},
        mock_ws,
        "",
    )

    client_info = api_main.clients[mock_ws]
    assert "subscriptions" in client_info
    assert "INTEL_FEED" in client_info["subscriptions"]
    assert "COMMAND_FEED" in client_info["subscriptions"]

    # Cleanup
    api_main.clients.pop(mock_ws, None)


@pytest.mark.asyncio
async def test_state_transition_emits_intel_feed():
    """When target state changes between ticks, intel_router.emit is called with INTEL_FEED."""
    import api_main

    mock_emit = AsyncMock()
    original_emit = api_main.intel_router.emit
    api_main.intel_router.emit = mock_emit

    # Seed previous state
    api_main._prev_target_states[99] = "DETECTED"

    # Simulate a state dict with a transition
    fake_state = {
        "targets": [{"id": 99, "state": "CLASSIFIED", "type": "SAM"}],
        "drones": [],
        "grid_zones": [],
    }

    with patch.object(api_main.sim, "tick"), \
         patch.object(api_main.sim, "get_state", return_value=fake_state), \
         patch.object(api_main.hitl, "get_strike_board", return_value=[]), \
         patch.object(api_main.assistant, "update", return_value=[]):
        # Run one iteration of the simulation loop logic
        api_main.sim.tick()
        state = api_main.sim.get_state()
        for t in state.get("targets", []):
            tid = t["id"]
            new_state = t["state"]
            prev = api_main._prev_target_states.get(tid)
            if prev and prev != new_state and new_state != "UNDETECTED":
                await api_main.intel_router.emit("INTEL_FEED", {
                    "event": new_state,
                    "target_id": tid,
                    "target_type": t["type"],
                    "from": prev,
                    "to": new_state,
                    "summary": f"Target {tid} ({t['type']}): {prev} -> {new_state}",
                })
            api_main._prev_target_states[tid] = new_state

    mock_emit.assert_called_once()
    args = mock_emit.call_args[0]
    assert args[0] == "INTEL_FEED"
    assert args[1]["target_id"] == 99
    assert args[1]["from"] == "DETECTED"
    assert args[1]["to"] == "CLASSIFIED"

    # Restore
    api_main.intel_router.emit = original_emit
    api_main._prev_target_states.pop(99, None)
