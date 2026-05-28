"""Map MangaPlus protobuf payload objects into stable domain DTOs."""

from __future__ import annotations

from typing import Any

from mloader.domain.manga import (
    Chapter,
    ChapterGroup,
    LastPage,
    MangaPage,
    MangaViewer,
    Title,
    TitleDetail,
    ViewerPage,
)


def chapter_from_proto(chapter: Any) -> Chapter:
    """Map a protobuf chapter object into a domain chapter."""
    return Chapter(
        title_id=int(getattr(chapter, "title_id", 0)),
        chapter_id=int(getattr(chapter, "chapter_id", 0)),
        name=str(getattr(chapter, "name", "")),
        sub_title=str(getattr(chapter, "sub_title", "")),
        thumbnail_url=str(getattr(chapter, "thumbnail_url", "")),
        start_timestamp=int(getattr(chapter, "start_timestamp", 0)),
        end_timestamp=int(getattr(chapter, "end_timestamp", 0)),
        already_viewed=bool(getattr(chapter, "already_viewed", False)),
        is_vertical_only=bool(getattr(chapter, "is_vertical_only", False)),
    )


def title_from_proto(title: Any) -> Title:
    """Map a protobuf title object into a domain title."""
    return Title(
        title_id=int(getattr(title, "title_id", 0)),
        name=str(getattr(title, "name", "")),
        author=str(getattr(title, "author", "")),
        portrait_image_url=str(getattr(title, "portrait_image_url", "")),
        landscape_image_url=str(getattr(title, "landscape_image_url", "")),
        language=int(getattr(title, "language", 0)),
    )


def chapter_group_from_proto(group: Any) -> ChapterGroup:
    """Map a protobuf chapter group into a domain chapter group."""
    return ChapterGroup(
        first_chapters=tuple(
            chapter_from_proto(chapter) for chapter in getattr(group, "first_chapter_list", ())
        ),
        mid_chapters=tuple(
            chapter_from_proto(chapter) for chapter in getattr(group, "mid_chapter_list", ())
        ),
        last_chapters=tuple(
            chapter_from_proto(chapter) for chapter in getattr(group, "last_chapter_list", ())
        ),
    )


def title_detail_from_proto(title_detail: Any) -> TitleDetail:
    """Map a protobuf title-detail view into a domain title detail."""
    chapter_groups = tuple(
        chapter_group_from_proto(group) for group in getattr(title_detail, "chapter_list_group", ())
    )
    if not any(group.chapters for group in chapter_groups):
        flat_chapters = tuple(
            chapter_from_proto(chapter) for chapter in getattr(title_detail, "chapter_list", ())
        )
        if flat_chapters:
            chapter_groups = (
                ChapterGroup(
                    first_chapters=flat_chapters,
                    mid_chapters=(),
                    last_chapters=(),
                ),
            )

    return TitleDetail(
        title=title_from_proto(title_detail.title),
        title_image_url=str(getattr(title_detail, "title_image_url", "")),
        overview=str(getattr(title_detail, "overview", "")),
        non_appearance_info=str(getattr(title_detail, "non_appearance_info", "")),
        number_of_views=int(getattr(title_detail, "number_of_views", 0)),
        chapter_groups=chapter_groups,
    )


def manga_page_from_proto(manga_page: Any) -> MangaPage:
    """Map a protobuf manga-page object into a domain page."""
    return MangaPage(
        image_url=str(getattr(manga_page, "image_url", "")),
        width=int(getattr(manga_page, "width", 0)),
        height=int(getattr(manga_page, "height", 0)),
        page_type=int(getattr(manga_page, "type", 0)),
        encryption_key=str(getattr(manga_page, "encryption_key", "")),
    )


def _optional_chapter_from_proto(chapter: Any) -> Chapter | None:
    """Map a protobuf chapter when it carries an identity, otherwise return ``None``."""
    if int(getattr(chapter, "chapter_id", 0)) == 0:
        return None
    return chapter_from_proto(chapter)


def last_page_from_proto(last_page: Any) -> LastPage | None:
    """Map terminal viewer metadata when present."""
    current_chapter = _optional_chapter_from_proto(last_page.current_chapter)
    if current_chapter is None:
        return None
    return LastPage(
        current_chapter=current_chapter,
        next_chapter=_optional_chapter_from_proto(last_page.next_chapter),
    )


def viewer_page_from_proto(page: Any) -> ViewerPage:
    """Map a protobuf viewer page envelope into a domain viewer page."""
    manga_page = manga_page_from_proto(page.manga_page)
    if not manga_page.image_url:
        manga_page = None
    return ViewerPage(
        manga_page=manga_page,
        last_page=last_page_from_proto(page.last_page),
    )


def manga_viewer_from_proto(viewer: Any) -> MangaViewer:
    """Map a protobuf manga-viewer payload into a domain viewer."""
    return MangaViewer(
        title_id=int(getattr(viewer, "title_id", 0)),
        chapter_id=int(getattr(viewer, "chapter_id", 0)),
        title_name=str(getattr(viewer, "title_name", "")),
        chapter_name=str(getattr(viewer, "chapter_name", "")),
        chapters=tuple(chapter_from_proto(chapter) for chapter in getattr(viewer, "chapters", ())),
        pages=tuple(viewer_page_from_proto(page) for page in getattr(viewer, "pages", ())),
    )


def titles_from_all_titles_proto(all_titles: Any) -> tuple[Title, ...]:
    """Map a protobuf title-index payload into a flat title tuple."""
    return tuple(
        title_from_proto(title)
        for title_group in getattr(all_titles, "title_groups", ())
        for title in getattr(title_group, "titles", ())
    )
