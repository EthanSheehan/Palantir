"""
Tests for comms_sim.py — TDD RED phase.

Covers:
- CommsPreset enum values
- PRESET_CONFIGS mapping to expected ranges
- CommsLink frozen dataclass creation
- CommsState creation with multiple drones
- set_link_preset immutability
- attempt_delivery with latency and packet loss
- degrade_all_links multiplies latency/loss
- get_failsafe_mode per preset
- create_comms_state defaults
- Edge cases: empty drone list, unknown preset, full loss
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from comms_sim import (
    PRESET_CONFIGS,
    CommsLink,
    CommsPreset,
    attempt_delivery,
    create_comms_state,
    degrade_all_links,
    get_failsafe_mode,
    set_link_preset,
)

# ---------------------------------------------------------------------------
# 1. CommsPreset enum
# ---------------------------------------------------------------------------


class TestCommsPreset:
    def test_full_preset_exists(self):
        assert CommsPreset.FULL is not None

    def test_contested_preset_exists(self):
        assert CommsPreset.CONTESTED is not None

    def test_denied_preset_exists(self):
        assert CommsPreset.DENIED is not None

    def test_reconnect_preset_exists(self):
        assert CommsPreset.RECONNECT is not None

    def test_all_four_presets_distinct(self):
        presets = [CommsPreset.FULL, CommsPreset.CONTESTED, CommsPreset.DENIED, CommsPreset.RECONNECT]
        assert len(set(presets)) == 4


# ---------------------------------------------------------------------------
# 2. PRESET_CONFIGS
# ---------------------------------------------------------------------------


class TestPresetConfigs:
    def test_all_presets_in_config(self):
        for preset in CommsPreset:
            assert preset in PRESET_CONFIGS

    def test_full_has_zero_latency(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.FULL]
        assert latency_ms == 0.0

    def test_full_has_zero_loss(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.FULL]
        assert loss == 0.0

    def test_full_has_high_bandwidth(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.FULL]
        assert bandwidth > 0

    def test_denied_has_max_loss(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.DENIED]
        assert loss == 1.0

    def test_denied_has_zero_bandwidth(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.DENIED]
        assert bandwidth == 0.0

    def test_contested_has_partial_loss(self):
        latency_ms, loss, bandwidth = PRESET_CONFIGS[CommsPreset.CONTESTED]
        assert 0.0 < loss < 1.0

    def test_contested_latency_greater_than_full(self):
        full_lat, _, _ = PRESET_CONFIGS[CommsPreset.FULL]
        contested_lat, _, _ = PRESET_CONFIGS[CommsPreset.CONTESTED]
        assert contested_lat > full_lat

    def test_reconnect_has_partial_loss(self):
        _, loss, _ = PRESET_CONFIGS[CommsPreset.RECONNECT]
        assert 0.0 < loss < 1.0

    def test_config_values_are_tuples_of_three(self):
        for preset, config in PRESET_CONFIGS.items():
            assert len(config) == 3


# ---------------------------------------------------------------------------
# 3. CommsLink dataclass
# ---------------------------------------------------------------------------


class TestCommsLink:
    def test_comms_link_is_frozen(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=0.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=1000.0,
            is_connected=True,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            link.latency_ms = 100.0  # type: ignore[misc]

    def test_comms_link_stores_drone_id(self):
        link = CommsLink(
            drone_id="uav-42",
            preset=CommsPreset.CONTESTED,
            latency_ms=50.0,
            packet_loss_rate=0.3,
            bandwidth_kbps=200.0,
            is_connected=True,
        )
        assert link.drone_id == "uav-42"

    def test_comms_link_denied_not_connected(self):
        _, _, _ = PRESET_CONFIGS[CommsPreset.DENIED]
        link = CommsLink(
            drone_id="uav-3",
            preset=CommsPreset.DENIED,
            latency_ms=9999.0,
            packet_loss_rate=1.0,
            bandwidth_kbps=0.0,
            is_connected=False,
        )
        assert link.is_connected is False

    def test_comms_link_has_all_fields(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=0.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=1000.0,
            is_connected=True,
        )
        assert hasattr(link, "drone_id")
        assert hasattr(link, "preset")
        assert hasattr(link, "latency_ms")
        assert hasattr(link, "packet_loss_rate")
        assert hasattr(link, "bandwidth_kbps")
        assert hasattr(link, "is_connected")


# ---------------------------------------------------------------------------
# 4. CommsState dataclass
# ---------------------------------------------------------------------------


class TestCommsState:
    def test_comms_state_is_frozen(self):
        state = create_comms_state(["uav-1"])
        with pytest.raises((FrozenInstanceError, AttributeError)):
            state.links = {}  # type: ignore[misc]

    def test_comms_state_has_links(self):
        state = create_comms_state(["uav-1", "uav-2"])
        assert hasattr(state, "links")

    def test_comms_state_has_pending_messages(self):
        state = create_comms_state(["uav-1"])
        assert hasattr(state, "pending_messages")

    def test_pending_messages_initially_empty(self):
        state = create_comms_state(["uav-1"])
        assert len(state.pending_messages) == 0


# ---------------------------------------------------------------------------
# 5. create_comms_state
# ---------------------------------------------------------------------------


class TestCreateCommsState:
    def test_creates_link_for_each_drone(self):
        state = create_comms_state(["uav-1", "uav-2", "uav-3"])
        assert len(state.links) == 3

    def test_default_preset_is_full(self):
        state = create_comms_state(["uav-1"])
        link = state.links["uav-1"]
        assert link.preset == CommsPreset.FULL

    def test_custom_preset_applied_to_all(self):
        state = create_comms_state(["uav-1", "uav-2"], preset=CommsPreset.CONTESTED)
        for drone_id, link in state.links.items():
            assert link.preset == CommsPreset.CONTESTED

    def test_empty_drone_list_creates_empty_state(self):
        state = create_comms_state([])
        assert len(state.links) == 0

    def test_drone_id_matches_in_link(self):
        state = create_comms_state(["alpha", "bravo"])
        assert state.links["alpha"].drone_id == "alpha"
        assert state.links["bravo"].drone_id == "bravo"

    def test_full_preset_link_is_connected(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.FULL)
        assert state.links["uav-1"].is_connected is True

    def test_denied_preset_link_is_not_connected(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.DENIED)
        assert state.links["uav-1"].is_connected is False


# ---------------------------------------------------------------------------
# 6. set_link_preset (immutability)
# ---------------------------------------------------------------------------


class TestSetLinkPreset:
    def test_returns_new_state(self):
        state = create_comms_state(["uav-1"])
        new_state = set_link_preset(state, "uav-1", CommsPreset.CONTESTED)
        assert new_state is not state

    def test_original_state_unchanged(self):
        state = create_comms_state(["uav-1"])
        original_preset = state.links["uav-1"].preset
        set_link_preset(state, "uav-1", CommsPreset.CONTESTED)
        assert state.links["uav-1"].preset == original_preset

    def test_new_state_has_updated_preset(self):
        state = create_comms_state(["uav-1"])
        new_state = set_link_preset(state, "uav-1", CommsPreset.DENIED)
        assert new_state.links["uav-1"].preset == CommsPreset.DENIED

    def test_other_drones_unaffected(self):
        state = create_comms_state(["uav-1", "uav-2"])
        new_state = set_link_preset(state, "uav-1", CommsPreset.DENIED)
        assert new_state.links["uav-2"].preset == CommsPreset.FULL

    def test_set_denied_marks_disconnected(self):
        state = create_comms_state(["uav-1"])
        new_state = set_link_preset(state, "uav-1", CommsPreset.DENIED)
        assert new_state.links["uav-1"].is_connected is False

    def test_set_full_marks_connected(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.DENIED)
        new_state = set_link_preset(state, "uav-1", CommsPreset.FULL)
        assert new_state.links["uav-1"].is_connected is True

    def test_links_dict_is_not_mutated(self):
        state = create_comms_state(["uav-1", "uav-2"])
        original_links = state.links
        new_state = set_link_preset(state, "uav-1", CommsPreset.CONTESTED)
        assert state.links is original_links


# ---------------------------------------------------------------------------
# 7. attempt_delivery
# ---------------------------------------------------------------------------


class TestAttemptDelivery:
    def test_full_link_always_delivers(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=0.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=1000.0,
            is_connected=True,
        )
        msg = {"type": "command", "payload": "move"}
        delivered, delay = attempt_delivery(link, msg)
        assert delivered is True
        assert delay == pytest.approx(0.0)

    def test_denied_link_never_delivers(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.DENIED,
            latency_ms=9999.0,
            packet_loss_rate=1.0,
            bandwidth_kbps=0.0,
            is_connected=False,
        )
        msg = {"type": "command", "payload": "move"}
        # With 100% loss, delivery must always fail
        for _ in range(20):
            delivered, delay = attempt_delivery(link, msg)
            assert delivered is False

    def test_returns_tuple_of_bool_and_float(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=10.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=500.0,
            is_connected=True,
        )
        result = attempt_delivery(link, {"type": "ping"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        delivered, delay = result
        assert isinstance(delivered, bool)
        assert isinstance(delay, float)

    def test_full_link_delay_equals_latency(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=25.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=1000.0,
            is_connected=True,
        )
        delivered, delay = attempt_delivery(link, {"type": "ping"})
        assert delivered is True
        assert delay == pytest.approx(25.0)

    def test_contested_eventually_delivers(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.CONTESTED,
            latency_ms=50.0,
            packet_loss_rate=0.3,
            bandwidth_kbps=200.0,
            is_connected=True,
        )
        msg = {"type": "command"}
        # With 30% loss, should deliver at least once in 30 tries
        deliveries = [attempt_delivery(link, msg)[0] for _ in range(30)]
        assert any(deliveries)

    def test_contested_sometimes_drops(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.CONTESTED,
            latency_ms=50.0,
            packet_loss_rate=0.9,
            bandwidth_kbps=200.0,
            is_connected=True,
        )
        msg = {"type": "command"}
        # With 90% loss, at least some should drop in 30 tries
        deliveries = [attempt_delivery(link, msg)[0] for _ in range(30)]
        assert not all(deliveries)

    def test_disconnected_link_never_delivers(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.RECONNECT,
            latency_ms=200.0,
            packet_loss_rate=0.5,
            bandwidth_kbps=50.0,
            is_connected=False,
        )
        for _ in range(10):
            delivered, _ = attempt_delivery(link, {"type": "ping"})
            assert delivered is False


# ---------------------------------------------------------------------------
# 8. degrade_all_links
# ---------------------------------------------------------------------------


class TestDegradeAllLinks:
    def test_returns_new_state(self):
        state = create_comms_state(["uav-1"])
        new_state = degrade_all_links(state, factor=1.5)
        assert new_state is not state

    def test_original_state_unchanged(self):
        state = create_comms_state(["uav-1"])
        original_latency = state.links["uav-1"].latency_ms
        degrade_all_links(state, factor=2.0)
        assert state.links["uav-1"].latency_ms == original_latency

    def test_latency_multiplied_by_factor(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.CONTESTED)
        original_latency = state.links["uav-1"].latency_ms
        new_state = degrade_all_links(state, factor=2.0)
        assert new_state.links["uav-1"].latency_ms == pytest.approx(original_latency * 2.0)

    def test_packet_loss_capped_at_1(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.CONTESTED)
        # Apply extreme degradation — loss should never exceed 1.0
        new_state = degrade_all_links(state, factor=100.0)
        assert new_state.links["uav-1"].packet_loss_rate <= 1.0

    def test_bandwidth_reduced_by_factor(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.FULL)
        original_bw = state.links["uav-1"].bandwidth_kbps
        new_state = degrade_all_links(state, factor=2.0)
        assert new_state.links["uav-1"].bandwidth_kbps == pytest.approx(original_bw / 2.0)

    def test_all_drones_degraded(self):
        state = create_comms_state(["uav-1", "uav-2", "uav-3"])
        # Change all to CONTESTED so there's something to degrade
        for drone_id in ["uav-1", "uav-2", "uav-3"]:
            state = set_link_preset(state, drone_id, CommsPreset.CONTESTED)
        original_latencies = {k: v.latency_ms for k, v in state.links.items()}
        new_state = degrade_all_links(state, factor=1.5)
        for drone_id in ["uav-1", "uav-2", "uav-3"]:
            assert new_state.links[drone_id].latency_ms >= original_latencies[drone_id]

    def test_factor_one_is_no_change_for_loss(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.CONTESTED)
        original_loss = state.links["uav-1"].packet_loss_rate
        new_state = degrade_all_links(state, factor=1.0)
        assert new_state.links["uav-1"].packet_loss_rate == pytest.approx(original_loss)

    def test_bandwidth_floor_zero(self):
        state = create_comms_state(["uav-1"], preset=CommsPreset.FULL)
        new_state = degrade_all_links(state, factor=999999.0)
        assert new_state.links["uav-1"].bandwidth_kbps >= 0.0


# ---------------------------------------------------------------------------
# 9. get_failsafe_mode
# ---------------------------------------------------------------------------


class TestGetFailsafeMode:
    def test_denied_returns_rtb(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.DENIED,
            latency_ms=9999.0,
            packet_loss_rate=1.0,
            bandwidth_kbps=0.0,
            is_connected=False,
        )
        mode = get_failsafe_mode(link)
        assert mode == "RTB"

    def test_contested_returns_overwatch(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.CONTESTED,
            latency_ms=50.0,
            packet_loss_rate=0.3,
            bandwidth_kbps=200.0,
            is_connected=True,
        )
        mode = get_failsafe_mode(link)
        assert mode == "OVERWATCH"

    def test_full_returns_none_or_nominal(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.FULL,
            latency_ms=0.0,
            packet_loss_rate=0.0,
            bandwidth_kbps=1000.0,
            is_connected=True,
        )
        mode = get_failsafe_mode(link)
        assert mode is None or mode == "NOMINAL"

    def test_reconnect_returns_overwatch(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.RECONNECT,
            latency_ms=200.0,
            packet_loss_rate=0.4,
            bandwidth_kbps=50.0,
            is_connected=False,
        )
        mode = get_failsafe_mode(link)
        assert mode == "OVERWATCH"

    def test_returns_string(self):
        link = CommsLink(
            drone_id="uav-1",
            preset=CommsPreset.DENIED,
            latency_ms=9999.0,
            packet_loss_rate=1.0,
            bandwidth_kbps=0.0,
            is_connected=False,
        )
        mode = get_failsafe_mode(link)
        assert mode is None or isinstance(mode, str)
