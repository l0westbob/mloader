"""Explicitly composed runtime services used by downloader orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from mloader.manga_loader.chapter_download import ChapterDownloader
from mloader.manga_loader.chapter_planning import (
    ChapterPlanner,
    DownloadPlanner,
)
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.manga_loader.manifest_tracking import ManifestTracker
from mloader.manga_loader.page_export import PageExportService, PageImageService
from mloader.manga_loader.title_assets import (
    CoverExporter,
    MetadataExporter,
    MetadataWriter,
)
from mloader.manga_loader.title_download import TitleDownloader


@dataclass(frozen=True, slots=True)
class DownloadServices:
    """Container for runtime collaborators used by download orchestration."""

    chapter_downloader: type[ChapterDownloader]
    chapter_planner: type[ChapterPlanner]
    metadata_writer: type[MetadataWriter]
    metadata_exporter: type[MetadataExporter]
    cover_exporter: type[CoverExporter]
    download_planner: type[DownloadPlanner]
    filename_policy: type[FilenamePolicy]
    manifest_tracker: type[ManifestTracker]
    page_export_service: type[PageExportService]
    page_image_service: type[PageImageService]
    title_downloader: type[TitleDownloader]

    @staticmethod
    def defaults() -> "DownloadServices":
        """Return default concrete service bindings."""
        return DownloadServices(
            chapter_downloader=ChapterDownloader,
            chapter_planner=ChapterPlanner,
            metadata_writer=MetadataWriter,
            metadata_exporter=MetadataExporter,
            cover_exporter=CoverExporter,
            download_planner=DownloadPlanner,
            filename_policy=FilenamePolicy,
            manifest_tracker=ManifestTracker,
            page_export_service=PageExportService,
            page_image_service=PageImageService,
            title_downloader=TitleDownloader,
        )
