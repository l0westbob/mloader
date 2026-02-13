"""Tests for CLI command orchestration."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from click.testing import CliRunner

from mloader.cli import main as cli_main
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
        }

    def download(self, **kwargs: Any) -> None:
        """Record download call keyword arguments for assertions."""
        type(self).download_args = kwargs


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

    assert result.exit_code != 0
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

    assert result.exit_code != 0
    assert "A MAX subscription is required to download this chapter." in result.output


def test_cli_forwards_capture_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --capture-api forwards directory to loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", DummyLoader)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter", "7", "--capture-api", "/tmp/captures"])

    assert result.exit_code == 0
    assert DummyLoader.init_args is not None
    assert DummyLoader.init_args["capture_api_dir"] == "/tmp/captures"


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
    result = runner.invoke(cli_main.main, ["--verify-capture-schema", "capture"])

    assert result.exit_code == 0
    assert "Verified 3 capture payload(s) in capture" in result.output


def test_cli_verify_capture_schema_returns_click_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify verification failures are exposed as click exceptions."""

    def _raise_error(_path: str) -> None:
        raise CaptureVerificationError("schema drift")

    monkeypatch.setattr(cli_main, "verify_capture_schema", _raise_error)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--verify-capture-schema", "capture"])

    assert result.exit_code != 0
    assert "schema drift" in result.output
