"""Explicitly composed runtime services used by downloader orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from mloader.manga_loader.services import (
    ChapterPlanner,
    MetadataWriter,
    PageExportService,
    PageImageService,
)


@dataclass(frozen=True, slots=True)
class DownloadServices:
    """Container for runtime collaborators used by ``DownloadMixin``."""

    chapter_planner: type[ChapterPlanner]
    metadata_writer: type[MetadataWriter]
    page_export_service: type[PageExportService]
    page_image_service: type[PageImageService]

    @staticmethod
    def defaults() -> "DownloadServices":
        """Return default concrete service bindings."""
        return DownloadServices(
            chapter_planner=ChapterPlanner,
            metadata_writer=MetadataWriter,
            page_export_service=PageExportService,
            page_image_service=PageImageService,
        )
