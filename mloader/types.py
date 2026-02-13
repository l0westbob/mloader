"""Typed protocol contracts shared across runtime components."""

from __future__ import annotations

from typing import Mapping, MutableMapping, Protocol, Sequence


class ChapterLike(Protocol):
    """Minimal chapter shape used by loader and exporter code."""

    chapter_id: int
    name: str
    sub_title: str
    thumbnail_url: str


class TitleLike(Protocol):
    """Minimal title shape used by loader and exporter code."""

    name: str
    author: str
    portrait_image_url: str
    language: int


class ChapterGroupLike(Protocol):
    """Shape for grouped chapter lists in title details payloads."""

    first_chapter_list: Sequence[ChapterLike]
    mid_chapter_list: Sequence[ChapterLike]
    last_chapter_list: Sequence[ChapterLike]


class TitleDumpLike(Protocol):
    """Shape for title details payload used by downloader."""

    title: TitleLike
    chapter_list_group: Sequence[ChapterGroupLike]
    non_appearance_info: str
    number_of_views: int
    overview: str


class MangaPageLike(Protocol):
    """Shape for chapter page image payload."""

    image_url: str
    type: int


class LastPageLike(Protocol):
    """Shape for final page metadata payload."""

    current_chapter: ChapterLike
    next_chapter: ChapterLike


class ViewerPageLike(Protocol):
    """Shape for a viewer page entry."""

    manga_page: MangaPageLike
    last_page: LastPageLike


class MangaViewerLike(Protocol):
    """Shape for manga viewer payload used in downloads."""

    title_id: int
    chapter_id: int
    chapter_name: str
    chapters: Sequence[ChapterLike]
    pages: Sequence[ViewerPageLike]


class ResponseLike(Protocol):
    """Minimal HTTP response contract used by loader transport code."""

    content: bytes

    def raise_for_status(self) -> None:
        """Raise for non-successful HTTP responses."""


class SessionLike(Protocol):
    """Minimal HTTP session contract used by loader mixins."""

    headers: MutableMapping[str, str]

    def get(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> ResponseLike:
        """Perform an HTTP GET request and return a response object."""

    def mount(self, prefix: str, adapter: object) -> None:
        """Attach a transport adapter for matching URL prefixes."""


class ExporterLike(Protocol):
    """Minimal exporter contract used by downloader orchestration."""

    def add_image(self, image_data: bytes, index: int | range) -> None:
        """Persist one image payload."""

    def skip_image(self, index: int | range) -> bool:
        """Return whether a page index should be skipped."""

    def close(self) -> None:
        """Finalize exporter output."""


class ExporterFactoryLike(Protocol):
    """Factory contract used by loader to construct exporters per chapter."""

    def __call__(
        self,
        *,
        title: TitleLike,
        chapter: ChapterLike,
        next_chapter: ChapterLike | None,
    ) -> ExporterLike:
        """Create and return an exporter instance."""
