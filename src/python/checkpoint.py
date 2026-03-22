"""checkpoint.py
================
Save/restore full simulation state as JSON snapshots for reproducibility
and replay.

Public API
----------
save_checkpoint(sim)            -> dict  (JSON-serializable blob)
load_checkpoint(blob)           -> dict  (validated blob)
save_to_file(blob, filepath)    -> None
load_from_file(filepath)        -> dict
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sim_engine import SimulationModel

# Increment when the schema changes in a backward-incompatible way.
CHECKPOINT_VERSION: int = 1

# Versions that can be loaded without error.
_COMPATIBLE_VERSIONS: frozenset[int] = frozenset({1})


class CheckpointError(ValueError):
    """Raised when a checkpoint blob is invalid or incompatible."""


def save_checkpoint(sim: "SimulationModel") -> dict:
    """Serialize full simulation state to a JSON-serializable dict.

    Parameters
    ----------
    sim:
        A SimulationModel instance. Only ``get_state()`` and
        ``tick_count`` are read; no internal mutation occurs.

    Returns
    -------
    dict with two top-level keys:
        ``state``    — exact output of ``sim.get_state()``
        ``metadata`` — timestamp, tick_count, checkpoint_version
    """
    state = sim.get_state()
    tick_count = getattr(sim, "tick_count", 0)
    return {
        "state": state,
        "metadata": {
            "timestamp": time.time(),
            "tick_count": tick_count,
            "checkpoint_version": CHECKPOINT_VERSION,
        },
    }


def load_checkpoint(blob: dict) -> dict:
    """Validate and return a checkpoint blob.

    Parameters
    ----------
    blob:
        A dict previously returned by ``save_checkpoint``.

    Returns
    -------
    The same blob after validation.

    Raises
    ------
    CheckpointError
        If ``blob`` is not a dict, is missing required keys, or was
        produced by an incompatible checkpoint version.
    """
    if not isinstance(blob, dict):
        raise CheckpointError(f"Invalid checkpoint: expected dict, got {type(blob).__name__}")

    if "state" not in blob:
        raise CheckpointError("Missing required key: 'state'")
    if "metadata" not in blob:
        raise CheckpointError("Missing required key: 'metadata'")

    meta = blob["metadata"]
    version = meta.get("checkpoint_version")
    if version not in _COMPATIBLE_VERSIONS:
        raise CheckpointError(f"Incompatible checkpoint version {version!r}. Supported: {sorted(_COMPATIBLE_VERSIONS)}")

    return blob


def save_to_file(blob: dict, filepath: str) -> None:
    """Write a checkpoint blob to a JSON file.

    Parameters
    ----------
    blob:
        A dict returned by ``save_checkpoint``.
    filepath:
        Destination file path (created or overwritten).
    """
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)


def load_from_file(filepath: str) -> dict:
    """Load and validate a checkpoint from a JSON file.

    Parameters
    ----------
    filepath:
        Path to a file previously written by ``save_to_file``.

    Returns
    -------
    Validated checkpoint dict.

    Raises
    ------
    FileNotFoundError
        If ``filepath`` does not exist.
    CheckpointError
        If the file contains invalid JSON or an incompatible checkpoint.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        try:
            blob = json.load(fh)
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"Invalid JSON in checkpoint file: {exc}") from exc

    return load_checkpoint(blob)
