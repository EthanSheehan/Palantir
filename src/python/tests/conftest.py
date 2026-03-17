"""Pytest configuration — add src/python to sys.path so bare imports work."""

import sys
from pathlib import Path

# Insert src/python at the front of sys.path
_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
