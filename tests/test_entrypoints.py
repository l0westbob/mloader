"""Tests for importable runtime entrypoint modules."""

from __future__ import annotations

import importlib


def test_import_mloader_main_module() -> None:
    """Verify the compatibility entrypoint module can be imported."""
    module = importlib.reload(importlib.import_module("mloader.main"))
    assert callable(module.main)


def test_import_mloader_dunder_main_module() -> None:
    """Verify the ``python -m`` entrypoint module can be imported."""
    module = importlib.reload(importlib.import_module("mloader.__main__"))
    assert callable(module.main)


def test_import_cli_init_module() -> None:
    """Verify the legacy CLI init module exports the main command."""
    module = importlib.reload(importlib.import_module("mloader.cli.init"))
    assert callable(module.main)
