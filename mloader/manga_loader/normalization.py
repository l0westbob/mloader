"""Normalization helpers that map input IDs to downloadable chapter sets."""

from collections import namedtuple
from itertools import chain
from typing import Collection, Dict, Set
from mloader.utils import chapter_name_to_int

MangaList = Dict[int, Set[int]]


class NormalizationMixin:
    """Provide chapter/title normalization logic for loader input."""

    def _normalize_ids(
            self,
            title_ids: Collection[int],
            chapter_ids: Collection[int],
            min_chapter: int,
            max_chapter: int,
            last_chapter: bool = False,
    ) -> MangaList:
        """
        Normalize manga title and chapter IDs into a mapping.

        Merges provided title and chapter IDs into a single mapping where each title ID maps
        to a set of chapter IDs that pass filtering based on the chapter range or last-chapter flag.
        """
        if not any((title_ids, chapter_ids)):
            raise ValueError("Expected at least one title or chapter id")

        remaining_title_ids = set(title_ids or [])
        provided_chapter_ids = set(chapter_ids or [])
        manga_mapping = {}
        ChapterMetadata = namedtuple("ChapterMetadata", "id name")

        for chapter_id in provided_chapter_ids:
            viewer = self._load_pages(chapter_id)
            current_title_id = viewer.title_id
            if current_title_id in remaining_title_ids:
                remaining_title_ids.remove(current_title_id)
                manga_mapping.setdefault(current_title_id, []).extend(
                    ChapterMetadata(ch.chapter_id, ch.name) for ch in viewer.chapters
                )
            else:
                manga_mapping.setdefault(current_title_id, []).append(
                    ChapterMetadata(viewer.chapter_id, viewer.chapter_name)
                )

        for title_id in remaining_title_ids:
            title_details = self._get_title_details(title_id)
            manga_mapping[title_id] = [
                ChapterMetadata(ch.chapter_id, ch.name)
                for group in title_details.chapter_list_group
                for ch in chain(
                    group.first_chapter_list, group.mid_chapter_list, group.last_chapter_list
                )
            ]

        for title_id, chapters in manga_mapping.items():
            if last_chapter:
                filtered_chapters = chapters[-1:]
            else:
                filtered_chapters = [
                    ch for ch in chapters
                    if min_chapter <= (chapter_name_to_int(ch.name) or 0) <= max_chapter
                ]
            manga_mapping[title_id] = {ch.id for ch in filtered_chapters}

        return manga_mapping

    def _prepare_normalized_manga_list(
            self,
            title_ids: Collection[int],
            chapter_ids: Collection[int],
            min_chapter: int,
            max_chapter: int,
            last_chapter: bool,
    ) -> MangaList:
        """
        Prepare the normalized manga mapping from title and chapter IDs.
        """
        return self._normalize_ids(title_ids, chapter_ids, min_chapter, max_chapter, last_chapter)
