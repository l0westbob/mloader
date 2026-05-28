"""Unit tests for application download use cases."""

from __future__ import annotations

from typing import cast

import pytest

from mloader.application import downloads
from mloader.application.errors import DownloadInterrupted, ExternalDependencyError
from mloader.domain.manga import Chapter, Title
from mloader.domain.requests import (
    ApiOutputFormat,
    DownloadRequest,
    DownloadSummary,
)
from mloader.types import ExporterFactoryLike
from tests.cli_fakes import (
    APIResponseErrorDownloadRuntime,
    ApplicationRecordingDownloadRuntime,
    ApplicationInterruptedDownloadRuntime,
    NoneReturningDownloadRuntime,
    RecordingCbzExporter,
    RecordingExporter,
    RecordingPdfExporter,
    RecordingRawExporter,
    RequestFailingDownloadRuntime,
)


def _build_request(*, raw: bool = False, output_format: ApiOutputFormat = "cbz") -> DownloadRequest:
    """Build a deterministic download request for helper tests."""
    return DownloadRequest(
        out_dir="/tmp/downloads",
        raw=raw,
        output_format=("pdf" if output_format == "pdf" else "cbz"),
        capture_api_dir="/tmp/capture",
        quality="high",
        split=True,
        begin=1,
        end=5,
        last=True,
        chapter_title=True,
        chapter_subdir=False,
        meta=True,
        cover=False,
        cover_format="png",
        resume=True,
        manifest_reset=False,
        chapters=frozenset({10, 11}),
        chapter_ids=frozenset({1024959}),
        titles=frozenset({100001}),
    )


