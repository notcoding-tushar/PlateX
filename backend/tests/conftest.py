"""Pytest configuration and shared fixtures for HOSNT12 tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_PATH = REPO_ROOT / "archive" / "Higher Validated 5-11-26.py"


@pytest.fixture(scope="session")
def legacy_solver_module():
    """Load archive/Higher Validated 5-11-26.py dynamically for parity testing."""
    if not LEGACY_PATH.exists():
        pytest.skip(f"Legacy reference script not found at {LEGACY_PATH}")
    spec = importlib.util.spec_from_file_location("legacy_hosnt12", LEGACY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module
