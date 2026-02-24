"""Tests for logging configuration helpers."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from mloader.cli import config as cli_config


def test_setup_logging_calls_basic_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure setup_logging configures handlers and logger levels."""
    captured: dict[str, Any] = {}

    def fake_basic_config(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_config.setup_logging()

    assert captured["level"] == logging.INFO
    assert captured["style"] == "{"
    assert captured["force"] is True
    assert isinstance(captured["handlers"][0], logging.StreamHandler)
    assert logging.getLogger("requests").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING


def test_setup_logging_accepts_explicit_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure setup_logging forwards custom logging level overrides."""
    captured: dict[str, Any] = {}

    def fake_basic_config(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    cli_config.setup_logging(level=logging.DEBUG)

    assert captured["level"] == logging.DEBUG


def test_get_logger_returns_named_logger() -> None:
    """Ensure get_logger returns a logger configured with the requested name."""
    logger = cli_config.get_logger("mloader.tests")
    assert logger.name == "mloader.tests"
