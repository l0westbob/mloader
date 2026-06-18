"""Chapter planning and filesystem filtering services."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from mloader.domain.manga import Chapter, TitleDetail
from mloader.domain.requests import FilenameStyle
from mloader.manga_loader.filename_policy import FilenamePolicy
from mloader.manga_loader.manifest import TitleDownloadManifestLike
from mloader.types import ChapterLike

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChapterMetadata:
    """Normalized chapter metadata used during planning."""

    thumbnail_url: str
    chapter_id: int
    sub_title: str


class ChapterPlanner:
    """Compute chapter extraction and download planning decisions."""

    @staticmethod
    def extract_chapter_data(
        title_detail: TitleDetail,
        prepare_filename: Callable[[str], str],
    ) -> dict[int, ChapterMetadata]:
        """Collect chapter metadata keyed by chapter ID from all chapter groups."""
        chapter_data: dict[int, ChapterMetadata] = {}
        for chapter in title_detail.chapters:
            chapter_data[chapter.chapter_id] = ChapterMetadata(
                thumbnail_url=chapter.thumbnail_url,
                chapter_id=chapter.chapter_id,
                sub_title=prepare_filename(chapter.sub_title),
            )
        return chapter_data

    @staticmethod
    def find_chapter_by_id(title_detail: TitleDetail, chapter_id: int) -> Chapter | None:
        """Find and return a chapter object by ``chapter_id`` if available."""
        return title_detail.find_chapter(chapter_id)

    @staticmethod
    def build_expected_filename(
        title_name: str,
        chapter_obj: ChapterLike,
        sub_title: str,
        title_language: int = 0,
        *,
        filename_style: FilenameStyle = "legacy",
    ) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        return FilenamePolicy.build_expected_filename(
            title_name,
            chapter_obj,
            sub_title,
            title_language,
            filename_style=filename_style,
        )

    @staticmethod
    def build_expected_filename_with_style(
        title_name: str,
        chapter_obj: ChapterLike,
        sub_title: str,
        title_language: int,
        filename_style: FilenameStyle,
    ) -> str:
        """Build normalized chapter stems for a requested filename style."""
        return FilenamePolicy.build_expected_filename(
            title_name,
            chapter_obj,
            sub_title,
            title_language,
            filename_style=filename_style,
        )

    @staticmethod
    def filter_chapters_to_download(
        chapter_data: Mapping[int, ChapterMetadata],
        title_detail: TitleDetail,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
        filename_style: FilenameStyle = "legacy",
    ) -> list[int]:
        """Return requested chapter IDs that do not yet exist on disk."""
        chapters_to_download: list[int] = []
        for _chapter_id, metadata in chapter_data.items():
            chapter_obj = ChapterPlanner.find_chapter_by_id(title_detail, metadata.chapter_id)
            if chapter_obj is None:
                # Keep warning for visibility when upstream chapter metadata is inconsistent.
                log.warning("Chapter id %s not found in title dump; skipping", metadata.chapter_id)
                continue
            expected_filename = ChapterPlanner.build_expected_filename(
                FilenamePolicy.title_directory_name(title_detail.title.name),
                chapter_obj,
                metadata.sub_title,
                filename_style=filename_style,
                title_language=title_detail.title.language,
            )
            if expected_filename not in existing_files:
                chapters_to_download.append(metadata.chapter_id)
        return [
            chapter_id for chapter_id in chapters_to_download if chapter_id in requested_chapter_ids
        ]


class DownloadPlanner:
    """Compute filesystem and manifest decisions for title downloads."""

    @staticmethod
    def chapter_output_extension(output_format: str) -> str | None:
        """Return chapter-level output extension, or ``None`` for raw image mode."""
        if output_format in {"pdf", "cbz"}:
            return output_format
        return None

    @staticmethod
    def get_existing_files(export_path: Path, *, output_format: str) -> list[str]:
        """Return existing chapter stems for single-file output formats."""
        if not export_path.exists():
            return []

        extension = DownloadPlanner.chapter_output_extension(output_format)
        if extension is None:
            return []

        existing_files = [file.stem for file in export_path.glob(f"*.{extension}")]
        log.info(f"    Found {len(existing_files)} existing chapter files in '{export_path}'.")
        log.debug(f"    Existing files: {existing_files}")
        return existing_files

    @staticmethod
    def filter_chapters_to_download(
        chapter_data: Mapping[int, ChapterMetadata],
        title_detail: TitleDetail,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
        filename_style: FilenameStyle = "legacy",
    ) -> list[int]:
        """Return chapter IDs that are requested and not already exported."""
        return ChapterPlanner.filter_chapters_to_download(
            chapter_data,
            title_detail,
            existing_files,
            requested_chapter_ids,
            filename_style=filename_style,
        )

    @staticmethod
    def exclude_manifest_completed_chapters(
        chapter_ids: Collection[int],
        manifest: TitleDownloadManifestLike,
    ) -> tuple[list[int], int]:
        """Exclude chapter IDs already marked completed in the title manifest."""
        pending = [
            chapter_id for chapter_id in chapter_ids if not manifest.is_completed(chapter_id)
        ]
        skipped_count = len(chapter_ids) - len(pending)
        if skipped_count:
            log.info(
                f"    Skipping {skipped_count} chapter(s) already marked completed in manifest."
            )
        return pending, skipped_count
