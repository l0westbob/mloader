"""Tests for CLI command orchestration."""

from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest
import requests
from click.testing import CliRunner

from mloader.cli import main as cli_main
from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG, VALIDATION_ERROR
from mloader.domain.requests import DownloadSummary
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.capture_verify import CaptureVerificationError, CaptureVerificationSummary


class DummyLoader:
    """Loader test double capturing constructor and download arguments."""

    init_args: ClassVar[dict[str, Any] | None] = None
    download_args: ClassVar[dict[str, Any] | None] = None

    def __init__(
        self,
        exporter_factory: Any,
        quality: str,
        split: bool,
        meta: bool,
        destination: str,
        output_format: str,
        capture_api_dir: str | None,
        resume: bool,
        manifest_reset: bool,
    ) -> None:
        """Record initialization arguments for assertions."""
        type(self).init_args = {
            "exporter_factory": exporter_factory,
            "quality": quality,
            "split": split,
            "meta": meta,
            "destination": destination,
            "output_format": output_format,
            "capture_api_dir": capture_api_dir,
            "resume": resume,
            "manifest_reset": manifest_reset,
        }

    def download(self, **kwargs: Any) -> DownloadSummary:
        """Record download call keyword arguments for assertions."""
        type(self).download_args = kwargs
        return DownloadSummary(
            downloaded=1,
            skipped_manifest=0,
            failed=0,
            failed_chapter_ids=(),
        )


class DummyRawExporter:
    """Raw exporter marker class for monkeypatched CLI tests."""


class DummyPdfExporter:
    """PDF exporter marker class for monkeypatched CLI tests."""


class FailingLoader(DummyLoader):
    """Loader test double that always raises from download."""

    def download(self, **kwargs: Any) -> None:
        """Raise a runtime error to exercise CLI exception handling."""
        del kwargs
        raise RuntimeError("boom")


class SubscriptionLoader(DummyLoader):
    """Loader test double that raises subscription-required error."""

    def download(self, **kwargs: Any) -> None:
        """Raise a subscription-required error to test CLI messaging."""
        del kwargs
        raise SubscriptionRequiredError("A MAX subscription is required to download this chapter.")


class RequestErrorLoader(DummyLoader):
    """Loader test double that raises request-layer failures."""

    def download(self, **kwargs: Any) -> None:
        """Raise request exception to verify external-failure mapping."""
        del kwargs
        raise requests.RequestException("network down")


class PartialFailureLoader(DummyLoader):
    """Loader test double returning a failed chapter summary."""

    def download(self, **kwargs: Any) -> DownloadSummary:
        """Return a deterministic summary with chapter failures."""
        del kwargs
        return DownloadSummary(
            downloaded=2,
            skipped_manifest=1,
            failed=2,
            failed_chapter_ids=(12, 13),
        )


def test_cli_uses_default_info_logging_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI configures INFO logging in default output mode."""
    observed_level: int | None = None

    def _setup_logging(*, level: int, stream: Any = None) -> None:
        nonlocal observed_level
        del stream
        observed_level = level

    monkeypatch.setattr(cli_main, "setup_logging", _setup_logging)
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "123"])

    assert result.exit_code == 0
    assert observed_level == 20


def test_cli_uses_warning_logging_level_in_quiet_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --quiet configures WARNING logging and suppresses intro text."""
    observed_level: int | None = None

    def _setup_logging(*, level: int, stream: Any = None) -> None:
        nonlocal observed_level
        del stream
        observed_level = level

    monkeypatch.setattr(cli_main, "setup_logging", _setup_logging)
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "123", "--quiet"])

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
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "123", "--verbose"])

    assert result.exit_code == 0
    assert observed_level == 10


def test_cli_uses_raw_exporter_when_raw_flag_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --raw selects RawExporter and forwards chapter IDs."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)
    monkeypatch.setattr(cli_main, "RawExporter", DummyRawExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "123", "--raw"])

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.download_args is not None
    assert DummyLoader.init_args["exporter_factory"].func is DummyRawExporter
    assert DummyLoader.init_args["output_format"] == "raw"
    assert DummyLoader.download_args["chapter_ids"] == {123}


def test_cli_uses_pdf_exporter_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --format pdf selects PDFExporter and forwards chapter IDs."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)
    monkeypatch.setattr(cli_main, "PDFExporter", DummyPdfExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55", "--format", "pdf"])

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.download_args is not None
    assert DummyLoader.init_args["exporter_factory"].func is DummyPdfExporter
    assert DummyLoader.init_args["output_format"] == "pdf"
    assert DummyLoader.download_args["chapter_ids"] == {55}


def test_cli_returns_error_when_download_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI returns a click error when loader download raises."""
    monkeypatch.setattr(cli_main, "MangaLoader", FailingLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55"])

    assert result.exit_code == INTERNAL_BUG
    assert "Download failed" in result.output


def test_cli_without_ids_prints_help_and_exits_cleanly() -> None:
    """Verify CLI prints usage text when no chapter/title input is provided."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_returns_subscription_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI exposes subscription requirement failures from downloader."""
    monkeypatch.setattr(cli_main, "MangaLoader", SubscriptionLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "A MAX subscription is required to download this chapter." in result.output


def test_cli_forwards_capture_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --capture-api forwards directory to loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "7", "--capture-api", "/tmp/captures"])

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.init_args["capture_api_dir"] == "/tmp/captures"


def test_cli_forwards_resume_and_manifest_reset_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify manifest behavior flags are forwarded to loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--chapter", "7", "--no-resume", "--manifest-reset"],
    )

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.init_args["resume"] is False
    assert DummyLoader.init_args["manifest_reset"] is True


def test_cli_verifies_capture_schema_and_exits_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify schema-verification mode runs and exits without invoking downloads."""
    monkeypatch.setattr(
        cli_main,
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
        cli_main,
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

    monkeypatch.setattr(cli_main, "verify_capture_schema", _raise_error)

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
        cli_main,
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


def test_cli_json_mode_returns_structured_success_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json returns machine-readable success payload for downloads."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["mode"] == "download"
    assert payload["exit_code"] == 0
    assert payload["targets"]["chapters"] == 1
    assert payload["summary"] == {
        "downloaded": 1,
        "skipped_manifest": 0,
        "failed": 0,
        "failed_chapter_ids": [],
    }


def test_cli_json_mode_returns_structured_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --json returns machine-readable error payload and deterministic exit code."""
    monkeypatch.setattr(cli_main, "MangaLoader", FailingLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter", "55"])

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
    monkeypatch.setattr(cli_main, "MangaLoader", RequestErrorLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download request failed: network down" in result.output


def test_cli_returns_external_failure_when_summary_has_failed_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed chapter summary maps to external failure exit code."""
    monkeypatch.setattr(cli_main, "MangaLoader", PartialFailureLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "55"])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "Download completed with 2 failed chapter(s)." in result.output


def test_cli_json_mode_includes_failed_summary_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify JSON error payload includes summary details for partial failures."""
    monkeypatch.setattr(cli_main, "MangaLoader", PartialFailureLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--json", "--chapter", "55"])

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
            "failed_chapter_ids": [12, 13],
        },
    }