def test_resolve_exporter_prefers_raw_over_requested_format() -> None:
    """Verify raw mode always forces raw exporter selection."""
    request = _build_request(raw=True, output_format="pdf")

    exporter, effective_format = downloads.resolve_exporter(
        request,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert exporter is RecordingRawExporter
    assert effective_format == "raw"


def test_resolve_exporter_selects_pdf_when_requested() -> None:
    """Verify non-raw PDF requests resolve to PDF exporter."""
    request = _build_request(raw=False, output_format="pdf")

    exporter, effective_format = downloads.resolve_exporter(
        request,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert exporter is RecordingPdfExporter
    assert effective_format == "pdf"


def test_resolve_exporter_falls_back_to_cbz() -> None:
    """Verify non-raw non-PDF requests resolve to CBZ exporter."""
    request = _build_request(raw=False, output_format="cbz")

    exporter, effective_format = downloads.resolve_exporter(
        request,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert exporter is RecordingCbzExporter
    assert effective_format == "cbz"


def test_execute_download_wires_loader_and_download_targets() -> None:
    """Verify execute_download builds loader and forwards normalized targets."""
    ApplicationRecordingDownloadRuntime.init_args = None
    ApplicationRecordingDownloadRuntime.download_args = None
    RecordingExporter.calls = []
    request = _build_request(raw=False, output_format="pdf")

    summary = downloads.execute_download(
        request,
        loader_factory=ApplicationRecordingDownloadRuntime,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert ApplicationRecordingDownloadRuntime.init_args is not None
    assert ApplicationRecordingDownloadRuntime.download_args is not None
    assert ApplicationRecordingDownloadRuntime.init_args["output_format"] == "pdf"
    assert ApplicationRecordingDownloadRuntime.init_args["capture_api_dir"] == "/tmp/capture"
    assert ApplicationRecordingDownloadRuntime.init_args["resume"] is True
    assert ApplicationRecordingDownloadRuntime.init_args["manifest_reset"] is False
    assert ApplicationRecordingDownloadRuntime.init_args["cover"] is False
    assert ApplicationRecordingDownloadRuntime.init_args["cover_format"] == "png"
    assert ApplicationRecordingDownloadRuntime.init_args["quality"] == "high"
    title = Title(
        title_id=1,
        name="Title",
        author="Author",
        portrait_image_url="",
        landscape_image_url="",
        language=0,
    )
    chapter = Chapter(title_id=1, chapter_id=1, name="#1", sub_title="One", thumbnail_url="")
    next_chapter = Chapter(title_id=1, chapter_id=2, name="#2", sub_title="Two", thumbnail_url="")
    exporter_factory = cast(
        ExporterFactoryLike, ApplicationRecordingDownloadRuntime.init_args["exporter_factory"]
    )
    exporter = exporter_factory(
        title=title,
        chapter=chapter,
        next_chapter=next_chapter,
    )
    assert isinstance(exporter, RecordingExporter)
    assert RecordingExporter.calls == [
        {
            "destination": "/tmp/downloads",
            "title": title,
            "chapter": chapter,
            "next_chapter": next_chapter,
            "add_chapter_title": True,
            "add_chapter_subdir": False,
        }
    ]
    assert ApplicationRecordingDownloadRuntime.download_args["title_ids"] == frozenset({100001})
    assert ApplicationRecordingDownloadRuntime.download_args["chapter_numbers"] == frozenset(
        {10, 11}
    )
    assert ApplicationRecordingDownloadRuntime.download_args["chapter_ids"] == frozenset({1024959})
    assert ApplicationRecordingDownloadRuntime.download_args["min_chapter"] == 1
    assert ApplicationRecordingDownloadRuntime.download_args["max_chapter"] == 5
    assert ApplicationRecordingDownloadRuntime.download_args["last_chapter"] is True
    assert summary == DownloadSummary(
        downloaded=2,
        skipped_manifest=1,
        failed=0,
        failed_chapter_ids=(),
    )


def test_execute_download_omits_empty_target_filters() -> None:
    """Verify execute_download forwards None when target sets are empty."""
    ApplicationRecordingDownloadRuntime.download_args = None
    request = DownloadRequest(
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
        chapters=frozenset(),
        chapter_ids=frozenset(),
        titles=frozenset(),
    )

    downloads.execute_download(
        request,
        loader_factory=ApplicationRecordingDownloadRuntime,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert ApplicationRecordingDownloadRuntime.download_args is not None
    assert ApplicationRecordingDownloadRuntime.download_args["title_ids"] is None
    assert ApplicationRecordingDownloadRuntime.download_args["chapter_numbers"] is None
    assert ApplicationRecordingDownloadRuntime.download_args["chapter_ids"] is None


def test_execute_download_wraps_request_errors_as_external_dependency_failure() -> None:
    """Verify request-layer failures are normalized into application external errors."""
    request = _build_request(raw=False, output_format="cbz")

    with pytest.raises(ExternalDependencyError, match="Download request failed: network"):
        downloads.execute_download(
            request,
            loader_factory=RequestFailingDownloadRuntime,
            raw_exporter=RecordingRawExporter,
            pdf_exporter=RecordingPdfExporter,
            cbz_exporter=RecordingCbzExporter,
        )


def test_execute_download_wraps_api_payload_errors_as_external_dependency_failure() -> None:
    """Verify invalid API payload failures map to application external errors."""
    request = _build_request(raw=False, output_format="cbz")

    with pytest.raises(
        ExternalDependencyError,
        match="Download request failed: MangaPlus API returned no manga_viewer payload.",
    ):
        downloads.execute_download(
            request,
            loader_factory=APIResponseErrorDownloadRuntime,
            raw_exporter=RecordingRawExporter,
            pdf_exporter=RecordingPdfExporter,
            cbz_exporter=RecordingCbzExporter,
        )


def test_execute_download_wraps_interrupt_as_application_interrupt() -> None:
    """Verify interrupted downloader runs are normalized with partial summary."""
    request = _build_request(raw=False, output_format="cbz")

    with pytest.raises(DownloadInterrupted) as interrupted:
        downloads.execute_download(
            request,
            loader_factory=ApplicationInterruptedDownloadRuntime,
            raw_exporter=RecordingRawExporter,
            pdf_exporter=RecordingPdfExporter,
            cbz_exporter=RecordingCbzExporter,
        )

    assert interrupted.value.summary == DownloadSummary(
        downloaded=3,
        skipped_manifest=1,
        failed=1,
        failed_chapter_ids=(77,),
    )


def test_execute_download_falls_back_when_loader_returns_non_summary() -> None:
    """Verify execute_download normalizes non-summary loader returns."""
    request = _build_request(raw=False, output_format="cbz")

    summary = downloads.execute_download(
        request,
        loader_factory=NoneReturningDownloadRuntime,
        raw_exporter=RecordingRawExporter,
        pdf_exporter=RecordingPdfExporter,
        cbz_exporter=RecordingCbzExporter,
    )

    assert summary == DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def test_to_chapter_id_debug_map_includes_expected_keys() -> None:
    """Verify debug-map helper exposes stable low-cardinality fields."""
    request = _build_request(raw=False, output_format="cbz")
    debug_map = downloads.to_chapter_id_debug_map(request)

    assert debug_map == {
        "target_titles": 1,
        "target_chapters": 2,
        "target_chapter_ids": 1,
        "begin": 1,
        "end": 5,
        "raw": False,
        "format": "cbz",
        "cover": False,
        "cover_format": "png",
        "resume": True,
        "manifest_reset": False,
        "capture_api": True,
        "run_report": False,
    }
