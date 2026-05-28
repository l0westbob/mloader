"""Tests for CLI capture-verification mode."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from mloader.cli import command_defaults as cli_defaults
from mloader.cli import main as cli_main
from mloader.cli.exit_codes import VALIDATION_ERROR
from mloader.infrastructure.mangaplus.capture_verify import (
    CaptureVerificationError,
    CaptureVerificationSummary,
)

CHAPTER_ID = "1024959"


def test_cli_verifies_capture_schema_and_exits_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema-verification mode runs and exits without invoking downloads."""
    monkeypatch.setattr(
        cli_defaults,
        "verify_capture_schema",
        lambda _path: CaptureVerificationSummary(
            total_records=3,
            endpoint_counts={"manga_viewer": 2, "title_detailV3": 1},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--verify-capture-schema", "tests/fixtures/api_captures/baseline"],
    )

    assert result.exit_code == 0
    assert "Verified 3 capture payload(s) in tests/fixtures/api_captures/baseline" in result.output


def test_cli_verifies_capture_schema_against_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify baseline comparison mode calls baseline verification path."""
    monkeypatch.setattr(
        cli_defaults,
        "verify_capture_schema_against_baseline",
        lambda _capture, _baseline: CaptureVerificationSummary(
            total_records=3,
            endpoint_counts={"manga_viewer": 2, "title_detailV3": 1},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        [
            "--verify-capture-schema",
            "tests/fixtures/api_captures/baseline",
            "--verify-capture-baseline",
            "tests/fixtures/api_captures/baseline",
        ],
    )

    assert result.exit_code == 0
    assert "against baseline tests/fixtures/api_captures/baseline" in result.output


def test_cli_rejects_baseline_option_without_capture_schema() -> None:
    """Verify baseline option requires a capture directory option."""
    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--verify-capture-baseline", "tests/fixtures/api_captures/baseline"],
    )

    assert result.exit_code == VALIDATION_ERROR
    assert "--verify-capture-baseline requires --verify-capture-schema." in result.output


def test_cli_verify_capture_schema_returns_click_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify verification failures are exposed as click exceptions."""

    def _raise_error(_path: str) -> None:
        raise CaptureVerificationError("schema drift")

    monkeypatch.setattr(cli_defaults, "verify_capture_schema", _raise_error)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--verify-capture-schema", "tests/fixtures/api_captures/baseline"],
    )

    assert result.exit_code == VALIDATION_ERROR
    assert "schema drift" in result.output


def test_cli_verify_capture_schema_json_mode_returns_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json emits machine-readable payload for capture verification mode."""
    monkeypatch.setattr(
        cli_defaults,
        "verify_capture_schema",
        lambda _path: CaptureVerificationSummary(
            total_records=3,
            endpoint_counts={"manga_viewer": 2, "title_detailV3": 1},
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--json", "--verify-capture-schema", "tests/fixtures/api_captures/baseline"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "status": "ok",
        "mode": "verify_capture",
        "exit_code": 0,
        "capture_dir": "tests/fixtures/api_captures/baseline",
        "baseline_dir": None,
        "total_records": 3,
        "endpoint_counts": {"manga_viewer": 2, "title_detailV3": 1},
    }
