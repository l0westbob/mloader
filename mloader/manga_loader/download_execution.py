"""Concrete download execution service for planned MangaPlus downloads."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mloader.domain.manga import MangaPage, MangaViewer, TitleDetail
from mloader.domain.planning import (
    DownloadPlan,
    TitleDownloadPlan,
    title_detail_with_selected_chapters,
)
from mloader.domain.requests import CoverFormat, DownloadSummary, FilenameStyle
from mloader.errors import DownloadInterruptedError
from mloader.manga_loader.chapter_planning import ChapterMetadata
from mloader.manga_loader.download_services import DownloadServices
from mloader.manga_loader.manifest import TitleDownloadManifest, TitleDownloadManifestLike
from mloader.manga_loader.run_report import RunReport
from mloader.manga_loader.title_download import (
    ManifestFactory,
    TitleDownloadContext,
    TitleProcessingOptions,
)
from mloader.types import ExporterFactoryLike, ExporterLike, SessionLike

log = logging.getLogger(__name__)

PrepareDownloadPlan = Callable[
    [
        Collection[int] | None,
        Collection[int] | None,
        Collection[int] | None,
        int,
        int,
        bool,
    ],
    DownloadPlan,
]
LoadPages = Callable[[str | int], MangaViewer]
ClearTitleCaches = Callable[[int, Collection[int] | None], None]


@dataclass(frozen=True, slots=True)
class DownloadExecutionContext:
    """Runtime collaborators and options for one configured downloader."""

    destination: str
    output_format: Literal["raw", "cbz", "pdf"]
    exporter: ExporterFactoryLike
    session: SessionLike
    request_timeout: tuple[float, float]
    cover: bool
    meta: bool
    resume: bool
    manifest_reset: bool
    filename_style: FilenameStyle
    rename_existing_filenames: bool
    cover_format: CoverFormat
    services: DownloadServices
    prepare_download_plan: PrepareDownloadPlan
    load_pages: LoadPages
    clear_api_caches_for_run: Callable[[], None]
    clear_api_caches_for_title: ClearTitleCaches
    manifest_factory: ManifestFactory = TitleDownloadManifest


class DownloadExecutionService:
    """Execute title and chapter download plans with composed runtime services."""

    def __init__(self, context: DownloadExecutionContext) -> None:
        """Store configured collaborators for download execution."""
        self.context = context

    def download(
        self,
        *,
        title_ids: Collection[int] | None = None,
        chapter_numbers: Collection[int] | None = None,
        chapter_ids: Collection[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> DownloadSummary:
        """Start a download run using already validated filters."""
        report = RunReport()
        self._clear_api_caches_for_run()
        try:
            download_plan = self._prepare_download_plan(
                title_ids,
                chapter_numbers,
                chapter_ids,
                min_chapter,
                max_chapter,
                last_chapter,
            )
            self._download(download_plan, report)
        except KeyboardInterrupt as interrupted:
            raise DownloadInterruptedError(report.as_summary()) from interrupted
        finally:
            self._clear_api_caches_for_run()
        return report.as_summary()

    def _prepare_download_plan(
        self,
        title_ids: Collection[int] | None,
        chapter_numbers: Collection[int] | None,
        chapter_ids: Collection[int] | None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool,
    ) -> DownloadPlan:
        """Resolve title/chapter filters into a concrete domain download plan."""
        return self.context.prepare_download_plan(
            title_ids,
            chapter_numbers,
            chapter_ids,
            min_chapter,
            max_chapter,
            last_chapter,
        )

    def _download(
        self,
        download_plan: DownloadPlan,
        report: RunReport,
    ) -> None:
        """Iterate through normalized titles and process them one by one."""
        total_titles = download_plan.title_count
        for title_index, title_plan in enumerate(download_plan.title_plans, 1):
            self._process_title(title_index, total_titles, title_plan, report=report)

    def _process_title(
        self,
        title_index: int,
        total_titles: int,
        title_plan: TitleDownloadPlan,
        *,
        report: RunReport,
    ) -> None:
        """Download and export all selected chapters for one title."""
        services = self.context.services
        services.title_downloader.process_title(
            title_index=title_index,
            total_titles=total_titles,
            title_plan=title_plan,
            report=report,
            context=TitleDownloadContext(
                options=TitleProcessingOptions(
                    destination=self.context.destination,
                    cover=self.context.cover,
                    meta=self.context.meta,
                    resume=self.context.resume,
                    manifest_reset=self.context.manifest_reset,
                    output_format=self.context.output_format,
                    filename_style=self.context.filename_style,
                    rename_existing_filenames=self.context.rename_existing_filenames,
                ),
                manifest_tracker=services.manifest_tracker,
                manifest_factory=self.context.manifest_factory,
                dump_title_cover=self._dump_title_cover,
                title_detail_with_selected_chapters=title_detail_with_selected_chapters,
                extract_chapter_data=self._extract_chapter_data,
                dump_title_metadata=self._dump_title_metadata,
                get_existing_files=self._get_existing_files,
                filter_chapters_to_download=self._filter_chapters_to_download,
                exclude_manifest_completed_chapters=self._exclude_manifest_completed_chapters,
                process_chapter=self._process_chapter,
                clear_api_caches_for_title=self._clear_api_caches_for_title,
            ),
        )

    def _process_chapter(
        self,
        title_detail: TitleDetail,
        chapter_index: int,
        total_chapters: int,
        chapter_id: int,
        *,
        manifest: TitleDownloadManifestLike | None = None,
    ) -> None:
        """Download and export a single chapter."""
        viewer = self._load_pages(chapter_id)
        self.context.services.chapter_downloader.process_chapter(
            viewer=viewer,
            title=title_detail.title,
            chapter_index=chapter_index,
            total_chapters=total_chapters,
            chapter_id=chapter_id,
            output_format=self.context.output_format,
            manifest=manifest,
            exporter_factory=self.context.exporter,
            process_pages=self._process_chapter_pages,
            prepare_filename=self._prepare_filename,
        )

    def _load_pages(self, chapter_id: str | int) -> MangaViewer:
        """Load chapter viewer data through the configured gateway."""
        return self.context.load_pages(chapter_id)

    def _process_chapter_pages(
        self,
        pages: Collection[MangaPage],
        chapter_name: str,
        exporter: ExporterLike,
    ) -> None:
        """Download all chapter pages and pass them to the exporter."""
        page_image_service = self.context.services.page_image_service

        def download_url(url: str) -> bytes:
            return page_image_service.download_image(
                self.context.session,
                self.context.request_timeout,
                url,
            )

        def decrypt_url(url: str, encryption_hex: str) -> bytearray:
            return page_image_service.decrypt_image(
                self.context.session,
                self.context.request_timeout,
                url,
                encryption_hex,
            )

        self.context.services.page_export_service.export_pages(
            pages,
            chapter_name,
            exporter,
            fetch_page_image=lambda page: page_image_service.fetch_page_image(
                page,
                download_image=download_url,
                decrypt_image=decrypt_url,
            ),
        )

    def _dump_title_metadata(
        self,
        title_detail: TitleDetail,
        chapter_data: Mapping[int, ChapterMetadata],
        export_dir: str | Path,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        self.context.services.metadata_exporter.dump_title_metadata(
            title_detail,
            chapter_data,
            export_dir,
        )
        log.info(f"    Metadata for title '{title_detail.title.name}' exported")

    def _dump_title_cover(
        self,
        title_detail: TitleDetail,
        export_dir: str | Path,
    ) -> None:
        """Download and store one title cover image using the selected cover format."""
        page_image_service = self.context.services.page_image_service
        self.context.services.cover_exporter.dump_title_cover(
            title_detail,
            export_dir,
            cover_format=self.context.cover_format,
            download_image=lambda url: page_image_service.download_image(
                self.context.session,
                self.context.request_timeout,
                url,
            ),
        )

    def _extract_chapter_data(self, title_detail: TitleDetail) -> dict[int, ChapterMetadata]:
        """Collect chapter metadata from all chapter groups into one mapping."""
        return self.context.services.chapter_planner.extract_chapter_data(
            title_detail,
            self._prepare_filename,
        )

    def _get_existing_files(self, export_path: Path) -> list[str]:
        """Return existing chapter stems for single-file output formats."""
        return self.context.services.download_planner.get_existing_files(
            export_path,
            output_format=self.context.output_format,
        )

    def _filter_chapters_to_download(
        self,
        chapter_data: Mapping[int, ChapterMetadata],
        title_detail: TitleDetail,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
        filename_style: FilenameStyle,
    ) -> list[int]:
        """Return chapter IDs that are requested and not already exported."""
        return self.context.services.download_planner.filter_chapters_to_download(
            chapter_data,
            title_detail,
            existing_files,
            requested_chapter_ids,
            filename_style=filename_style,
        )

    def _exclude_manifest_completed_chapters(
        self,
        chapter_ids: Collection[int],
        manifest: TitleDownloadManifestLike,
    ) -> tuple[list[int], int]:
        """Exclude chapter IDs already marked completed in the title manifest."""
        return self.context.services.download_planner.exclude_manifest_completed_chapters(
            chapter_ids,
            manifest,
        )

    def _prepare_filename(self, text: str) -> str:
        """Fix common encoding glitches and sanitize text for filesystem use."""
        return self.context.services.filename_policy.prepare_filename(text)

    def _clear_api_caches_for_run(self) -> None:
        """Clear all cached gateway payloads for a download run."""
        self.context.clear_api_caches_for_run()

    def _clear_api_caches_for_title(
        self,
        title_id: int,
        chapter_ids: Collection[int] | None,
    ) -> None:
        """Clear title-scoped gateway cache entries after title processing."""
        self.context.clear_api_caches_for_title(title_id, chapter_ids)
