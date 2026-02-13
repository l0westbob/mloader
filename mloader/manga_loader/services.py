"""Small focused services used by downloader orchestration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Collection, Mapping

from mloader.types import ChapterLike, TitleDumpLike, TitleLike
from mloader.utils import escape_path

log = logging.getLogger(__name__)


def _coerce_chapter_metadata(data: ChapterMetadata | Mapping[str, object]) -> ChapterMetadata:
    """Normalize chapter metadata from dataclass or mapping payloads."""
    if isinstance(data, ChapterMetadata):
        return data

    chapter_id_raw = data.get("chapter_id", 0)
    chapter_id = chapter_id_raw if isinstance(chapter_id_raw, int) else int(str(chapter_id_raw))
    thumbnail_url_raw = data.get("thumbnail_url", "")
    return ChapterMetadata(
        thumbnail_url=str(thumbnail_url_raw),
        chapter_id=chapter_id,
    )


@dataclass(frozen=True)
class ChapterMetadata:
    """Normalized chapter metadata used during planning."""

    thumbnail_url: str
    chapter_id: int

    def __getitem__(self, key: str) -> str | int:
        """Provide mapping-like access for compatibility with dict-shaped tests."""
        if key == "thumbnail_url":
            return self.thumbnail_url
        if key == "chapter_id":
            return self.chapter_id
        raise KeyError(key)


class ChapterPlanner:
    """Compute chapter extraction and download planning decisions."""

    @staticmethod
    def extract_chapter_data(
        title_dump: TitleDumpLike,
        prepare_filename: Callable[[str], str],
    ) -> dict[str, ChapterMetadata]:
        """Collect chapter metadata from all chapter groups into one mapping."""
        chapter_data: dict[str, ChapterMetadata] = {}
        for group in title_dump.chapter_list_group:
            for chapter_list in (
                group.first_chapter_list,
                group.mid_chapter_list,
                group.last_chapter_list,
            ):
                for chapter in chapter_list:
                    prepared_sub_title = prepare_filename(chapter.sub_title)
                    chapter_data[prepared_sub_title] = ChapterMetadata(
                        thumbnail_url=chapter.thumbnail_url,
                        chapter_id=chapter.chapter_id,
                    )
        return chapter_data

    @staticmethod
    def find_chapter_by_id(title_dump: TitleDumpLike, chapter_id: int) -> ChapterLike | None:
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

    @staticmethod
    def build_expected_filename(title_name: str, chapter_obj: ChapterLike, sub_title: str) -> str:
        """Build normalized filename stem expected for chapter-level outputs."""
        sanitized_title = escape_path(title_name)
        sanitized_chapter_name = escape_path(chapter_obj.name.lstrip("#").strip())
        sanitized_sub_title = escape_path(sub_title)
        return f"{sanitized_title} - {sanitized_chapter_name} - {sanitized_sub_title}"

    @staticmethod
    def filter_chapters_to_download(
        chapter_data: Mapping[str, ChapterMetadata | Mapping[str, object]],
        title_dump: TitleDumpLike,
        title_detail: TitleLike,
        existing_files: Collection[str],
        requested_chapter_ids: Collection[int],
    ) -> list[int]:
        """Return requested chapter IDs that do not yet exist on disk."""
        chapters_to_download: list[int] = []
        for sub_title, data in chapter_data.items():
            metadata = _coerce_chapter_metadata(data)
            chapter_obj = ChapterPlanner.find_chapter_by_id(title_dump, metadata.chapter_id)
            if chapter_obj is None:
                # Keep warning for visibility when upstream chapter metadata is inconsistent.
                log.warning("Chapter id %s not found in title dump; skipping", metadata.chapter_id)
                continue
            expected_filename = ChapterPlanner.build_expected_filename(
                escape_path(title_detail.name).title(),
                chapter_obj,
                sub_title,
            )
            if expected_filename not in existing_files:
                chapters_to_download.append(metadata.chapter_id)
        return [chapter_id for chapter_id in chapters_to_download if chapter_id in requested_chapter_ids]


class MetadataWriter:
    """Write metadata outputs derived from title details."""

    @staticmethod
    def dump_title_metadata(
        title_dump: TitleDumpLike,
        chapter_data: Mapping[str, ChapterMetadata | Mapping[str, object]],
        export_dir: str | Path,
    ) -> None:
        """Write title-level metadata JSON into ``export_dir``."""
        normalized_chapter_data = {
            escape_path(key).title(): {
                "thumbnail_url": metadata.thumbnail_url,
                "chapter_id": metadata.chapter_id,
            }
            for key, value in chapter_data.items()
            for metadata in [_coerce_chapter_metadata(value)]
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
            "chapters": normalized_chapter_data,
        }

        metadata_file = export_dir_path / "title_metadata.json"
        with metadata_file.open("w", encoding="utf-8") as file_obj:
            json.dump(title_data, file_obj, ensure_ascii=False, indent=4)
