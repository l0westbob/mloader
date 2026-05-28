"""Tests for CLI download-mode behavior."""

from __future__ import annotations

from typing import cast

import pytest
from click.testing import CliRunner

from mloader.cli import main as cli_main
from mloader.cli.exit_codes import EXTERNAL_FAILURE, INTERNAL_BUG
from mloader.types import ExporterFactoryLike
from tests.cli_fakes import (
    FakeChapter,
    FakeTitle,
    RecordingDownloadRuntime,
    RecordingPdfExporter,
    RecordingRawExporter,
    RuntimeFailingDownloadRuntime,
    SubscriptionRequiredDownloadRuntime,
)

CHAPTER_ID = "1024959"


def test_cli_uses_raw_exporter_when_raw_flag_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --raw selects RawExporter and forwards chapter IDs."""
    RecordingRawExporter.init_args = None
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)
    monkeypatch.setattr(cli_main, "RawExporter", RecordingRawExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--raw"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.download_args is not None
    exporter_factory = cast(
        ExporterFactoryLike, RecordingDownloadRuntime.init_args["exporter_factory"]
    )
    exporter = exporter_factory(title=FakeTitle(), chapter=FakeChapter())
    assert isinstance(exporter, RecordingRawExporter)
    assert RecordingRawExporter.init_args is not None
    assert RecordingRawExporter.init_args["destination"] == "mloader_downloads"
    assert RecordingDownloadRuntime.init_args["output_format"] == "raw"
    assert RecordingDownloadRuntime.download_args["chapter_ids"] == {int(CHAPTER_ID)}


def test_cli_uses_pdf_exporter_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --format pdf selects PDFExporter and forwards chapter IDs."""
    RecordingPdfExporter.init_args = None
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)
    monkeypatch.setattr(cli_main, "PDFExporter", RecordingPdfExporter)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--format", "pdf"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.download_args is not None
    exporter_factory = cast(
        ExporterFactoryLike, RecordingDownloadRuntime.init_args["exporter_factory"]
    )
    exporter = exporter_factory(title=FakeTitle(), chapter=FakeChapter())
    assert isinstance(exporter, RecordingPdfExporter)
    assert RecordingPdfExporter.init_args is not None
    assert RecordingPdfExporter.init_args["destination"] == "mloader_downloads"
    assert RecordingDownloadRuntime.init_args["output_format"] == "pdf"
    assert RecordingDownloadRuntime.download_args["chapter_ids"] == {int(CHAPTER_ID)}


def test_cli_returns_error_when_download_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI returns a click error when loader download raises."""
    monkeypatch.setattr(cli_main, "MangaLoader", RuntimeFailingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == INTERNAL_BUG
    assert "Download failed" in result.output


def test_cli_returns_subscription_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI exposes subscription requirement failures from downloader."""
    monkeypatch.setattr(cli_main, "MangaLoader", SubscriptionRequiredDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == EXTERNAL_FAILURE
    assert "A MAX subscription is required to download this chapter." in result.output


def test_cli_forwards_capture_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --capture-api forwards directory to loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main, ["--chapter-id", CHAPTER_ID, "--capture-api", "/tmp/captures"]
    )

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["capture_api_dir"] == "/tmp/captures"


def test_cli_forwards_cover_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --cover enables title-cover download mode in loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--cover"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["cover"] is True
    assert RecordingDownloadRuntime.init_args["cover_format"] == "png"


def test_cli_forwards_cover_format_when_cover_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --cover-format selects title-cover image format."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--chapter-id", CHAPTER_ID, "--cover", "--cover-format", "webp"],
    )

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["cover"] is True
    assert RecordingDownloadRuntime.init_args["cover_format"] == "webp"


def test_cli_cover_format_implies_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify explicit --cover-format enables title-cover download mode."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--cover-format", "jpg"])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["cover"] is True
    assert RecordingDownloadRuntime.init_args["cover_format"] == "jpg"


def test_cli_rejects_invalid_cover_format() -> None:
    """Verify unsupported cover formats fail during CLI validation."""
    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID, "--cover-format", "bmp"])

    assert result.exit_code == 2
    assert "Invalid value for '--cover-format'" in result.output


def test_cli_cover_defaults_to_disabled_with_png_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cover download remains disabled by default."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["--chapter-id", CHAPTER_ID])

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["cover"] is False
    assert RecordingDownloadRuntime.init_args["cover_format"] == "png"


def test_cli_forwards_resume_and_manifest_reset_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify manifest behavior flags are forwarded to loader initialization."""
    monkeypatch.setattr(cli_main, "MangaLoader", RecordingDownloadRuntime)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["--chapter-id", CHAPTER_ID, "--no-resume", "--manifest-reset"],
    )

    assert result.exit_code == 0
    assert RecordingDownloadRuntime.init_args is not None
    assert RecordingDownloadRuntime.init_args["resume"] is False
    assert RecordingDownloadRuntime.init_args["manifest_reset"] is True
