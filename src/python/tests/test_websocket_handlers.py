"""Tests for websocket_handlers.py — dispatch table, validation, and all action handlers."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from websocket_handlers import (
    _ACTION_SCHEMAS,
    _DISPATCH_TABLE,
    _TYPE_FORWARD,
    MAX_SITREP_QUERY_LENGTH,
    HandlerContext,
    _build_sitrep_payload,
    _send_error,
    _validate_payload,
    handle_payload,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ctx(**overrides) -> HandlerContext:
    """Build a HandlerContext with sensible mocks for all dependencies."""
    defaults = {
        "sim": MagicMock(),
        "hitl": MagicMock(),
        "intel_router": AsyncMock(),
        "broadcast": AsyncMock(),
        "clients": {},
        "ai_tasking_manager": MagicMock(),
        "raw_data": "{}",
    }
    defaults.update(overrides)
    return HandlerContext(**defaults)


def _make_ws() -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def ws():
    return _make_ws()


@pytest.fixture
def ctx():
    return _make_ctx()


# ---------------------------------------------------------------------------
# _validate_payload
# ---------------------------------------------------------------------------


class TestValidatePayload:
    def test_valid_payload(self):
        schema = {"drone_id": "int", "target_id": "int"}
        assert _validate_payload({"drone_id": 1, "target_id": 2}, schema) is None

    def test_missing_field(self):
        schema = {"drone_id": "int", "target_id": "int"}
        result = _validate_payload({"drone_id": 1}, schema)
        assert result is not None
        assert "target_id" in result

    def test_none_field(self):
        schema = {"drone_id": "int"}
        result = _validate_payload({"drone_id": None}, schema)
        assert result is not None

    def test_wrong_type_string_for_int(self):
        schema = {"drone_id": "int"}
        result = _validate_payload({"drone_id": "abc"}, schema)
        assert result is not None
        assert "int" in result

    def test_float_as_int_accepted(self):
        schema = {"drone_id": "int"}
        assert _validate_payload({"drone_id": 1.0}, schema) is None

    def test_float_with_fraction_rejected_as_int(self):
        schema = {"drone_id": "int"}
        result = _validate_payload({"drone_id": 1.5}, schema)
        assert result is not None

    def test_str_type_valid(self):
        schema = {"entry_id": "str"}
        assert _validate_payload({"entry_id": "abc-123"}, schema) is None

    def test_str_type_invalid(self):
        schema = {"entry_id": "str"}
        result = _validate_payload({"entry_id": 42}, schema)
        assert result is not None

    def test_float_type_accepts_int(self):
        schema = {"lon": "float"}
        assert _validate_payload({"lon": 42}, schema) is None

    def test_float_type_accepts_float(self):
        schema = {"lon": "float"}
        assert _validate_payload({"lon": 42.5}, schema) is None


# ---------------------------------------------------------------------------
# _send_error
# ---------------------------------------------------------------------------


class TestSendError:
    @pytest.mark.asyncio
    async def test_sends_json_error(self):
        ws = _make_ws()
        await _send_error(ws, "bad input", "test_action")
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"
        assert sent["message"] == "bad input"
        assert sent["action"] == "test_action"

    @pytest.mark.asyncio
    async def test_no_action_field_when_none(self):
        ws = _make_ws()
        await _send_error(ws, "err")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert "action" not in sent

    @pytest.mark.asyncio
    async def test_swallows_disconnect(self):
        from fastapi import WebSocketDisconnect

        ws = _make_ws()
        ws.send_text.side_effect = WebSocketDisconnect()
        await _send_error(ws, "err")  # should not raise


# ---------------------------------------------------------------------------
# handle_payload — dispatch and validation
# ---------------------------------------------------------------------------


class TestHandlePayloadDispatch:
    @pytest.mark.asyncio
    async def test_unknown_action_no_crash(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "nonexistent_action"}, ws, "{}", ctx)
        # No error sent, no crash — the payload just falls through

    @pytest.mark.asyncio
    async def test_validation_rejects_missing_field(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "spike"}, ws, "{}", ctx)
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"
        assert "lon" in sent["message"] or "lat" in sent["message"]

    @pytest.mark.asyncio
    async def test_validation_rejects_wrong_type(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "spike", "lon": "abc", "lat": 1.0}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"

    @pytest.mark.asyncio
    async def test_type_forward_drone_feed(self):
        ws = _make_ws()
        ctx = _make_ctx(raw_data='{"type":"DRONE_FEED"}')
        await handle_payload({"type": "DRONE_FEED"}, ws, '{"type":"DRONE_FEED"}', ctx)
        ctx.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_type_forward_track_update(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"type": "TRACK_UPDATE"}, ws, "{}", ctx)
        ctx.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sitrep_query_by_type(self):
        """SITREP_QUERY dispatched via p_type fallback."""
        ws = _make_ws()
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(sim=sim, hitl=hitl)
        await handle_payload({"type": "SITREP_QUERY", "query": "status?"}, ws, "{}", ctx)
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "SITREP_RESPONSE"


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------


class TestSpikeHandler:
    @pytest.mark.asyncio
    async def test_spike_calls_sim(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "spike", "lon": 44.5, "lat": 33.5}, ws, "{}", ctx)
        ctx.sim.trigger_demand_spike.assert_called_once_with(44.5, 33.5)


class TestMoveDrone:
    @pytest.mark.asyncio
    async def test_valid_move(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload(
            {"action": "move_drone", "drone_id": 1, "target_lon": 44.0, "target_lat": 33.0}, ws, "{}", ctx
        )
        ctx.sim.command_move.assert_called_once_with(1, 44.0, 33.0)

    @pytest.mark.asyncio
    async def test_nan_rejected(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload(
            {"action": "move_drone", "drone_id": 1, "target_lon": float("nan"), "target_lat": 33.0},
            ws,
            "{}",
            ctx,
        )
        ctx.sim.command_move.assert_not_called()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"

    @pytest.mark.asyncio
    async def test_inf_rejected(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload(
            {"action": "move_drone", "drone_id": 1, "target_lon": float("inf"), "target_lat": 33.0},
            ws,
            "{}",
            ctx,
        )
        ctx.sim.command_move.assert_not_called()

    @pytest.mark.asyncio
    async def test_out_of_range_rejected(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload(
            {"action": "move_drone", "drone_id": 1, "target_lon": 200.0, "target_lat": 33.0},
            ws,
            "{}",
            ctx,
        )
        ctx.sim.command_move.assert_not_called()


class TestFollowTarget:
    @pytest.mark.asyncio
    async def test_calls_sim_and_emits(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "follow_target", "drone_id": 1, "target_id": 5}, ws, "{}", ctx)
        ctx.sim.command_follow.assert_called_once_with(1, 5)
        ctx.intel_router.emit.assert_awaited_once()


class TestPaintTarget:
    @pytest.mark.asyncio
    async def test_calls_sim_and_emits(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "paint_target", "drone_id": 1, "target_id": 5}, ws, "{}", ctx)
        ctx.sim.command_paint.assert_called_once_with(1, 5)
        ctx.intel_router.emit.assert_awaited_once()


class TestInterceptTarget:
    @pytest.mark.asyncio
    async def test_calls_sim_and_emits(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "intercept_target", "drone_id": 1, "target_id": 5}, ws, "{}", ctx)
        ctx.sim.command_intercept.assert_called_once_with(1, 5)
        ctx.intel_router.emit.assert_awaited_once()


class TestInterceptEnemy:
    @pytest.mark.asyncio
    async def test_calls_sim_and_emits(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "intercept_enemy", "uav_id": 1, "enemy_uav_id": 3}, ws, "{}", ctx)
        ctx.sim.command_intercept_enemy.assert_called_once_with(1, 3)
        ctx.intel_router.emit.assert_awaited_once()


class TestCancelTrack:
    @pytest.mark.asyncio
    async def test_cancel_track(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "cancel_track", "drone_id": 2}, ws, "{}", ctx)
        ctx.sim.cancel_track.assert_called_once_with(2)
        ctx.intel_router.emit.assert_awaited_once()


class TestScanArea:
    @pytest.mark.asyncio
    async def test_scan_area(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "scan_area", "drone_id": 3}, ws, "{}", ctx)
        ctx.sim.cancel_track.assert_called_once_with(3)


class TestApproveNomination:
    @pytest.mark.asyncio
    async def test_approve_success(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(hitl=hitl)
        await handle_payload(
            {"action": "approve_nomination", "entry_id": "E-1", "rationale": "threat confirmed"}, ws, "{}", ctx
        )
        hitl.approve_nomination.assert_called_once_with("E-1", "threat confirmed")
        ctx.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_value_error_handled(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.approve_nomination.side_effect = ValueError("not found")
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "approve_nomination", "entry_id": "E-bad"}, ws, "{}", ctx)
        # No crash, no broadcast
        ctx.broadcast.assert_not_awaited()


class TestRejectNomination:
    @pytest.mark.asyncio
    async def test_reject_success(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "reject_nomination", "entry_id": "E-1"}, ws, "{}", ctx)
        hitl.reject_nomination.assert_called_once()
        ctx.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_value_error_handled(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.reject_nomination.side_effect = ValueError("not found")
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "reject_nomination", "entry_id": "E-bad"}, ws, "{}", ctx)
        ctx.broadcast.assert_not_awaited()


class TestRetaskNomination:
    @pytest.mark.asyncio
    async def test_retask_success(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "retask_nomination", "entry_id": "E-1"}, ws, "{}", ctx)
        hitl.retask_nomination.assert_called_once()
        ctx.broadcast.assert_awaited_once()


class TestAuthorizeCoa:
    @pytest.mark.asyncio
    async def test_authorize_success(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.get_coas_for_entry.return_value = []
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "authorize_coa", "entry_id": "E-1", "coa_id": "COA-1"}, ws, "{}", ctx)
        hitl.authorize_coa.assert_called_once_with("E-1", "COA-1", "")
        ctx.intel_router.emit.assert_awaited_once()
        ctx.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authorize_value_error(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.authorize_coa.side_effect = ValueError("not found")
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "authorize_coa", "entry_id": "E-1", "coa_id": "COA-1"}, ws, "{}", ctx)
        ctx.broadcast.assert_not_awaited()


class TestRejectCoa:
    @pytest.mark.asyncio
    async def test_reject_coa_success(self):
        ws = _make_ws()
        hitl = MagicMock()
        hitl.get_coas_for_entry.return_value = []
        ctx = _make_ctx(hitl=hitl)
        await handle_payload({"action": "reject_coa", "entry_id": "E-1"}, ws, "{}", ctx)
        hitl.reject_coa.assert_called_once()
        ctx.broadcast.assert_awaited_once()


class TestReset:
    @pytest.mark.asyncio
    async def test_reset(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "reset"}, ws, "{}", ctx)
        ctx.sim.reset_queues.assert_called_once()


class TestSetAutonomyLevel:
    @pytest.mark.asyncio
    async def test_valid_level(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "set_autonomy_level", "level": "SUPERVISED"}, ws, "{}", ctx)
        assert ctx.sim.autonomy_level == "SUPERVISED"
        ctx.intel_router.emit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_level(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "set_autonomy_level", "level": "INVALID"}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"


class TestSetDroneAutonomy:
    @pytest.mark.asyncio
    async def test_uav_not_found(self):
        ws = _make_ws()
        ctx = _make_ctx()
        ctx.sim._find_uav.return_value = None
        await handle_payload({"action": "set_drone_autonomy", "drone_id": 99}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"
        assert "99" in sent["message"]

    @pytest.mark.asyncio
    async def test_valid_override(self):
        ws = _make_ws()
        uav = MagicMock()
        ctx = _make_ctx()
        ctx.sim._find_uav.return_value = uav
        await handle_payload({"action": "set_drone_autonomy", "drone_id": 1, "level": "AUTONOMOUS"}, ws, "{}", ctx)
        assert uav.autonomy_override == "AUTONOMOUS"

    @pytest.mark.asyncio
    async def test_clear_override(self):
        ws = _make_ws()
        uav = MagicMock()
        ctx = _make_ctx()
        ctx.sim._find_uav.return_value = uav
        await handle_payload({"action": "set_drone_autonomy", "drone_id": 1}, ws, "{}", ctx)
        assert uav.autonomy_override is None

    @pytest.mark.asyncio
    async def test_invalid_override_level(self):
        ws = _make_ws()
        uav = MagicMock()
        ctx = _make_ctx()
        ctx.sim._find_uav.return_value = uav
        await handle_payload({"action": "set_drone_autonomy", "drone_id": 1, "level": "BOGUS"}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"


class TestApproveRejectTransition:
    @pytest.mark.asyncio
    async def test_approve_transition(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "approve_transition", "drone_id": 1}, ws, "{}", ctx)
        ctx.sim.approve_transition.assert_called_once_with(1)
        ctx.intel_router.emit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_transition(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "reject_transition", "drone_id": 1}, ws, "{}", ctx)
        ctx.sim.reject_transition.assert_called_once_with(1)
        ctx.intel_router.emit.assert_awaited_once()


class TestRequestReleaseSwarm:
    @pytest.mark.asyncio
    async def test_request_swarm(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "request_swarm", "target_id": 5}, ws, "{}", ctx)
        ctx.sim.request_swarm.assert_called_once_with(5)
        ctx.intel_router.emit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_swarm(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "release_swarm", "target_id": 5}, ws, "{}", ctx)
        ctx.sim.release_swarm.assert_called_once_with(5)
        ctx.intel_router.emit.assert_awaited_once()


class TestSetCoverageMode:
    @pytest.mark.asyncio
    async def test_valid_mode(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "set_coverage_mode", "mode": "balanced"}, ws, "{}", ctx)
        ctx.sim.set_coverage_mode.assert_called_once_with("balanced")

    @pytest.mark.asyncio
    async def test_valid_threat_adaptive(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "set_coverage_mode", "mode": "threat_adaptive"}, ws, "{}", ctx)
        ctx.sim.set_coverage_mode.assert_called_once_with("threat_adaptive")

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "set_coverage_mode", "mode": "BOGUS"}, ws, "{}", ctx)
        ctx.sim.set_coverage_mode.assert_not_called()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_valid_subscribe(self):
        ws = _make_ws()
        clients = {ws: {}}
        intel = AsyncMock()
        intel.get_history = MagicMock(return_value=[])
        ctx = _make_ctx(clients=clients, intel_router=intel)
        await handle_payload({"action": "subscribe", "feeds": ["INTEL_FEED"]}, ws, "{}", ctx)
        assert "INTEL_FEED" in clients[ws]["subscriptions"]

    @pytest.mark.asyncio
    async def test_invalid_feed_type(self):
        ws = _make_ws()
        ctx = _make_ctx(clients={ws: {}})
        await handle_payload({"action": "subscribe", "feeds": ["BOGUS_FEED"]}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"
        assert "BOGUS_FEED" in sent["message"]

    @pytest.mark.asyncio
    async def test_feeds_not_list(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "subscribe", "feeds": "INTEL_FEED"}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"

    @pytest.mark.asyncio
    async def test_subscribe_sends_history(self):
        ws = _make_ws()
        clients = {ws: {}}
        intel = AsyncMock()
        intel.get_history = MagicMock(return_value=[{"event": "test"}])
        ctx = _make_ctx(clients=clients, intel_router=intel)
        await handle_payload({"action": "subscribe", "feeds": ["INTEL_FEED"]}, ws, "{}", ctx)
        # Should have sent FEED_HISTORY
        assert ws.send_text.await_count >= 1
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "FEED_HISTORY"


class TestSubscribeSensorFeed:
    @pytest.mark.asyncio
    async def test_sensor_feed(self):
        ws = _make_ws()
        clients = {ws: {}}
        ctx = _make_ctx(clients=clients)
        await handle_payload({"action": "subscribe_sensor_feed", "uav_ids": [1, 2, 3]}, ws, "{}", ctx)
        assert "SENSOR_FEED" in clients[ws]["subscriptions"]
        assert clients[ws]["sensor_feed_uav_ids"] == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_sensor_feed_filters_non_int(self):
        ws = _make_ws()
        clients = {ws: {}}
        ctx = _make_ctx(clients=clients)
        await handle_payload({"action": "subscribe_sensor_feed", "uav_ids": [1, "bad", 3]}, ws, "{}", ctx)
        assert clients[ws]["sensor_feed_uav_ids"] == {1, 3}


class TestSitrepQuery:
    @pytest.mark.asyncio
    async def test_sitrep_basic(self):
        ws = _make_ws()
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(sim=sim, hitl=hitl)
        await handle_payload({"action": "sitrep_query", "query": "status"}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "SITREP_RESPONSE"
        assert "query" in sent

    @pytest.mark.asyncio
    async def test_sitrep_query_too_long(self):
        ws = _make_ws()
        ctx = _make_ctx()
        long_query = "x" * (MAX_SITREP_QUERY_LENGTH + 1)
        await handle_payload({"action": "sitrep_query", "query": long_query}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"

    @pytest.mark.asyncio
    async def test_sitrep_non_string_query(self):
        ws = _make_ws()
        ctx = _make_ctx()
        await handle_payload({"action": "sitrep_query", "query": 12345}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ERROR"

    @pytest.mark.asyncio
    async def test_generate_sitrep_alias(self):
        """generate_sitrep should route to the same handler as sitrep_query."""
        ws = _make_ws()
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        ctx = _make_ctx(sim=sim, hitl=hitl)
        await handle_payload({"action": "generate_sitrep"}, ws, "{}", ctx)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "SITREP_RESPONSE"


class TestSetScenario:
    def test_dispatch_entry_exists(self):
        assert "SET_SCENARIO" in _DISPATCH_TABLE


# ---------------------------------------------------------------------------
# _build_sitrep_payload
# ---------------------------------------------------------------------------


class TestBuildSitrepPayload:
    def test_no_targets(self):
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        result = _build_sitrep_payload(sim, hitl)
        assert "clear" in result["sitrep_narrative"].lower()
        assert result["confidence"] == 0.9
        assert "Continue ISR coverage." in result["recommended_actions"]

    def test_with_targets(self):
        sim = MagicMock()
        sim.get_state.return_value = {
            "targets": [
                {"id": 1, "type": "SAM", "lat": 44.0, "lon": 26.0, "state": "DETECTED"},
                {"id": 2, "type": "TEL", "lat": 44.1, "lon": 26.1, "state": "CLASSIFIED"},
            ]
        }
        hitl = MagicMock()
        hitl.get_strike_board.return_value = [{"status": "PENDING"}]
        result = _build_sitrep_payload(sim, hitl)
        assert "2 active contact" in result["sitrep_narrative"]
        assert result["confidence"] == 0.7
        assert len(result["key_threats"]) == 2
        assert any("pending" in a.lower() for a in result["recommended_actions"])

    def test_query_included(self):
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        result = _build_sitrep_payload(sim, hitl, "test query")
        assert result["query"] == "test query"

    def test_query_omitted_when_empty(self):
        sim = MagicMock()
        sim.get_state.return_value = {"targets": []}
        hitl = MagicMock()
        hitl.get_strike_board.return_value = []
        result = _build_sitrep_payload(sim, hitl)
        assert "query" not in result


# ---------------------------------------------------------------------------
# Dispatch table completeness
# ---------------------------------------------------------------------------


class TestDispatchTableCompleteness:
    def test_all_schema_actions_in_dispatch(self):
        """Every action with a validation schema should be in the dispatch table."""
        for action in _ACTION_SCHEMAS:
            assert action in _DISPATCH_TABLE, f"Action '{action}' has schema but no handler"

    def test_type_forward_set(self):
        assert "DRONE_FEED" in _TYPE_FORWARD
        assert "TRACK_UPDATE" in _TYPE_FORWARD
        assert "TRACK_UPDATE_BATCH" in _TYPE_FORWARD
