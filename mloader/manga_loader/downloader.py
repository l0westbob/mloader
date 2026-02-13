"""Download orchestration logic for titles, chapters, and page assets."""

from __future__ import annotations

import json
import logging
import sys
from itertools import count
from pathlib import Path
from typing import Any, Collection, Mapping

import click

from mloader.constants import PageType
from mloader.utils import escape_path

log = logging.getLogger(__name__)


class DownloadMixin:
    """Provide download and export orchestration for manga content."""

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

        export_path = Path(self.exporter.keywords["destination"]) / escape_path(
            title_detail.name
        ).title()

        if self.meta:
            self._dump_title_metadata(title_dump, export_path)

        chapter_data = self._extract_chapter_data(title_dump)
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
        title_detail: Any,
        chapter_index: int,
        total_chapters: int,
        chapter_id: int,
    ) -> None:
        """Download and export a single chapter."""
        viewer = self._load_pages(chapter_id)
        if not self._has_last_page(viewer):
            log.info("A MAX subscription is required to download this chapter.")
            sys.exit(1)

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
        pages: Collection[Any],
        chapter_name: str,
        exporter: Any,
    ) -> None:
        """Download all chapter pages and pass them to the exporter."""
        with click.progressbar(pages, label=chapter_name, show_pos=True) as progress_bar:
            page_counter = count()
            for page_index, page in zip(page_counter, progress_bar):
                if PageType(page.type) == PageType.DOUBLE:
                    page_index = range(page_index, next(page_counter))

                if exporter.skip_image(page_index):
                    continue

                image_blob = self._download_image(page.image_url)
                exporter.add_image(image_blob, page_index)

    def _download_image(self, url: str) -> bytes:
        """Download an image blob from ``url``."""
        response = self.session.get(url)
        response.raise_for_status()
        return response.content

    def _dump_title_metadata(self, title_dump: Any, export_dir: str | Path) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        chapter_data = {
            escape_path(key).title(): value
            for key, value in self._extract_chapter_data(title_dump).items()
        }
        export_dir_path = Path(export_dir)
        export_dir_path.mkdir(parents=True, exist_ok=True)

        title_data = {
            "non_appearance_info": title_dump.non_appearance_info,
            "number_of_views": title_dump.number_of_views,
            "overview": title_dump.overview,
            "name": title_dump.title.name,
            "author": title_dump.title.author,
            "portrait_image_url": title_dump.title.portrait_image_url,
            "chapters": chapter_data,
        }

        metadata_file = export_dir_path / "title_metadata.json"
        with metadata_file.open("w", encoding="utf-8") as file_obj:
            json.dump(title_data, file_obj, ensure_ascii=False, indent=4)

        log.info(f"    Metadata for title '{title_data['name']}' exported")

    def _extract_chapter_data(self, title_dump: Any) -> dict[str, dict[str, Any]]:
        """Collect chapter metadata from all chapter groups into one mapping."""
        chapter_data: dict[str, dict[str, Any]] = {}
        for group in title_dump.chapter_list_group:
            for chapter_list in (
                group.first_chapter_list,
                group.mid_chapter_list,
                group.last_chapter_list,
            ):
                for chapter in chapter_list:
                    prepared_sub_title = self._prepare_filename(chapter.sub_title)
                    chapter_data[prepared_sub_title] = {
                        "thumbnail_url": chapter.thumbnail_url,
                        "chapter_id": chapter.chapter_id,
                    }
        return chapter_data

    def _get_existing_files(self, export_path: Path) -> list[str]:
        """Return already exported PDF chapter stems in ``export_path``."""
        if not export_path.exists():
            return []

        existing_files = [file.stem for file in export_path.glob("*.pdf")]
        log.info(f"    Found {len(existing_files)} existing chapter files in '{export_path}'.")
        log.debug(f"    Existing files: {existing_files}")
        return existing_files

    def _filter_chapters_to_download(
        self,
        chapter_data: Mapping[str, Mapping[str, Any]],
        title_dump: Any,
        title_detail: Any,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
    ) -> list[int]:
        """Return chapter IDs that are requested and not already exported."""
        chapters_to_download: list[int] = []
        for sub_title, data in chapter_data.items():
            chapter_id = int(data["chapter_id"])
            chapter_obj = self._find_chapter_by_id(title_dump, chapter_id)

            if not chapter_obj:
                log.warning(f"    Chapter ID {chapter_id} not found in title dump!")
                continue

            expected_filename = self._build_expected_filename(
                escape_path(title_detail.name).title(),
                chapter_obj,
                sub_title,
            )
            log.debug(f"    Checking if '{expected_filename}.pdf' exists...")

            if expected_filename in existing_files:
                log.info(f"    Skipping Chapter '{chapter_obj.name}': Already exists.")
            else:
                chapters_to_download.append(chapter_id)

        return [cid for cid in chapters_to_download if cid in requested_chapter_ids]

    def _build_expected_filename(
        self,
        title_name: str,
        chapter_obj: Any,
        sub_title: str,
    ) -> str:
        """Build the normalized filename stem expected for a chapter PDF."""
        sanitized_title = escape_path(title_name)
        sanitized_chapter_name = escape_path(chapter_obj.name.lstrip("#").strip())
        sanitized_sub_title = escape_path(sub_title)
        return f"{sanitized_title} - {sanitized_chapter_name} - {sanitized_sub_title}"

    def _find_chapter_by_id(self, title_dump: Any, chapter_id: int) -> Any | None:
        """Find and return a chapter object by ``chapter_id`` if available."""
        for group in title_dump.chapter_list_group:
            for chapter_list in (
                group.first_chapter_list,
                group.mid_chapter_list,
                group.last_chapter_list,
            ):
                for chapter in chapter_list:
                    if chapter.chapter_id == chapter_id:
                        return chapter
        return None

    def _has_last_page(self, viewer: Any) -> bool:
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
