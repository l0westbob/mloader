"""Domain services and models for normalized download planning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Collection

from mloader.domain.manga import Chapter, ChapterGroup, MangaViewer, TitleDetail
from mloader.utils import chapter_name_to_int


@dataclass(frozen=True, slots=True)
class ChapterSelection:
    """Selected chapter IDs for one title."""

    title_id: int
    chapter_ids: frozenset[int]

    @property
    def chapter_count(self) -> int:
        """Return the number of selected chapters."""
        return len(self.chapter_ids)


@dataclass(frozen=True, slots=True)
class TitleDownloadPlan:
    """Concrete title details and chapters selected for download."""

    title_detail: TitleDetail
    selected_chapters: tuple[Chapter, ...]

    @property
    def title_id(self) -> int:
        """Return the selected title ID."""
        return self.title_detail.title.title_id

    @property
    def chapter_ids(self) -> frozenset[int]:
        """Return selected chapter IDs for this title."""
        return frozenset(chapter.chapter_id for chapter in self.selected_chapters)

    @property
    def chapter_count(self) -> int:
        """Return the number of selected chapters."""
        return len(self.selected_chapters)


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    """Concrete title/chapter plan for one download run."""

    title_plans: tuple[TitleDownloadPlan, ...]

    @property
    def selections(self) -> tuple[ChapterSelection, ...]:
        """Return ID-only selections derived from concrete title plans."""
        return tuple(
            ChapterSelection(title_id=title_plan.title_id, chapter_ids=title_plan.chapter_ids)
            for title_plan in self.title_plans
        )

    @property
    def title_count(self) -> int:
        """Return the number of selected titles."""
        return len(self.title_plans)

    @property
    def chapter_count(self) -> int:
        """Return the total number of selected chapters."""
        return sum(title_plan.chapter_count for title_plan in self.title_plans)


TitleDetailLoader = Callable[[int], TitleDetail]
MangaViewerLoader = Callable[[int], MangaViewer]


def build_download_plan(
    *,
    title_ids: Collection[int] | None,
    chapter_numbers: Collection[int] | None,
    chapter_ids: Collection[int] | None,
    min_chapter: int,
    max_chapter: int,
    last_chapter: bool,
    load_title_detail: TitleDetailLoader,
    load_viewer: MangaViewerLoader,
) -> DownloadPlan:
    """Resolve validated target filters into a concrete domain download plan."""
    selected_ids_by_title, fallback_chapters, loaded_title_details = _resolve_planning_inputs(
        title_ids=title_ids,
        chapter_numbers=chapter_numbers,
        chapter_ids=chapter_ids,
        min_chapter=min_chapter,
        max_chapter=max_chapter,
        last_chapter=last_chapter,
        load_title_detail=load_title_detail,
        load_viewer=load_viewer,
    )

    title_plans: list[TitleDownloadPlan] = []
    for title_id, selected_chapter_ids in sorted(selected_ids_by_title.items()):
        title_detail = loaded_title_details.get(title_id) or load_title_detail(title_id)
        chapters_by_id = {chapter.chapter_id: chapter for chapter in title_detail.chapters}
        selected_chapters = [
            chapter
            for chapter in title_detail.chapters
            if chapter.chapter_id in selected_chapter_ids
        ]
        selected_chapter_id_set = {chapter.chapter_id for chapter in selected_chapters}
        missing_chapter_ids = selected_chapter_ids - selected_chapter_id_set
        selected_chapters.extend(
            fallback_chapters[chapter_id]
            for chapter_id in sorted(missing_chapter_ids)
            if chapter_id in fallback_chapters and chapter_id not in chapters_by_id
        )
        title_plans.append(
            TitleDownloadPlan(
                title_detail=title_detail,
                selected_chapters=tuple(selected_chapters),
            )
        )

    return DownloadPlan(title_plans=tuple(title_plans))


def title_detail_with_selected_chapters(
    title_detail: TitleDetail,
    selected_chapters: Collection[Chapter],
) -> TitleDetail:
    """Return title details augmented with direct-ID selected chapters if needed."""
    missing_chapters = tuple(
        chapter
        for chapter in selected_chapters
        if title_detail.find_chapter(chapter.chapter_id) is None
    )
    if not missing_chapters:
        return title_detail
    return replace(
        title_detail,
        chapter_groups=(
            *title_detail.chapter_groups,
            ChapterGroup(
                first_chapters=missing_chapters,
                mid_chapters=(),
                last_chapters=(),
            ),
        ),
    )


def _resolve_planning_inputs(
    *,
    title_ids: Collection[int] | None,
    chapter_numbers: Collection[int] | None,
    chapter_ids: Collection[int] | None,
    min_chapter: int,
    max_chapter: int,
    last_chapter: bool,
    load_title_detail: TitleDetailLoader,
    load_viewer: MangaViewerLoader,
) -> tuple[dict[int, set[int]], dict[int, Chapter], dict[int, TitleDetail]]:
    """Resolve filters while carrying title details loaded during planning."""
    if not any((title_ids, chapter_numbers, chapter_ids)):
        raise ValueError("Expected at least one title or chapter id")

    remaining_title_ids = set(title_ids or [])
    provided_chapter_numbers = set(chapter_numbers or [])
    provided_chapter_ids = set(chapter_ids or [])
    direct_chapter_ids_by_title: dict[int, set[int]] = {}
    candidate_chapters_by_title: dict[int, list[Chapter]] = {}
    fallback_chapters_by_id: dict[int, Chapter] = {}
    loaded_title_details: dict[int, TitleDetail] = {}

    if provided_chapter_numbers and not remaining_title_ids and not provided_chapter_ids:
        raise ValueError("Chapter numbers require at least one title ID, --all, or viewer URL.")

    for chapter_id in provided_chapter_ids:
        viewer = load_viewer(chapter_id)
        current_title_id = viewer.title_id
        direct_chapter_ids_by_title.setdefault(current_title_id, set()).add(viewer.chapter_id)
        viewer_chapters = _viewer_chapters_for_planning(viewer)
        for chapter in viewer_chapters:
            fallback_chapters_by_id[chapter.chapter_id] = chapter

        if current_title_id in remaining_title_ids:
            remaining_title_ids.remove(current_title_id)
            candidate_chapters_by_title.setdefault(current_title_id, []).extend(viewer_chapters)
        else:
            candidate_chapters_by_title.setdefault(current_title_id, []).append(
                _viewer_current_chapter(viewer)
            )

    titles_requiring_full_details = set(remaining_title_ids)
    if provided_chapter_numbers:
        titles_requiring_full_details.update(candidate_chapters_by_title)

    for title_id in titles_requiring_full_details:
        title_detail = load_title_detail(title_id)
        loaded_title_details[title_id] = title_detail
        candidate_chapters_by_title[title_id] = list(title_detail.chapters)

    selected_ids_by_title: dict[int, set[int]] = {}
    for title_id, candidate_chapters in candidate_chapters_by_title.items():
        selected_chapters = _select_candidate_chapters(
            candidate_chapters,
            chapter_numbers=provided_chapter_numbers,
            min_chapter=min_chapter,
            max_chapter=max_chapter,
            last_chapter=last_chapter,
        )
        selected_ids = {chapter.chapter_id for chapter in selected_chapters}
        selected_ids.update(direct_chapter_ids_by_title.get(title_id, set()))
        selected_ids_by_title[title_id] = selected_ids

    return selected_ids_by_title, fallback_chapters_by_id, loaded_title_details


def _select_candidate_chapters(
    chapters: Collection[Chapter],
    *,
    chapter_numbers: Collection[int],
    min_chapter: int,
    max_chapter: int,
    last_chapter: bool,
) -> list[Chapter]:
    """Apply chapter-number/range selection to candidate chapters."""
    chapter_list = list(chapters)
    if last_chapter:
        return chapter_list[-1:]

    if chapter_numbers:
        return [
            chapter
            for chapter in chapter_list
            if (chapter_number := chapter_name_to_int(chapter.name)) is not None
            and chapter_number in chapter_numbers
            and min_chapter <= chapter_number <= max_chapter
        ]

    return [
        chapter
        for chapter in chapter_list
        if min_chapter <= (chapter_name_to_int(chapter.name) or 0) <= max_chapter
    ]


def _viewer_chapters_for_planning(viewer: MangaViewer) -> tuple[Chapter, ...]:
    """Return viewer chapter list or a fallback current chapter."""
    if viewer.chapters:
        return viewer.chapters
    return (_viewer_current_chapter(viewer),)


def _viewer_current_chapter(viewer: MangaViewer) -> Chapter:
    """Return the viewer's current chapter, synthesizing a minimal fallback if needed."""
    if viewer.last_page is not None:
        return viewer.last_page.current_chapter
    for chapter in viewer.chapters:
        if chapter.chapter_id == viewer.chapter_id:
            return chapter
    return Chapter(
        title_id=viewer.title_id,
        chapter_id=viewer.chapter_id,
        name=viewer.chapter_name,
        sub_title="",
        thumbnail_url="",
    )
