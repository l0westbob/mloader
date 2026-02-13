"""Download orchestration logic for titles, chapters, and page assets."""

from __future__ import annotations

import logging
from itertools import count
from pathlib import Path
from typing import Collection, Literal, Mapping

import click

from mloader.constants import PageType
from mloader.errors import SubscriptionRequiredError
from mloader.manga_loader.services import ChapterMetadata, ChapterPlanner, MetadataWriter
from mloader.types import (
    ChapterLike,
    ExporterFactoryLike,
    ExporterLike,
    MangaPageLike,
    MangaViewerLike,
    SessionLike,
    TitleDumpLike,
    TitleLike,
)
from mloader.utils import escape_path

log = logging.getLogger(__name__)


class DownloadMixin:
    """Provide download and export orchestration for manga content."""

    meta: bool
    destination: str
    output_format: Literal["raw", "cbz", "pdf"]
    exporter: ExporterFactoryLike
    session: SessionLike
    request_timeout: tuple[float, float]

    def _prepare_normalized_manga_list(
        self,
        title_ids: Collection[int] | None,
        chapter_ids: Collection[int] | None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool,
    ) -> Mapping[int, Collection[int]]:
        """Normalize title/chapter filters into a concrete download mapping."""
        raise NotImplementedError

    def _get_title_details(self, title_id: str | int) -> TitleDumpLike:
        """Load title details for ``title_id``."""
        raise NotImplementedError

    def _load_pages(self, chapter_id: str | int) -> MangaViewerLike:
        """Load chapter viewer payload for ``chapter_id``."""
        raise NotImplementedError

    def download(
        self,
        *,
        title_ids: Collection[int] | None = None,
        chapter_ids: Collection[int] | None = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> None:
        """Start a download run using already validated filters."""
        normalized_mapping = self._prepare_normalized_manga_list(
            title_ids,
            chapter_ids,
            min_chapter,
            max_chapter,
            last_chapter,
        )
        self._download(normalized_mapping)

    def _download(self, manga_mapping: Mapping[int, Collection[int]]) -> None:
        """Iterate through normalized titles and process them one by one."""
        total_titles = len(manga_mapping)
        for title_index, (title_id, chapter_ids) in enumerate(manga_mapping.items(), 1):
            self._process_title(title_index, total_titles, title_id, chapter_ids)

    def _process_title(
        self,
        title_index: int,
        total_titles: int,
        title_id: int,
        chapter_ids: Collection[int],
    ) -> None:
        """Download and export all selected chapters for one title."""
        title_dump = self._get_title_details(title_id)
        title_detail = title_dump.title

        log.info(f"{title_index}/{total_titles}) Manga: {title_detail.name}")
        log.info(f"    Author: {title_detail.author}")

        export_path = Path(self.destination) / escape_path(title_detail.name).title()
        chapter_data = self._extract_chapter_data(title_dump)

        if self.meta:
            self._dump_title_metadata(title_dump, chapter_data, export_path)

        existing_files = self._get_existing_files(export_path)
        chapters_to_download = self._filter_chapters_to_download(
            chapter_data,
            title_dump,
            title_detail,
            existing_files,
            chapter_ids,
        )

        if not chapters_to_download:
            log.info(f"    All chapters for '{title_detail.name}' are already downloaded.")
            return

        total_chapters = len(chapters_to_download)
        log.info(f"    {total_chapters} chapter(s) to download for '{title_detail.name}'.")
        for chapter_index, chapter_id in enumerate(sorted(chapters_to_download), 1):
            self._process_chapter(title_detail, chapter_index, total_chapters, chapter_id)

    def _process_chapter(
        self,
        title_detail: TitleLike,
        chapter_index: int,
        total_chapters: int,
        chapter_id: int,
    ) -> None:
        """Download and export a single chapter."""
        viewer = self._load_pages(chapter_id)
        if not self._has_last_page(viewer):
            raise SubscriptionRequiredError("A MAX subscription is required to download this chapter.")

        last_page = viewer.pages[-1].last_page
        current_chapter = last_page.current_chapter
        next_chapter = (
            last_page.next_chapter if last_page.next_chapter.chapter_id != 0 else None
        )

        current_chapter.sub_title = self._prepare_filename(current_chapter.sub_title)
        log.info(
            f"    {chapter_index}/{total_chapters}) Chapter "
            f"{viewer.chapter_name}: {current_chapter.sub_title}"
        )

        exporter = self.exporter(
            title=title_detail,
            chapter=current_chapter,
            next_chapter=next_chapter,
        )
        pages = [page.manga_page for page in viewer.pages if page.manga_page.image_url]

        self._process_chapter_pages(pages, viewer.chapter_name, exporter)
        exporter.close()

    def _process_chapter_pages(
        self,
        pages: Collection[MangaPageLike],
        chapter_name: str,
        exporter: ExporterLike,
    ) -> None:
        """Download all chapter pages and pass them to the exporter."""
        with click.progressbar(pages, label=chapter_name, show_pos=True) as progress_bar:
            page_counter = count()
            for page_index, page in zip(page_counter, progress_bar):
                output_index: int | range = page_index
                if PageType(page.type) == PageType.DOUBLE:
                    output_index = range(page_index, next(page_counter))

                if exporter.skip_image(output_index):
                    continue

                image_blob = self._download_image(page.image_url)
                exporter.add_image(image_blob, output_index)

    def _download_image(self, url: str) -> bytes:
        """Download an image blob from ``url``."""
        response = self.session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        return response.content

    def _dump_title_metadata(
        self,
        title_dump: TitleDumpLike,
        chapter_data_or_export_dir: Mapping[str, ChapterMetadata | Mapping[str, object]] | str | Path,
        export_dir: str | Path | None = None,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        resolved_chapter_data: Mapping[str, ChapterMetadata | Mapping[str, object]]
        resolved_export_dir: str | Path
        if export_dir is None:
            if isinstance(chapter_data_or_export_dir, Mapping):
                raise TypeError("Expected export directory when chapter metadata is omitted.")
            resolved_chapter_data = self._extract_chapter_data(title_dump)
            resolved_export_dir = chapter_data_or_export_dir
        else:
            if not isinstance(chapter_data_or_export_dir, Mapping):
                raise TypeError("Expected chapter metadata mapping when export_dir is provided.")
            resolved_chapter_data = chapter_data_or_export_dir
            resolved_export_dir = export_dir

        MetadataWriter.dump_title_metadata(title_dump, resolved_chapter_data, resolved_export_dir)
        log.info(f"    Metadata for title '{title_dump.title.name}' exported")

    def _extract_chapter_data(self, title_dump: TitleDumpLike) -> dict[str, ChapterMetadata]:
        """Collect chapter metadata from all chapter groups into one mapping."""
        return ChapterPlanner.extract_chapter_data(title_dump, self._prepare_filename)

    def _get_existing_files(self, export_path: Path) -> list[str]:
        """Return existing chapter stems for single-file output formats."""
        if not export_path.exists():
            return []

        extension = self._chapter_output_extension()
        if extension is None:
            return []

        existing_files = [file.stem for file in export_path.glob(f"*.{extension}")]
        log.info(f"    Found {len(existing_files)} existing chapter files in '{export_path}'.")
        log.debug(f"    Existing files: {existing_files}")
        return existing_files

    def _chapter_output_extension(self) -> str | None:
        """Return chapter-level output extension, or ``None`` for raw image mode."""
        if self.output_format in {"pdf", "cbz"}:
            return self.output_format
        return None

    def _filter_chapters_to_download(
        self,
        chapter_data: Mapping[str, ChapterMetadata],
        title_dump: TitleDumpLike,
        title_detail: TitleLike,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
    ) -> list[int]:
        """Return chapter IDs that are requested and not already exported."""
        return ChapterPlanner.filter_chapters_to_download(
            chapter_data,
            title_dump,
            title_detail,
            existing_files,
            requested_chapter_ids,
        )

    def _build_expected_filename(
        self,
        title_name: str,
        chapter_obj: ChapterLike,
        sub_title: str,
    ) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        del self
        return ChapterPlanner.build_expected_filename(title_name, chapter_obj, sub_title)

    def _find_chapter_by_id(self, title_dump: TitleDumpLike, chapter_id: int) -> ChapterLike | None:
        """Find and return a chapter object by ``chapter_id`` if available."""
        return ChapterPlanner.find_chapter_by_id(title_dump, chapter_id)

    def _has_last_page(self, viewer: MangaViewerLike) -> bool:
        """Return whether ``viewer`` includes a valid terminal page payload."""
        return bool(viewer.pages and viewer.pages[-1] and hasattr(viewer.pages[-1], "last_page"))

    def _prepare_filename(self, text: str) -> str:
        """Fix common encoding glitches and sanitize text for filesystem use."""
        fixed_text = text
        try:
            fixed_text = text.encode("latin1").decode("utf8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            log.warning(f"    Encoding fix skipped for: {text}")
        return escape_path(fixed_text)
