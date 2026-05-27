"""Application use cases for download execution."""

from __future__ import annotations

from collections.abc import Mapping

import requests

from mloader.application.errors import DownloadInterrupted, ExternalDependencyError
from mloader.application.ports import DownloadRuntimeFactory, ExporterClass
from mloader.domain.requests import DownloadRequest, DownloadSummary, EffectiveOutputFormat
from mloader.errors import APIResponseError
from mloader.errors import DownloadInterruptedError
from mloader.types import ChapterLike, ExporterFactoryLike, ExporterLike, TitleLike


def resolve_exporter(
    request: DownloadRequest,
    *,
    raw_exporter: ExporterClass,
    pdf_exporter: ExporterClass,
    cbz_exporter: ExporterClass,
) -> tuple[ExporterClass, EffectiveOutputFormat]:
    """Resolve exporter class and effective output format from request options."""
    if request.raw:
        return raw_exporter, "raw"
    if request.output_format == "pdf":
        return pdf_exporter, "pdf"
    return cbz_exporter, "cbz"


def build_exporter_factory(
    request: DownloadRequest,
    exporter_class: ExporterClass,
) -> ExporterFactoryLike:
    """Build the per-chapter exporter factory passed into the download runtime."""

    def create_exporter(
        *,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None = None,
    ) -> ExporterLike:
        return exporter_class(
            destination=request.out_dir,
            title=title,
            chapter=chapter,
            next_chapter=next_chapter,
            add_chapter_title=request.chapter_title,
            add_chapter_subdir=request.chapter_subdir,
        )

    return create_exporter


def execute_download(
    request: DownloadRequest,
    *,
    loader_factory: DownloadRuntimeFactory,
    raw_exporter: ExporterClass,
    pdf_exporter: ExporterClass,
    cbz_exporter: ExporterClass,
) -> DownloadSummary:
    """Execute the configured download request via the provided factories."""
    exporter_class, effective_output_format = resolve_exporter(
        request,
        raw_exporter=raw_exporter,
        pdf_exporter=pdf_exporter,
        cbz_exporter=cbz_exporter,
    )
    exporter_factory = build_exporter_factory(request, exporter_class)

    loader = loader_factory(
        exporter_factory,
        request.quality,
        request.split,
        request.meta,
        request.cover,
        destination=request.out_dir,
        output_format=effective_output_format,
        capture_api_dir=request.capture_api_dir,
        resume=request.resume,
        manifest_reset=request.manifest_reset,
        cover_format=request.cover_format,
    )
    try:
        summary = loader.download(
            title_ids=request.titles or None,
            chapter_numbers=request.chapters or None,
            chapter_ids=request.chapter_ids or None,
            min_chapter=request.begin,
            max_chapter=request.max_chapter,
            last_chapter=request.last,
        )
    except DownloadInterruptedError as exc:
        raise DownloadInterrupted(exc.summary) from exc
    except (requests.RequestException, APIResponseError) as exc:
        raise ExternalDependencyError(f"Download request failed: {exc}") from exc

    if isinstance(summary, DownloadSummary):
        return summary
    return DownloadSummary(
        downloaded=0,
        skipped_manifest=0,
        failed=0,
        failed_chapter_ids=(),
    )


def to_chapter_id_debug_map(
    request: DownloadRequest,
) -> Mapping[str, int | bool | str | None]:
    """Return minimal structured fields useful for debug logging."""
    return {
        "target_titles": len(request.titles),
        "target_chapters": len(request.chapters),
        "target_chapter_ids": len(request.chapter_ids),
        "begin": request.begin,
        "end": request.end,
        "raw": request.raw,
        "format": request.output_format,
        "cover": request.cover,
        "cover_format": request.cover_format,
        "resume": request.resume,
        "manifest_reset": request.manifest_reset,
        "capture_api": request.capture_api_dir is not None,
        "run_report": request.run_report_path is not None,
    }
