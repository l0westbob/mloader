"""Unit tests for application-layer workflow helpers."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
import requests

from mloader.application import workflows
from mloader.domain.requests import DownloadRequest, DownloadSummary
from mloader.manga_loader.downloader import DownloadInterruptedError


class DummyRawExporter:
    """Marker exporter for raw output selection tests."""


class DummyPdfExporter:
    """Marker exporter for PDF output selection tests."""


class DummyCbzExporter:
    """Marker exporter for CBZ output selection tests."""


class DummyLoader:
    """Loader test double for application execute_download tests."""

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
        """Capture initializer values for assertions."""
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
        """Capture download invocation payload."""
        type(self).download_args = kwargs
        return DownloadSummary(
            downloaded=2,
            skipped_manifest=1,
            failed=0,
            failed_chapter_ids=(),
        )


class RequestFailingLoader(DummyLoader):
    """Loader test double that fails with a request-layer exception."""

    def download(self, **kwargs: Any) -> None:
        """Raise request exception for external-dependency mapping tests."""
        del kwargs
        raise requests.RequestException("network")


class InterruptingLoader(DummyLoader):
    """Loader test double that raises interrupt wrapper with partial summary."""

    def download(self, **kwargs: Any) -> None:
        """Raise interrupted-download error to verify workflow mapping behavior."""
        del kwargs
        raise DownloadInterruptedError(
            DownloadSummary(
                downloaded=3,
                skipped_manifest=1,
                failed=1,
                failed_chapter_ids=(77,),
            )
        )


class NoneReturningLoader:
    """Loader test double returning a non-summary sentinel value."""

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
        """Accept standard loader constructor arguments and ignore payload."""
        del (
            exporter_factory,
            quality,
            split,
            meta,
            destination,
            output_format,
            capture_api_dir,
            resume,
            manifest_reset,
        )

    def download(self, **kwargs: Any) -> None:
        """Return None to exercise workflow summary fallback branch."""
        del kwargs
        return None


def _build_request(*, raw: bool = False, output_format: str = "cbz") -> DownloadRequest:
    """Build a deterministic download request for workflow helper tests."""
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
        resume=True,
        manifest_reset=False,
        chapters=frozenset({10, 11}),
        titles=frozenset({100001}),
    )


def test_verify_discovery_flags_rejects_list_only_without_all() -> None:
    """Verify list-only validation fails when all-mode is disabled."""
    message = workflows.verify_discovery_flags(
        download_all_titles=False,
        list_only=True,
        languages=(),
    )

    assert message == "--list-only requires --all."


def test_verify_discovery_flags_rejects_language_without_all() -> None:
    """Verify language validation fails when all-mode is disabled."""
    message = workflows.verify_discovery_flags(
        download_all_titles=False,
        list_only=False,
        languages=("english",),
    )

    assert message == "--language requires --all."


def test_verify_discovery_flags_accepts_all_mode() -> None:
    """Verify discovery flag validation allows all-mode combinations."""
    message = workflows.verify_discovery_flags(
        download_all_titles=True,
        list_only=True,
        languages=("english",),
    )

    assert message is None


def test_resolve_exporter_prefers_raw_over_requested_format() -> None:
    """Verify raw mode always forces raw exporter selection."""
    request = _build_request(raw=True, output_format="pdf")

    exporter, effective_format = workflows.resolve_exporter(
        request,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert exporter is DummyRawExporter
    assert effective_format == "raw"


def test_resolve_exporter_selects_pdf_when_requested() -> None:
    """Verify non-raw PDF requests resolve to PDF exporter."""
    request = _build_request(raw=False, output_format="pdf")

    exporter, effective_format = workflows.resolve_exporter(
        request,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert exporter is DummyPdfExporter
    assert effective_format == "pdf"


def test_resolve_exporter_falls_back_to_cbz() -> None:
    """Verify non-raw non-PDF requests resolve to CBZ exporter."""
    request = _build_request(raw=False, output_format="cbz")

    exporter, effective_format = workflows.resolve_exporter(
        request,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert exporter is DummyCbzExporter
    assert effective_format == "cbz"


def test_execute_download_wires_loader_and_download_targets() -> None:
    """Verify execute_download builds loader and forwards normalized targets."""
    DummyLoader.init_args = None
    DummyLoader.download_args = None
    request = _build_request(raw=False, output_format="pdf")

    summary = workflows.execute_download(
        request,
        loader_factory=DummyLoader,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert DummyLoader.init_args is not None
    assert DummyLoader.download_args is not None
    assert DummyLoader.init_args["output_format"] == "pdf"
    assert DummyLoader.init_args["capture_api_dir"] == "/tmp/capture"
    assert DummyLoader.init_args["resume"] is True
    assert DummyLoader.init_args["manifest_reset"] is False
    assert DummyLoader.init_args["quality"] == "high"
    assert DummyLoader.download_args["title_ids"] == frozenset({100001})
    assert DummyLoader.download_args["chapter_ids"] == frozenset({10, 11})
    assert DummyLoader.download_args["min_chapter"] == 1
    assert DummyLoader.download_args["max_chapter"] == 5
    assert DummyLoader.download_args["last_chapter"] is True
    assert summary == DownloadSummary(
        downloaded=2,
        skipped_manifest=1,
        failed=0,
        failed_chapter_ids=(),
    )


def test_execute_download_omits_empty_target_filters() -> None:
    """Verify execute_download forwards None when both target sets are empty."""
    DummyLoader.download_args = None
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
        resume=True,
        manifest_reset=False,
        chapters=frozenset(),
        titles=frozenset(),
    )

    workflows.execute_download(
        request,
        loader_factory=DummyLoader,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert DummyLoader.download_args is not None
    assert DummyLoader.download_args["title_ids"] is None
    assert DummyLoader.download_args["chapter_ids"] is None


def test_execute_download_wraps_request_errors_as_external_dependency_failure() -> None:
    """Verify request-layer failures are normalized into workflow external errors."""
    request = _build_request(raw=False, output_format="cbz")

    with pytest.raises(workflows.ExternalDependencyError, match="Download request failed: network"):
        workflows.execute_download(
            request,
            loader_factory=RequestFailingLoader,
            raw_exporter=DummyRawExporter,
            pdf_exporter=DummyPdfExporter,
            cbz_exporter=DummyCbzExporter,
        )


def test_execute_download_wraps_interrupt_as_workflow_interrupt() -> None:
    """Verify interrupted downloader runs are normalized with partial summary."""
    request = _build_request(raw=False, output_format="cbz")

    with pytest.raises(workflows.DownloadInterrupted) as interrupted:
        workflows.execute_download(
            request,
            loader_factory=InterruptingLoader,
            raw_exporter=DummyRawExporter,
            pdf_exporter=DummyPdfExporter,
            cbz_exporter=DummyCbzExporter,
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

    summary = workflows.execute_download(
        request,
        loader_factory=NoneReturningLoader,
        raw_exporter=DummyRawExporter,
        pdf_exporter=DummyPdfExporter,
        cbz_exporter=DummyCbzExporter,
    )

    assert summary == DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def test_format_helpers_return_expected_cli_strings() -> None:
    """Verify helper formatters produce deterministic human-facing output."""
    assert workflows.summarize_discovery([1, 2, 3]) == "Discovered 3 title ID(s)."
    assert workflows.format_discovered_ids([100001, 100002]) == "100001 100002"


def test_build_request_helpers_create_immutable_domain_models() -> None:
    """Verify request builder helpers normalize and freeze collection inputs."""
    download_request = workflows.build_download_request(
        out_dir="/tmp/downloads",
        raw=False,
        output_format="pdf",
        capture_api_dir=None,
        quality="high",
        split=False,
        begin=0,
        end=None,
        last=False,
        chapter_title=False,
        chapter_subdir=False,
        meta=False,
        resume=False,
        manifest_reset=True,
        chapters={5, 5},
        titles={100010, 100010},
    )
    discovery_request = workflows.build_discovery_request(
        pages=("https://example.com",),
        title_index_endpoint="https://api.example/allV2",
        id_length=6,
        languages=("english",),
        browser_fallback=True,
    )

    assert download_request.output_format == "pdf"
    assert download_request.chapters == frozenset({5})
    assert download_request.titles == frozenset({100010})
    assert download_request.resume is False
    assert download_request.manifest_reset is True
    assert discovery_request.title_index_endpoint == "https://api.example/allV2"
    assert discovery_request.languages == ("english",)


def test_to_chapter_id_debug_map_includes_expected_keys() -> None:
    """Verify debug-map helper exposes stable low-cardinality fields."""
    request = _build_request(raw=False, output_format="cbz")
    debug_map = workflows.to_chapter_id_debug_map(request)

    assert debug_map == {
        "target_titles": 1,
        "target_chapters": 2,
        "begin": 1,
        "end": 5,
        "raw": False,
        "format": "cbz",
        "resume": True,
        "manifest_reset": False,
    }
