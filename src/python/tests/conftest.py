"""Pytest configuration — add src/python to sys.path so bare imports work."""

import os
import sys
from pathlib import Path

# Insert src/python at the front of sys.path
_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Disable RBAC auth checks in test environment so handler tests
# reach the actual handler logic instead of being blocked by permission checks.
os.environ.setdefault("AUTH_DISABLED", "true")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _disable_rbac_for_tests(monkeypatch):
    """Ensure RBAC is disabled even if rbac module was already imported."""
    import rbac  # noqa: E402

    monkeypatch.setattr(rbac, "AUTH_DISABLED", True)
