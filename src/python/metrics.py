"""Prometheus-compatible metrics for Palantir C2.

Implements the Prometheus text exposition format (0.0.4) without requiring
the prometheus_client library.  Each metric is stored as a frozen snapshot
dataclass; mutable state lives in a single module-level ``_State`` object
that helper functions update atomically.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from typing import Final

# ---------------------------------------------------------------------------
# Internal mutable state (protected by a lock)
# ---------------------------------------------------------------------------

_lock: Final = threading.Lock()


@dataclasses.dataclass
class _State:
    tick_durations: list[float] = dataclasses.field(default_factory=list)
    connected_clients: int = 0
    detection_events_total: int = 0
    hitl_approvals_total: int = 0
    hitl_rejections_total: int = 0
    targets_active: int = 0
    drones_active: int = 0
    autonomy_level: str = "MANUAL"


_state = _State()


# ---------------------------------------------------------------------------
# Frozen snapshot (immutable view for callers)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MetricsSnapshot:
    tick_count: int
    tick_duration_sum: float
    tick_duration_p50: float
    connected_clients: int
    detection_events_total: int
    hitl_approvals_total: int
    hitl_rejections_total: int
    targets_active: int
    drones_active: int
    autonomy_level: str
    timestamp: float


# ---------------------------------------------------------------------------
# Helper functions (public API)
# ---------------------------------------------------------------------------


def record_tick(duration_seconds: float) -> None:
    """Record a simulation tick duration."""
    with _lock:
        _state.tick_durations.append(duration_seconds)
        # Keep a bounded window to avoid unbounded memory growth
        if len(_state.tick_durations) > 10_000:
            _state.tick_durations = _state.tick_durations[-5_000:]


def increment_detection() -> None:
    """Increment the detection events counter."""
    with _lock:
        _state.detection_events_total += 1


def increment_approval() -> None:
    """Increment the HITL approval counter."""
    with _lock:
        _state.hitl_approvals_total += 1


def increment_rejection() -> None:
    """Increment the HITL rejection counter."""
    with _lock:
        _state.hitl_rejections_total += 1


def update_gauges(
    client_count: int,
    target_count: int,
    drone_count: int,
    autonomy_level: str,
) -> None:
    """Update all gauge values atomically."""
    with _lock:
        _state.connected_clients = client_count
        _state.targets_active = target_count
        _state.drones_active = drone_count
        _state.autonomy_level = autonomy_level


def get_snapshot() -> MetricsSnapshot:
    """Return an immutable snapshot of current metric values."""
    with _lock:
        durations = list(_state.tick_durations)
        snapshot = MetricsSnapshot(
            tick_count=len(durations),
            tick_duration_sum=sum(durations),
            tick_duration_p50=_percentile(durations, 50) if durations else 0.0,
            connected_clients=_state.connected_clients,
            detection_events_total=_state.detection_events_total,
            hitl_approvals_total=_state.hitl_approvals_total,
            hitl_rejections_total=_state.hitl_rejections_total,
            targets_active=_state.targets_active,
            drones_active=_state.drones_active,
            autonomy_level=_state.autonomy_level,
            timestamp=time.time(),
        )
    return snapshot


def reset() -> None:
    """Reset all metrics to zero (useful in tests)."""
    global _state
    with _lock:
        _state = _State()


# ---------------------------------------------------------------------------
# Prometheus text exposition (format version 0.0.4)
# ---------------------------------------------------------------------------

_AUTONOMY_LEVELS: Final = ("MANUAL", "SUPERVISED", "AUTONOMOUS")


def generate_metrics_text() -> str:
    """Return Prometheus text exposition format string."""
    s = get_snapshot()
    lines: list[str] = []

    def _gauge(name: str, help_text: str, value: float, labels: str = "") -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        label_str = f"{{{labels}}}" if labels else ""
        lines.append(f"{name}{label_str} {_fmt(value)}")

    def _counter(name: str, help_text: str, value: float) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name}_total {_fmt(value)}")

    def _histogram(name: str, help_text: str, count: int, total: float, p50: float) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} histogram")
        # Emit a single quantile as a summary-style gauge for simplicity
        lines.append(f'{name}_bucket{{le="0.1"}} {count}')
        lines.append(f'{name}_bucket{{le="+Inf"}} {count}')
        lines.append(f"{name}_sum {_fmt(total)}")
        lines.append(f"{name}_count {count}")

    _histogram(
        "palantir_tick_duration_seconds",
        "Simulation tick duration in seconds",
        s.tick_count,
        s.tick_duration_sum,
        s.tick_duration_p50,
    )

    _gauge(
        "palantir_connected_clients",
        "Number of currently connected WebSocket clients",
        s.connected_clients,
    )

    _counter(
        "palantir_detection_events",
        "Total detection events from simulation engine",
        s.detection_events_total,
    )

    _counter(
        "palantir_hitl_approvals",
        "Total HITL nomination approvals",
        s.hitl_approvals_total,
    )

    _counter(
        "palantir_hitl_rejections",
        "Total HITL nomination rejections",
        s.hitl_rejections_total,
    )

    _gauge(
        "palantir_targets_active",
        "Number of active (non-destroyed) targets",
        s.targets_active,
    )

    _gauge(
        "palantir_drones_active",
        "Number of operational drones",
        s.drones_active,
    )

    # Autonomy level as one-hot gauges with label
    lines.append("# HELP palantir_autonomy_level Current autonomy level (1 = active)")
    lines.append("# TYPE palantir_autonomy_level gauge")
    sanitized_level = s.autonomy_level if s.autonomy_level in _AUTONOMY_LEVELS else "UNKNOWN"
    for level in _AUTONOMY_LEVELS:
        active = 1 if sanitized_level == level else 0
        lines.append(f'palantir_autonomy_level{{level="{level}"}} {active}')

    lines.append("")  # trailing newline required by spec
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _percentile(data: list[float], pct: int) -> float:
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def _fmt(value: float) -> str:
    """Format a float for Prometheus exposition (no scientific notation for small values)."""
    if value == int(value):
        return str(int(value))
    return f"{value:.6g}"
