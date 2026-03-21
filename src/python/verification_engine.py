from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationThreshold:
    classify_confidence: float  # fused_confidence needed for DETECTED -> CLASSIFIED
    verify_confidence: float  # fused_confidence needed for CLASSIFIED -> VERIFIED
    verify_sensor_types: int  # min distinct sensor types OR...
    verify_sustained_sec: float  # ...sustained detect time threshold (whichever lower)
    regression_timeout_sec: float  # seconds with no sensors before regressing one state


# Per-target-type thresholds (SAMs/TELs verify faster — high threat)
VERIFICATION_THRESHOLDS: dict[str, VerificationThreshold] = {
    "SAM": VerificationThreshold(0.5, 0.7, 2, 10.0, 8.0),
    "TEL": VerificationThreshold(0.5, 0.7, 2, 10.0, 10.0),
    "RADAR": VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "C2_NODE": VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "MANPADS": VerificationThreshold(0.5, 0.7, 2, 10.0, 8.0),
    "CP": VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "TRUCK": VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "LOGISTICS": VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "ARTILLERY": VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "APC": VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
}

# Default threshold for unknown target types
_DEFAULT_THRESHOLD = VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0)

# DEMO_FAST preset: halves all time thresholds, lowers confidence by 0.1
DEMO_FAST_THRESHOLDS: dict[str, VerificationThreshold] = {
    k: VerificationThreshold(
        max(0.3, v.classify_confidence - 0.1),
        max(0.4, v.verify_confidence - 0.1),
        v.verify_sensor_types,
        v.verify_sustained_sec / 2.0,
        v.regression_timeout_sec / 2.0,
    )
    for k, v in VERIFICATION_THRESHOLDS.items()
}

# States the verification engine manages
_MANAGED_STATES = frozenset({"DETECTED", "CLASSIFIED", "VERIFIED"})

# States managed by other systems — never regress these
_TERMINAL_STATES = frozenset({"NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED"})


def evaluate_target_state(
    current_state: str,
    target_type: str,
    fused_confidence: float,
    sensor_type_count: int,
    time_in_current_state_sec: float,
    seconds_since_last_sensor: float,
    demo_fast: bool = False,
) -> str:
    """Pure function: given current evidence, return the new target state.

    Does not modify any object. Returns the same state if no transition occurs.

    Rules:
    - DETECTED -> CLASSIFIED: fused_confidence >= classify_confidence
    - CLASSIFIED -> VERIFIED: fused_confidence >= verify_confidence AND
                               (sensor_type_count >= verify_sensor_types OR
                                time_in_current_state_sec >= verify_sustained_sec)
    - VERIFIED -> NOMINATED: handled externally by ISR/Strategy pipeline (never here)
    - Regression: seconds_since_last_sensor >= regression_timeout_sec -> regress one state
    - Terminal states (NOMINATED, LOCKED, ENGAGED, DESTROYED, ESCAPED): no-op
    """
    if current_state in _TERMINAL_STATES:
        return current_state

    if current_state not in _MANAGED_STATES and current_state != "UNDETECTED":
        return current_state

    thresholds = (DEMO_FAST_THRESHOLDS if demo_fast else VERIFICATION_THRESHOLDS).get(target_type, _DEFAULT_THRESHOLD)

    # Regression: no sensor contact -> step back one state
    if seconds_since_last_sensor >= thresholds.regression_timeout_sec:
        if current_state == "VERIFIED":
            return "CLASSIFIED"
        if current_state == "CLASSIFIED":
            return "DETECTED"
        if current_state == "DETECTED":
            return "UNDETECTED"
        return current_state

    # Promotion rules
    if current_state == "CLASSIFIED":
        meets_sensor_diversity = sensor_type_count >= thresholds.verify_sensor_types
        meets_sustained = time_in_current_state_sec >= thresholds.verify_sustained_sec
        if fused_confidence >= thresholds.verify_confidence and (meets_sensor_diversity or meets_sustained):
            return "VERIFIED"

    elif current_state == "DETECTED":
        if fused_confidence >= thresholds.classify_confidence:
            return "CLASSIFIED"

    return current_state
