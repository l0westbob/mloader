"""Tests for CLI output presenter behavior."""

from __future__ import annotations

import json

import pytest

from mloader.cli.examples import CliExample
from mloader.cli.presenter import CliPresenter
from mloader.domain.requests import DownloadSummary
from mloader.manga_loader.capture_verify import CaptureVerificationSummary


def test_presenter_emits_human_intro_when_enabled(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify intro banner is emitted in default human-output mode."""
    presenter = CliPresenter(json_output=False, quiet=False)

    presenter.emit_intro("hello")

    assert "hello" in capsys.readouterr().out


def test_presenter_suppresses_human_intro_in_quiet_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify intro banner is suppressed in quiet mode."""
    presenter = CliPresenter(json_output=False, quiet=True)

    presenter.emit_intro("hello")

    assert capsys.readouterr().out == ""


def test_presenter_emits_capture_summary_json_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify capture summary is emitted as structured JSON in json mode."""
    presenter = CliPresenter(json_output=True, quiet=False)

    presenter.emit_capture_verification(
        summary=CaptureVerificationSummary(total_records=3, endpoint_counts={"a": 1, "b": 2}),
        capture_dir="./capture",
        baseline_dir=None,
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["mode"] == "verify_capture"
    assert payload["total_records"] == 3
    assert payload["endpoint_counts"] == {"a": 1, "b": 2}


def test_presenter_suppresses_capture_summary_in_quiet_human_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify quiet human mode suppresses capture-summary output."""
    presenter = CliPresenter(json_output=False, quiet=True)

    presenter.emit_capture_verification(
        summary=CaptureVerificationSummary(total_records=1, endpoint_counts={"manga_viewer": 1}),
        capture_dir="./capture",
        baseline_dir="./baseline",
    )

    assert capsys.readouterr().out == ""


def test_presenter_emits_download_summary_human_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify human mode prints a compact download summary with failed IDs."""
    presenter = CliPresenter(json_output=False, quiet=False)
    presenter.emit_download_summary(
        DownloadSummary(
            downloaded=3,
            skipped_manifest=2,
            failed=1,
            failed_chapter_ids=(99,),
        )
    )

    output = capsys.readouterr().out
    assert "downloaded=3" in output
    assert "skipped_manifest=2" in output
    assert "failed=1" in output
    assert "99" in output


def test_presenter_suppresses_download_summary_in_quiet_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify quiet mode suppresses download-summary output."""
    presenter = CliPresenter(json_output=False, quiet=True)
    presenter.emit_download_summary(
        DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=0,
            failed_chapter_ids=(),
        )
    )

    assert capsys.readouterr().out == ""


def test_presenter_emits_examples_human_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify presenter prints example catalog in human mode."""
    presenter = CliPresenter(json_output=False, quiet=False)
    presenter.emit_examples(
        [
            CliExample(
                title="Example title",
                command="mloader --chapter-id 102277",
                description="Example description.",
            )
        ]
    )

    output = capsys.readouterr().out
    assert "mloader example catalog" in output
    assert "Example title" in output
    assert "mloader --chapter-id 102277" in output


def test_presenter_emits_examples_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify presenter emits structured example catalog in JSON mode."""
    presenter = CliPresenter(json_output=True, quiet=False)
    presenter.emit_examples(
        [
            CliExample(
                title="Example title",
                command="mloader --chapter-id 102277",
                description="Example description.",
            )
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["mode"] == "show_examples"
    assert payload["count"] == 1
    assert payload["examples"][0]["command"] == "mloader --chapter-id 102277"
