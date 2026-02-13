"""Tests for importable runtime entrypoint modules."""

from __future__ import annotations

import importlib


def test_import_mloader_dunder_main_module() -> None:
    """Verify the ``python -m`` entrypoint module can be imported."""
    module = importlib.reload(importlib.import_module("mloader.__main__"))
    assert callable(module.main)
