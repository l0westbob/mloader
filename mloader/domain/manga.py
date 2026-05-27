"""Stable domain models for MangaPlus title and chapter payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chapter:
    """Domain representation of one MangaPlus chapter."""

    title_id: int
    chapter_id: int
    name: str
    sub_title: str
    thumbnail_url: str
    start_timestamp: int = 0
    end_timestamp: int = 0
    already_viewed: bool = False
    is_vertical_only: bool = False


@dataclass(frozen=True, slots=True)
class Title:
    """Domain representation of one MangaPlus title."""

    title_id: int
    name: str
    author: str
    portrait_image_url: str
    landscape_image_url: str
    language: int


@dataclass(frozen=True, slots=True)
class ChapterGroup:
    """Domain representation of grouped title-detail chapter lists."""

    first_chapters: tuple[Chapter, ...]
    mid_chapters: tuple[Chapter, ...]
    last_chapters: tuple[Chapter, ...]

    @property
    def chapters(self) -> tuple[Chapter, ...]:
        """Return all chapters in MangaPlus display order."""
        return (*self.first_chapters, *self.mid_chapters, *self.last_chapters)


@dataclass(frozen=True, slots=True)
class TitleDetail:
    """Domain representation of a title-detail response."""

    title: Title
    title_image_url: str
    overview: str
    non_appearance_info: str
    number_of_views: int
    chapter_groups: tuple[ChapterGroup, ...]

    @property
    def chapters(self) -> tuple[Chapter, ...]:
        """Return all chapters from all groups in MangaPlus display order."""
        return tuple(chapter for group in self.chapter_groups for chapter in group.chapters)

    def find_chapter(self, chapter_id: int) -> Chapter | None:
        """Return the chapter matching ``chapter_id``, if it exists in this title."""
        return next(
            (chapter for chapter in self.chapters if chapter.chapter_id == chapter_id),
            None,
        )


@dataclass(frozen=True, slots=True)
class MangaPage:
    """Domain representation of one downloadable page image."""

    image_url: str
    width: int
    height: int
    page_type: int
    encryption_key: str


@dataclass(frozen=True, slots=True)
class LastPage:
    """Domain representation of terminal viewer-page metadata."""

    current_chapter: Chapter
    next_chapter: Chapter | None


@dataclass(frozen=True, slots=True)
class ViewerPage:
    """Domain representation of one viewer page envelope."""

    manga_page: MangaPage | None
    last_page: LastPage | None


@dataclass(frozen=True, slots=True)
class MangaViewer:
    """Domain representation of a chapter viewer response."""

    title_id: int
    chapter_id: int
    title_name: str
    chapter_name: str
    chapters: tuple[Chapter, ...]
    pages: tuple[ViewerPage, ...]

    @property
    def last_page(self) -> LastPage | None:
        """Return terminal viewer-page metadata when present."""
        return next(
            (page.last_page for page in reversed(self.pages) if page.last_page is not None),
            None,
        )

    @property
    def downloadable_pages(self) -> tuple[MangaPage, ...]:
        """Return only pages that include downloadable image URLs."""
        return tuple(
            page.manga_page
            for page in self.pages
            if page.manga_page is not None and page.manga_page.image_url
        )
