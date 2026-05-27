"""Tests for core CLI command orchestration."""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import CliRunner

from mloader.cli import download_command as cli_download_command
from mloader.cli import main as cli_main
from mloader.cli.exit_codes import VALIDATION_ERROR
from mloader.config import AuthSettings
from tests.cli_fakes import RecordingDownloadRuntime

CHAPTER_ID = "1024959"


def test_cli_uses_default_info_logging_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI configures INFO logging in default output mode."""
    observed_level: int | None = None

    def _setup_logging(*, level: int, stream: Any = None) -> None:
        nonlocal observed_level
        del stream
        observed_level = level

    monkeypatch.setattr(cli_main, "setup_logging", _setup_logging)
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == 0
    assert observed_level == 20


def test_cli_exits_when_auth_os_value_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI warns and exits when auth OS config value is unsupported."""
    monkeypatch.setattr(
        cli_main,
        "AUTH_SETTINGS",
        AuthSettings(
            app_ver="97",
            os="Windows_NT",
            os_ver="18.1",
            secret="secret",
        ),
    )
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == VALIDATION_ERROR
    assert "Unsupported API auth OS value" in result.output
    assert "Windows_NT" in result.output


def test_cli_uses_warning_logging_level_in_quiet_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --quiet configures WARNING logging and suppresses intro text."""
    observed_level: int | None = None

    def _setup_logging(*, level: int, stream: Any = None) -> None:
        nonlocal observed_level
        del stream
        observed_level = level

    monkeypatch.setattr(cli_main, "setup_logging", _setup_logging)
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--quiet"])

    assert result.exit_code == 0
    assert observed_level == 30
    assert cli_main.about.__intro__ not in result.output


def test_cli_uses_debug_logging_level_in_verbose_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --verbose enables DEBUG logging level."""
    observed_level: int | None = None

    def _setup_logging(*, level: int, stream: Any = None) -> None:
        nonlocal observed_level
        del stream
        observed_level = level

    monkeypatch.setattr(cli_main, "setup_logging", _setup_logging)
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--verbose"])

    assert result.exit_code == 0
    assert observed_level == 10


def test_cli_without_ids_prints_help_and_exits_cleanly() -> None:
    """Verify CLI prints usage text when no chapter/title input is provided."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Examples:" not in result.output


def test_cli_show_examples_exits_without_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --show-examples prints catalog and exits before download workflow."""
    invoked = {"download_called": False}

    def _raise_if_called(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        invoked["download_called"] = True
        raise AssertionError("execute_download should not be called in --show-examples mode")

    monkeypatch.setattr(
        cli_download_command.download_use_cases,
        "execute_download",
        _raise_if_called,
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--show-examples"])

    assert result.exit_code == 0
    assert "mloader example catalog" in result.output
    assert "--manifest-reset" in result.output
    assert invoked["download_called"] is False


def test_cli_show_examples_json_mode_returns_catalog() -> None:
    """Verify --show-examples with --json emits structured example payload."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--show-examples", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["mode"] == "show_examples"
    assert payload["count"] > 0
    assert isinstance(payload["examples"], list)
