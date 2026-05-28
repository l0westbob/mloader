"""Tests for CLI JSON, run-report, and error-report behavior."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from mloader.application import requests as app_requests
from mloader.cli import main as cli_main
from mloader.cli.download_command import run_download_request
from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG
from mloader.cli.presenter import CliPresenter
from mloader.cli.run_report import write_run_report_if_requested
from mloader.domain.requests import DownloadSummary
from tests.cli_fakes import (
    DEFAULT_FAILED_CHAPTER_IDS,
    DEFAULT_INTERRUPTED_CHAPTER_ID,
    InterruptedDownloadRuntime,
    PartialFailureDownloadRuntime,
    RecordingDownloadRuntime,
    RecordingPdfExporter,
    RecordingRawExporter,
    RequestErrorDownloadRuntime,
    RuntimeFailingDownloadRuntime,
)

CHAPTER_ID = "1024959"


def test_cli_json_mode_returns_structured_success_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json returns machine-readable success payload for downloads."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter-id", CHAPTER_ID])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["mode"] == "download"
    assert payload["exit_code"] == 0
    assert payload["targets"]["chapters"] == 0
    assert payload["targets"]["chapter_ids"] == 1
    assert payload["summary"] == {
        "downloaded": 1,
        "skipped_manifest": 0,
        "failed": 0,
        "failed_chapter_ids": [],
    }


def test_cli_writes_run_report_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify optional run reports capture cron-friendly run metadata."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)
    report_path = tmp_path / "run-report.json"

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--chapter-id", CHAPTER_ID, "--run-report", str(report_path)],
    )

    assert result.exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["exit_code"] == 0
    assert report["selected_args"]["target_chapter_ids"] == 1
    assert report["selected_args"]["cover"] is False
    assert report["selected_args"]["cover_format"] == "png"
    assert report["summary"]["downloaded"] == 1
    assert report["subscription_access_failures"] == 0
    assert report["exporter_safety"]["version"] == "pdf-streaming-and-atomic-cbz-v1"


def test_cli_writes_error_run_report_when_download_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify failed runs include error text in optional run reports."""
    monkeypatch.setattr(cli_main, "MangaLoader", RuntimeFailingDownloadRuntime)
    report_path = tmp_path / "run-report.json"

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--chapter-id", CHAPTER_ID, "--run-report", str(report_path)],
    )

    assert result.exit_code == INTERNAL_BUG
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["exit_code"] == INTERNAL_BUG
    assert "Download failed: boom" == report["error"]


def test_run_report_write_errors_are_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify report write failures do not mask the original CLI outcome."""
    request = app_requests.build_download_request(
        out_dir="/tmp/downloads",
        raw=False,
        output_format="cbz",
        capture_api_dir=None,
        quality="high",
        split=False,
        begin=0,
        end=None,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        cover=False,
        cover_format="png",
        resume=True,
        manifest_reset=False,
        chapters=None,
        chapter_ids={int(CHAPTER_ID)},
        titles=None,
        run_report_path="/tmp/report.json",
    )

    def _raise_write_error(self: Path, *_args: object, **_kwargs: object) -> int:
        del self
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _raise_write_error)
    caplog.set_level(logging.WARNING)

    write_run_report_if_requested(
        request,
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        status="ok",
        exit_code=0,
        discovery=None,
        summary=DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=0,
            failed_chapter_ids=(),
        ),
        error_message=None,
    )

    assert "Failed to write run report" in caplog.text


def test_run_download_request_injects_report_run_id_and_clock() -> None:
    """Verify download command reporting does not depend on global time/id state."""
    request = app_requests.build_download_request(
        out_dir="/tmp/downloads",
        raw=False,
        output_format="cbz",
        capture_api_dir=None,
        quality="high",
        split=False,
        begin=0,
        end=None,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        cover=False,
        cover_format="png",
        resume=True,
        manifest_reset=False,
        chapters=None,
        chapter_ids={int(CHAPTER_ID)},
        titles=None,
        run_report_path="/tmp/report.json",
    )
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed_at = datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    timestamps = iter((started_at, completed_at))
    reports: list[dict[str, object]] = []

    def _write_report(_request: object, **kwargs: object) -> None:
        reports.append(kwargs)

    run_download_request(
        request,
        presenter=CliPresenter(json_output=False, quiet=True),
        discovery_metadata=None,
        loader_factory=RecordingDownloadRuntime,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingRawExporter,
        write_run_report=_write_report,
        run_id_factory=lambda: "fixed-run-id",
        clock=lambda: next(timestamps),
    )

    assert reports == [
        {
            "run_id": "fixed-run-id",
            "started_at": started_at,
            "completed_at": completed_at,
            "status": "ok",
            "exit_code": 0,
            "discovery": None,
            "summary": DownloadSummary(
                downloaded=1,
                skipped_manifest=0,
                failed=0,
                failed_chapter_ids=(),
            ),
            "error_message": None,
        }
    ]


def test_cli_json_mode_returns_structured_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json returns machine-readable error payload and deterministic exit code."""
    monkeypatch.setattr(cli_main, "MangaLoader", RuntimeFailingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter-id", CHAPTER_ID])

    assert result.exit_code == INTERNAL_BUG
    payload = json.loads(result.output)
    assert payload == {
        "status": "error",
        "exit_code": INTERNAL_BUG,
        "message": "Download failed",
    }


def test_cli_maps_request_failures_to_external_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify request-layer failures are mapped to external-failure exit code."""
    monkeypatch.setattr(cli_main, "MangaLoader", RequestErrorDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download request failed: network down" in result.output


def test_cli_maps_interrupted_download_to_external_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify interrupted runs include partial summary and map to external failure."""
    monkeypatch.setattr(cli_main, "MangaLoader", InterruptedDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download summary: downloaded=1, skipped_manifest=1, failed=1" in result.output
    assert f"Failed chapter IDs: {DEFAULT_INTERRUPTED_CHAPTER_ID}" in result.output
    assert "Download interrupted by user." in result.output


def test_cli_returns_external_failure_when_summary_has_failed_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed chapter summary maps to external failure exit code."""
    monkeypatch.setattr(cli_main, "MangaLoader", PartialFailureDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download completed with 2 failed chapter(s)." in result.output


def test_cli_json_mode_includes_failed_summary_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify JSON error payload includes summary details for partial failures."""
    monkeypatch.setattr(cli_main, "MangaLoader", PartialFailureDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    payload = json.loads(result.output)
    assert payload == {
        "status": "error",
        "exit_code": EXTERNAL_FAILURE,
        "message": "Download completed with 2 failed chapter(s).",
        "summary": {
            "downloaded": 2,
            "skipped_manifest": 1,
            "failed": 2,
            "failed_chapter_ids": [DEFAULT_FAILED_CHAPTER_IDS[0], DEFAULT_FAILED_CHAPTER_IDS[1]],
        },
    }


def test_cli_json_mode_includes_interrupted_summary_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify interrupted runs emit JSON error payload including partial summary."""
    monkeypatch.setattr(cli_main, "MangaLoader", InterruptedDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    payload = json.loads(result.output)
    assert payload == {
        "status": "error",
        "exit_code": EXTERNAL_FAILURE,
        "message": "Download interrupted by user.",
        "summary": {
            "downloaded": 1,
            "skipped_manifest": 1,
            "failed": 1,
            "failed_chapter_ids": [int(DEFAULT_INTERRUPTED_CHAPTER_ID)],
        },
    }
