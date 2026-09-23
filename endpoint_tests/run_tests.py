"""Convenience runner for the standalone endpoint tests.

Usage:
    python endpoint_tests/run_tests.py            # run all
    python endpoint_tests/run_tests.py -k chart   # pass extra pytest args

Equivalent to `python -m pytest endpoint_tests`, but works from any working
directory and needs no manual PYTHONPATH setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    # -p no:cacheprovider keeps pytest from writing a .pytest_cache at the
    # project root, so every artifact stays inside this deletable folder.
    raise SystemExit(
        pytest.main([str(HERE), "-v", "-p", "no:cacheprovider", *sys.argv[1:]])
    )
