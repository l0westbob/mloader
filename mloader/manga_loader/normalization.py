"""Normalization helpers that map input IDs to downloadable chapter sets."""

from dataclasses import dataclass
from itertools import chain
from typing import Collection

from mloader.types import MangaViewerLike, TitleDumpLike
from mloader.utils import chapter_name_to_int

MangaList = dict[int, set[int]]


@dataclass(frozen=True)
class ChapterMetadata:
    """Temporary chapter metadata used during normalization filtering."""

    id: int
    name: str


class NormalizationMixin:
    """Provide chapter/title normalization logic for loader input."""

    def _load_pages(self, chapter_id: str | int) -> MangaViewerLike:
        """Load chapter viewer payload for ``chapter_id``."""
        raise NotImplementedError

    def _get_title_details(self, title_id: str | int) -> TitleDumpLike:
        """Load title detail payload for ``title_id``."""
        raise NotImplementedError

    def _normalize_ids(
            self,
            title_ids: Collection[int] | None,
            chapter_numbers: Collection[int] | None,
            chapter_ids: Collection[int] | None,
            min_chapter: int,
            max_chapter: int,
            last_chapter: bool = False,
    ) -> MangaList:
        """
        Normalize manga title and chapter IDs into a mapping.

        Merges provided title and chapter IDs into a single mapping where each title ID maps
        to a set of chapter IDs that pass filtering based on the chapter range or last-chapter flag.
        """
        if not any((title_ids, chapter_numbers, chapter_ids)):
            raise ValueError("Expected at least one title or chapter id")

        remaining_title_ids = set(title_ids or [])
        provided_chapter_numbers = set(chapter_numbers or [])
        provided_chapter_ids = set(chapter_ids or [])
        direct_chapter_ids_by_title: dict[int, set[int]] = {}
        manga_mapping: dict[int, list[ChapterMetadata]] = {}

        if provided_chapter_numbers and not remaining_title_ids and not provided_chapter_ids:
            raise ValueError("Chapter numbers require at least one title ID, --all, or viewer URL.")

        for chapter_id in provided_chapter_ids:
            viewer = self._load_pages(chapter_id)
            current_title_id = viewer.title_id
            direct_chapter_ids_by_title.setdefault(current_title_id, set()).add(viewer.chapter_id)
            if current_title_id in remaining_title_ids:
                remaining_title_ids.remove(current_title_id)
                manga_mapping.setdefault(current_title_id, []).extend(
                    ChapterMetadata(ch.chapter_id, ch.name) for ch in viewer.chapters
                )
            else:
                manga_mapping.setdefault(current_title_id, []).append(
                    ChapterMetadata(viewer.chapter_id, viewer.chapter_name)
                )

        titles_requiring_full_details = set(remaining_title_ids)
        if provided_chapter_numbers:
            titles_requiring_full_details.update(manga_mapping.keys())

        for title_id in titles_requiring_full_details:
            title_details = self._get_title_details(title_id)
            manga_mapping[title_id] = [
                ChapterMetadata(ch.chapter_id, ch.name)
                for group in title_details.chapter_list_group
                for ch in chain(
                    group.first_chapter_list, group.mid_chapter_list, group.last_chapter_list
                )
            ]

        normalized_mapping: MangaList = {}
        for title_id, chapters in manga_mapping.items():
            if last_chapter:
                filtered_chapters = chapters[-1:]
            elif provided_chapter_numbers:
                filtered_chapters = [
                    ch for ch in chapters
                    if (chapter_number := chapter_name_to_int(ch.name)) is not None
                    and chapter_number in provided_chapter_numbers
                    and min_chapter <= chapter_number <= max_chapter
                ]
            else:
                filtered_chapters = [
                    ch for ch in chapters
                    if min_chapter <= (chapter_name_to_int(ch.name) or 0) <= max_chapter
                ]
            resolved_ids = {ch.id for ch in filtered_chapters}
            resolved_ids.update(direct_chapter_ids_by_title.get(title_id, set()))
            normalized_mapping[title_id] = resolved_ids

        return normalized_mapping

    def _prepare_normalized_manga_list(
            self,
            title_ids: Collection[int] | None,
            chapter_numbers: Collection[int] | None,
            chapter_ids: Collection[int] | None,
            min_chapter: int,
            max_chapter: int,
            last_chapter: bool,
    ) -> MangaList:
        """
        Prepare the normalized manga mapping from title and chapter IDs.
        """
        return self._normalize_ids(
            title_ids,
            chapter_numbers,
            chapter_ids,
            min_chapter,
            max_chapter,
            last_chapter,
        )
