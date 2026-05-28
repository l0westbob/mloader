"""Typed protocol contracts shared across runtime components."""

from __future__ import annotations

from typing import Mapping, MutableMapping, Protocol

PageIndex = int | range


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
    landscape_image_url: str
    language: int


class ResponseLike(Protocol):
    """Minimal HTTP response contract used by loader transport code."""

    content: bytes

    def raise_for_status(self) -> None:
        """Raise for non-successful HTTP responses."""


class SessionLike(Protocol):
    """Minimal HTTP session contract used by runtime transport code."""

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

    def add_image(self, image_data: bytes, index: PageIndex) -> None:
        """Persist one image payload."""

    def skip_image(self, index: PageIndex) -> bool:
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
        next_chapter: ChapterLike | None = None,
    ) -> ExporterLike:
        """Create and return an exporter instance."""


class PayloadCaptureLike(Protocol):
    """Contract for persisting API payload captures."""

    def capture(
        self,
        *,
        endpoint: str,
        identifier: str | int,
        url: str,
        params: Mapping[str, object],
        response_content: bytes,
    ) -> None:
        """Persist payload capture artifacts."""
